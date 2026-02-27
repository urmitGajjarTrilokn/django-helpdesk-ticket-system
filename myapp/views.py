from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Q, Avg, OuterRef, Subquery, Count
from django.http import HttpResponse, FileResponse, JsonResponse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.paginator import Paginator
from django.urls import reverse
from datetime import datetime, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io

from .models import (
    UserProfile, TaskDetail, MyCart, ActivityLog,
    UserComment, Category, Notification, Department, DepartmentMember,
    TaskHistory, TaskRating,
    CannedResponse,
)
from .decorators import (
    department_member_required,
    admin_required,
    LoginRoleAuthorization,
)
from .analytics import (
    get_date_range, get_task_statistics, get_tasks_over_time,
    get_department_statistics, get_department_comparison,
    get_top_task_creators, get_top_task_resolvers,
    get_priority_distribution, get_category_distribution,
    prepare_export_data,
)
from .notifications import (
    create_notification,
    notify_task_created, notify_task_updated,
    notify_task_closed, notify_task_resolved, notify_task_reopened,
    notify_task_commented,
    notify_task_rated,
)
from .forms import (
    LoginForm, RegisterForm, UserProfileForm, TaskDetailForm,
    UserCommentForm, TaskUpdateForm, TaskFilterForm, CategoryForm,
    AccountSettingsForm,
)


def log_activity(user, action, title, description='', task=None, old_value='', new_value=''):
    ActivityLog.objects.create(
        user=user, task=task, action=action,
        title=title, description=description,
        old_value=old_value, new_value=new_value,
    )

def _is_admin_user(user):
    """Superuser is the only admin. No role field needed."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser

def _ensure_userprofile_and_permissions(user):
    """Just ensures a UserProfile exists. No role needed."""
    if not user or not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _is_department_member(user, task):
    if not task.assigned_department:
        return False
    return DepartmentMember.objects.filter(
        user=user, department=task.assigned_department, is_active=True
    ).exists()


def _can_view_task(user, task):
    if _is_admin_user(user):
        return True
    if task.TASK_CREATED_id == user.id:
        return True
    if task.assigned_to_id == user.id:
        return True
                                                                            
    return MyCart.objects.filter(user=user, task=task).exists()

def _can_work_on_task(user, task):
    if user.is_superuser:
        return False
    if task.TASK_CREATED_id == user.id:
        return True
    if task.assigned_to_id == user.id:
        return True
    return MyCart.objects.filter(user=user, task=task).exists()


def _sync_mycart_for_user(user):
    if not user.is_authenticated or user.is_superuser:
        return

    department_ids = DepartmentMember.objects.filter(
        user=user, is_active=True
    ).values_list('department_id', flat=True)

    rejected_task_ids = set(
        TaskHistory.objects.filter(
            changed_by=user,
            action_type='REJECTED'
        ).values_list('task_id', flat=True)
    )

    eligible_tasks = TaskDetail.objects.filter(
        ~Q(TASK_STATUS__in=['Closed', 'Resolved', 'Expired'])
    ).filter(
        Q(assigned_to=user) |
        (
            Q(assigned_department_id__in=department_ids) &
            Q(assigned_to__isnull=True)
        )
    ).exclude(
        TASK_CREATED=user
    ).exclude(
        Q(id__in=rejected_task_ids) & ~Q(assigned_to=user)
    ).distinct()

    eligible_task_ids = set(eligible_tasks.values_list('id', flat=True))
    existing_task_ids = set(
        MyCart.objects.filter(user=user).values_list('task_id', flat=True)
    )

    for task_id in (eligible_task_ids - existing_task_ids):
        MyCart.objects.create(user=user, task_id=task_id)

    if existing_task_ids:
        MyCart.objects.filter(user=user).exclude(
            task_id__in=eligible_task_ids
        ).delete()

    if rejected_task_ids:
        MyCart.objects.filter(
            user=user,
            task_id__in=rejected_task_ids
        ).exclude(task__assigned_to=user).delete()


def _is_non_rejectable_assignment(user, task):
    if task.TASK_STATUS == 'Reopen':
        return True

    if task.assigned_by_id and task.assigned_by.is_superuser:
        return True

    latest_assigned = (
        TaskHistory.objects
        .filter(task=task, action_type='ASSIGNED')
        .order_by('-changed_at')
        .first()
    )
    if (
        latest_assigned
        and latest_assigned.new_value == user.username
        and latest_assigned.description
        and 'Auto-assigned to' in latest_assigned.description
    ):
        latest_reopened = (
            TaskHistory.objects
            .filter(task=task, action_type='REOPENED')
            .order_by('-changed_at')
            .first()
        )
        if not latest_reopened or latest_reopened.changed_at <= latest_assigned.changed_at:
            return True

    return False


def _auto_assign_on_department_rejection(task, rejected_by):
    """
    Auto-assign only when rejection leaves a single non-rejecting member,
    or when everyone in the department has rejected (fallback to last member).
    """
    if not task.assigned_department_id:
        return None
    if task.TASK_STATUS in ['Closed', 'Resolved', 'Expired']:
        return None

    memberships = (
        DepartmentMember.objects
        .filter(
            department=task.assigned_department,
            is_active=True,
            user__is_active=True,
        )
        .select_related('user')
        .order_by('-id')
    )
    if not memberships.exists():
        return None

    creator_id = task.TASK_CREATED_id
    assignable_memberships = memberships.exclude(user_id=creator_id)
    if not assignable_memberships.exists():
        return None

    preferred_memberships = assignable_memberships.exclude(user_id=rejected_by.id)
    active_user_ids = list(assignable_memberships.values_list('user_id', flat=True))
    rejected_user_ids = set(
        TaskHistory.objects.filter(
            task=task,
            action_type='REJECTED',
            changed_by_id__in=active_user_ids,
        ).values_list('changed_by_id', flat=True)
    )
    rejected_user_ids.add(rejected_by.id)

    remaining_memberships = preferred_memberships.exclude(user_id__in=rejected_user_ids)
    remaining_count = remaining_memberships.count()

    assignee_membership = None
    if remaining_count >= 1:
        assignee_membership = remaining_memberships.first()

    if not assignee_membership:
        return None

    assignee = assignee_membership.user
    if task.assigned_to_id == assignee.id:
        return assignee

    old_assignee_name = task.assigned_to.username if task.assigned_to_id else 'Unassigned'
    task.assigned_to = assignee
    task.TASK_HOLDER = assignee.username
    task.save(update_fields=['assigned_to', 'TASK_HOLDER'])
    MyCart.objects.get_or_create(user=assignee, task=task)

    TaskHistory.objects.create(
        task=task,
        changed_by=rejected_by,
        action_type='ASSIGNED',
        old_value=old_assignee_name,
        new_value=assignee.username,
        description=(
            f'Auto-assigned to {assignee.username} after department rejections.'
        ),
    )
    create_notification(
        user=assignee,
        notification_type='TASK_ASSIGNED',
        title=f'Auto-assigned task #{task.id}',
        message=f'Task "{task.TASK_TITLE}" was auto-assigned to you after rejections.',
        task=task,
        extra_data={
            'auto_assigned': True,
            'department': task.assigned_department.name if task.assigned_department else '',
            'triggered_by': rejected_by.username,
        },
    )
    return assignee


def _get_primary_department_id(user):
    membership = DepartmentMember.objects.filter(
        user=user, is_active=True
    ).order_by('department__name').first()
    return membership.department_id if membership else None


def _get_dashboard_redirect_url(user):
    if user.is_superuser:
        return reverse('base')
    return reverse('base')

def _notifications_for_user(user):
    base_qs = Notification.objects.filter(user=user).select_related('task', 'task__assigned_department')
    if _is_admin_user(user):
        return base_qs

    department_ids = DepartmentMember.objects.filter(
        user=user, is_active=True
    ).values_list('department_id', flat=True)

    return base_qs.filter(task__assigned_department_id__in=department_ids)

def landing_page(request):
    if request.user.is_authenticated:
        return redirect(_get_dashboard_redirect_url(request.user))
    return render(request, 'landing.html')

@login_required
def Basepage(request, dept_id=None):
    if not request.user.is_authenticated:
        messages.error(request, "You must log in to view tasks.")
        return redirect('login')

    is_admin_user = _is_admin_user(request.user)
    user_memberships = DepartmentMember.objects.filter(
        user=request.user, is_active=True
    ).select_related('department').order_by('department__name')
    user_department_ids = list(user_memberships.values_list('department_id', flat=True))

    ticket_view = request.GET.get('view', '').strip().lower()
    is_created_view = (ticket_view == 'created')
    is_mine_only_filter = (
        request.GET.get('mine_only') in ['1', 'true', 'True', 'on']
        or request.GET.get('my_tasks') in ['1', 'true', 'True', 'on']
    )

    selected_department = None
    if not is_admin_user and user_department_ids and not is_created_view:
        if dept_id is not None:
            if dept_id not in user_department_ids:
                messages.error(request, "You do not have access to this department dashboard.")
                return redirect('base')
            selected_department = Department.objects.filter(id=dept_id).first()
    elif dept_id is not None and not is_created_view:
        selected_department = get_object_or_404(Department, id=dept_id)

    Taskdatas = TaskDetail.objects.all()
    if is_mine_only_filter:
        Taskdatas = Taskdatas.filter(TASK_CREATED=request.user)
    elif is_created_view and not is_admin_user:
        Taskdatas = Taskdatas.filter(TASK_CREATED=request.user)
    elif selected_department:
        Taskdatas = Taskdatas.filter(assigned_department=selected_department)
        if not is_admin_user:
            Taskdatas = Taskdatas.filter(
                ~Q(TASK_CREATED=request.user)
            )
    elif not is_admin_user:
        department_ids = DepartmentMember.objects.filter(
            user=request.user, is_active=True
        ).values_list('department_id', flat=True)
        Taskdatas = Taskdatas.filter(
            Q(assigned_department_id__in=department_ids) &
            ~Q(TASK_CREATED=request.user)
        ).distinct()

    if is_admin_user and not is_mine_only_filter:
        Taskdatas = Taskdatas.exclude(TASK_CREATED=request.user)

    visible_tasks = Taskdatas
    filter_form = TaskFilterForm(request.GET or None)
    if selected_department:
        filter_form.fields['department'].queryset = Department.objects.filter(id=selected_department.id)
        filter_form.fields['department'].initial = selected_department.id
    elif not is_admin_user:
        filter_form.fields['department'].queryset = Department.objects.filter(id__in=user_department_ids)

    if filter_form.is_valid():
        cd = filter_form.cleaned_data
        if cd.get('search'):
            Taskdatas = Taskdatas.filter(
                Q(TASK_TITLE__icontains=cd['search']) |
                Q(TASK_DESCRIPTION__icontains=cd['search'])
            )
        if cd.get('status'):
            Taskdatas = Taskdatas.filter(TASK_STATUS=cd['status'])
        if cd.get('priority'):
            Taskdatas = Taskdatas.filter(priority=cd['priority'])
        if cd.get('category'):
            Taskdatas = Taskdatas.filter(category=cd['category'])
        if cd.get('department'):
            Taskdatas = Taskdatas.filter(assigned_department=cd['department'])
        if cd.get('my_tasks') or is_mine_only_filter:
            Taskdatas = Taskdatas.filter(TASK_CREATED=request.user)

    paginator  = Paginator(Taskdatas.order_by('-TASK_CREATED_ON', '-id'), 20)
    page_obj   = paginator.get_page(request.GET.get('page'))

    if is_admin_user:
        task_ids = [task.id for task in page_obj.object_list]
        assignee_ids = {task.id: task.assigned_to_id for task in page_obj.object_list}
        preferred_rejections = {}
        fallback_rejections = {}
        if task_ids:
            rejected_histories = (
                TaskHistory.objects
                .filter(task_id__in=task_ids, action_type='REJECTED')
                .select_related('changed_by')
                .order_by('task_id', '-changed_at')
            )
            for history in rejected_histories:
                reason_text = (history.description or '').strip()
                if 'Reason:' in reason_text:
                    reason_text = reason_text.split('Reason:', 1)[1].strip()
                rejection_data = {
                    'reason': reason_text,
                    'rejected_by': history.changed_by.username if history.changed_by_id else 'Unknown',
                }
                current_assignee_id = assignee_ids.get(history.task_id)
                if current_assignee_id and history.changed_by_id == current_assignee_id:
                    if history.task_id not in fallback_rejections:
                        fallback_rejections[history.task_id] = rejection_data
                    continue
                if history.task_id not in preferred_rejections:
                    preferred_rejections[history.task_id] = rejection_data
        for task in page_obj.object_list:
            rejection_info = preferred_rejections.get(task.id) or fallback_rejections.get(task.id, {})
            task.latest_reject_reason = rejection_info.get('reason', '')
            task.latest_rejected_by = rejection_info.get('rejected_by', '')

    stats = {
        'total':       visible_tasks.count(),
        'open':        visible_tasks.filter(TASK_STATUS='Open').count(),
        'in_progress': visible_tasks.filter(TASK_STATUS='In Progress').count(),
        'closed':      visible_tasks.filter(TASK_STATUS='Closed').count(),
        'resolved':    visible_tasks.filter(TASK_STATUS='Resolved').count(),
        'my_tasks':    TaskDetail.objects.filter(TASK_CREATED=request.user).count(),
    }

    pagination_query = request.GET.copy()
    if 'page' in pagination_query:
        del pagination_query['page']

    department_dashboard_url = reverse('base')
    created_tickets_url = f"{reverse('base')}?view=created"

    return render(request, 'dashboard.html', {
        'Taskdatas':   page_obj,
        'taskdata':    page_obj,
        'filter_form': filter_form,
        'stats':       stats,
        'selected_department': selected_department,
        'is_created_view': is_created_view,
        'is_mine_only_filter': is_mine_only_filter,
        'is_admin_user': is_admin_user,
        'user_dashboard_departments': [m.department for m in user_memberships],
        'user_department_names': ", ".join([m.department.name for m in user_memberships]),
        'current_base_url': reverse('base_department', kwargs={'dept_id': selected_department.id}) if selected_department else reverse('base'),
        'department_dashboard_url': department_dashboard_url,
        'created_tickets_url': created_tickets_url,
        'pagination_query': pagination_query.urlencode(),
    })

@login_required
def TaskDetails(request):
    if request.method == "POST":
        form = TaskDetailForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save(commit=False)
            task.TASK_CREATED = request.user
            if task.assigned_department:
                task.assignment_type = 'MANUAL'
                task.assigned_by     = request.user
                task.assigned_at     = timezone.now()
            task.save()
            form.save_m2m()

            TaskHistory.objects.create(
                task=task, changed_by=request.user,
                action_type='CREATED',
                description=f'Task created by {request.user.username}',
            )
            log_activity(request.user, 'CREATED', f'Created ticket: {task.TASK_TITLE}', task=task)

            if task.assigned_department:
                notify_task_created(task)
                for member in DepartmentMember.objects.filter(
                    department=task.assigned_department, is_active=True
                ):
                    MyCart.objects.get_or_create(user=member.user, task=task)
                    Notification.objects.create(
                        user=member.user, task=task,
                        notification_type='TASK_CREATED',
                        message=f'New task "{task.TASK_TITLE}" in {task.assigned_department.name}',
                    )

            messages.success(request, 'Ticket created successfully!')
            return redirect(_get_dashboard_redirect_url(request.user))
    else:
        form = TaskDetailForm()
    return render(request, 'TaskDetail.html', {'form': form})


@login_required
def TaskInfo(request, pk):
    taskinfos = get_object_or_404(TaskDetail, id=pk)
    if not _can_view_task(request.user, taskinfos):
        is_same_department_user = (
            taskinfos.assigned_department_id
            and DepartmentMember.objects.filter(
                user=request.user,
                department=taskinfos.assigned_department,
                is_active=True,
            ).exists()
        )
        if (
            is_same_department_user
            and taskinfos.assigned_to_id
            and taskinfos.TASK_CREATED_id != request.user.id
            and taskinfos.assigned_to_id != request.user.id
        ):
            messages.error(request, "You have not permission to see this ticket.")
        else:
            messages.error(request, "You do not have permission to view this ticket.")
        return redirect('base')

    is_admin         = _is_admin_user(request.user)

    is_department_member = False
    is_senior_dept_member = False
    if taskinfos.assigned_department:
        is_department_member = DepartmentMember.objects.filter(
            user=request.user, department=taskinfos.assigned_department, is_active=True
        ).exists()
        is_senior_dept_member = DepartmentMember.objects.filter(
            user=request.user, department=taskinfos.assigned_department,
            role__in=['LEAD', 'MANAGER', 'HEAD'], is_active=True
        ).exists()

    is_agent  = is_admin or is_senior_dept_member
    _sync_mycart_for_user(request.user)
    can_work_on_task = _can_work_on_task(request.user, taskinfos)
    can_edit_task = (
        taskinfos.TASK_STATUS == 'Open'
        and (taskinfos.TASK_CREATED_id == request.user.id or is_admin)
    )
    can_reject = (
        MyCart.objects.filter(user=request.user, task=taskinfos).exists()
        and not _is_non_rejectable_assignment(request.user, taskinfos)
    )
    comments_qs = UserComment.objects.filter(task=taskinfos)
    if not is_admin:
        participant_ids = [taskinfos.TASK_CREATED_id]
        if taskinfos.assigned_to_id:
            participant_ids.append(taskinfos.assigned_to_id)
        comments_qs = comments_qs.filter(user_id__in=participant_ids)
    comments = comments_qs

    notification_id = request.GET.get('mark_read')
    if notification_id:
        try:
            Notification.objects.get(id=notification_id, user=request.user).mark_as_read()
        except Notification.DoesNotExist:
            pass

    creator_edit_only_mode = (
        request.GET.get('mine_only') in ['1', 'true', 'True', 'on']
        and taskinfos.TASK_CREATED_id == request.user.id
    )
    can_creator_decide_closed = (
        taskinfos.TASK_STATUS == 'Closed'
        and (taskinfos.TASK_CREATED_id == request.user.id or is_admin)
    )
    can_reopen_ticket = is_admin or not TaskHistory.objects.filter(
        task=taskinfos,
        action_type='REOPENED',
        changed_by=request.user,
    ).exists()
    can_rate_resolved_task = (
        taskinfos.TASK_CREATED_id == request.user.id
        and taskinfos.TASK_STATUS == 'Resolved'
        and not _is_admin_user(request.user)
        and not hasattr(taskinfos, 'rating')
    )
    normalized_description = " ".join((taskinfos.TASK_DESCRIPTION or "").split())
    can_view_admin_note_thread = bool(
        is_admin
        or taskinfos.assigned_to_id == request.user.id
        or is_department_member
    )
    overdue_note_thread = TaskHistory.objects.none()
    if can_view_admin_note_thread:
        overdue_note_thread = (
            TaskHistory.objects
            .filter(
                task=taskinfos,
                field_name__in=['admin_overdue_note', 'admin_overdue_note_reply'],
            )
            .select_related('changed_by')
            .order_by('changed_at')
        )
    can_reply_admin_overdue_note = (
        can_view_admin_note_thread
        and not is_admin
        and taskinfos.TASK_STATUS not in ['Closed', 'Resolved', 'Expired']
    )
    latest_rejection = (
        TaskHistory.objects
        .filter(task=taskinfos, action_type='REJECTED')
        .exclude(changed_by=taskinfos.assigned_to)
        .select_related('changed_by')
        .order_by('-changed_at')
        .first()
    )
    if not latest_rejection:
        latest_rejection = (
            TaskHistory.objects
            .filter(task=taskinfos, action_type='REJECTED')
            .select_related('changed_by')
            .order_by('-changed_at')
            .first()
        )
    latest_rejection_reason = ''
    latest_rejection_by = ''
    if latest_rejection:
        reason_text = (latest_rejection.description or '').strip()
        if 'Reason:' in reason_text:
            reason_text = reason_text.split('Reason:', 1)[1].strip()
        latest_rejection_reason = reason_text
        latest_rejection_by = latest_rejection.changed_by.username if latest_rejection.changed_by_id else ''

    return render(request, 'TaskInfo.html', {
        'taskinfos':            taskinfos,
        'normalized_description': normalized_description,
        'comments':             comments,
        'can_work_on_task':     can_work_on_task,
        'can_edit_task':        can_edit_task,
        'can_reject':           can_reject,
        'creator_edit_only_mode': creator_edit_only_mode,
        'can_creator_decide_closed': can_creator_decide_closed,
        'can_reopen_ticket': can_reopen_ticket,
        'can_rate_resolved_task': can_rate_resolved_task,
        'is_department_member': is_department_member,
        'is_agent':             is_agent,
        'is_admin':             is_admin,
        'latest_rejection_reason': latest_rejection_reason,
        'latest_rejection_by': latest_rejection_by,
        'can_view_admin_note_thread': can_view_admin_note_thread,
        'overdue_note_thread': overdue_note_thread,
        'can_reply_admin_overdue_note': can_reply_admin_overdue_note,
    })


@login_required
def updatetask(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    is_admin_user = _is_admin_user(request.user)
    can_edit_task = (
        task.TASK_STATUS == 'Open'
        and (task.TASK_CREATED_id == request.user.id or is_admin_user)
    )
    if not can_edit_task:
        messages.error(request, 'Only the ticket creator or admin can edit an open ticket.')
        return redirect('taskinfo', pk=pk)

    if not is_admin_user and not _can_work_on_task(request.user, task):
        messages.error(request, 'You do not have permission to edit this task.')
        return redirect('taskinfo', pk=pk)

    is_creator_edit = task.TASK_CREATED_id == request.user.id and not is_admin_user
    if is_creator_edit:
        old_department = task.assigned_department
        form = TaskDetailForm(request.POST or None, request.FILES or None, instance=task)
        if request.method == "POST" and form.is_valid():
            changed_fields = form.changed_data
            updated_task = form.save(commit=False)
            updated_task.TASK_CREATED = task.TASK_CREATED
            if updated_task.TASK_DESCRIPTION:
                updated_task.TASK_DESCRIPTION = " ".join(updated_task.TASK_DESCRIPTION.split())

            if 'assigned_department' in changed_fields and updated_task.assigned_department:
                updated_task.assignment_type = 'MANUAL'
                updated_task.assigned_by = request.user
                updated_task.assigned_at = timezone.now()
                new_members = DepartmentMember.objects.filter(
                    department=updated_task.assigned_department, is_active=True
                )
                for member in new_members:
                    MyCart.objects.get_or_create(user=member.user, task=updated_task)
                    Notification.objects.create(
                        user=member.user, task=updated_task,
                        notification_type='TASK_ASSIGNED',
                        message=f'Task "{updated_task.TASK_TITLE}" reassigned to {updated_task.assigned_department.name}',
                    )

            updated_task.save()
            form.save_m2m()

            if 'assigned_department' in changed_fields and old_department and old_department != updated_task.assigned_department:
                old_member_ids = DepartmentMember.objects.filter(
                    department=old_department, is_active=True
                ).values_list('user_id', flat=True)
                if updated_task.assigned_department:
                    new_member_ids = DepartmentMember.objects.filter(
                        department=updated_task.assigned_department, is_active=True
                    ).values_list('user_id', flat=True)
                    MyCart.objects.filter(
                        task=updated_task, user_id__in=old_member_ids
                    ).exclude(user_id__in=new_member_ids).delete()
                else:
                    MyCart.objects.filter(task=updated_task, user_id__in=old_member_ids).delete()

            for field in changed_fields:
                action_type = 'PRIORITY_CHANGED' if field == 'priority' else 'UPDATED'
                TaskHistory.objects.create(
                    task=updated_task, changed_by=request.user,
                    action_type=action_type, field_name=field,
                    old_value=str(form.initial.get(field, '')),
                    new_value=str(form.cleaned_data.get(field, '')),
                    description=f'{field} changed by {request.user.username}',
                )

            notify_task_updated(updated_task, request.user, changes=changed_fields)
            log_activity(request.user, 'UPDATED', f'Updated ticket: {updated_task.TASK_TITLE}', task=updated_task)
            messages.success(request, 'Ticket updated successfully!')
            if request.GET.get('mine_only') in ['1', 'true', 'True', 'on']:
                return redirect(f"{reverse('taskinfo', kwargs={'pk': pk})}?mine_only=1")
            return redirect('taskinfo', pk=pk)

        return render(request, 'TaskDetail.html', {
            'form': form,
            'task': task,
            'edit_mode': True,
            'mine_only_mode': request.GET.get('mine_only') in ['1', 'true', 'True', 'on'],
        })

    if request.method == "POST":
        old_department = task.assigned_department
        form = TaskUpdateForm(request.POST, instance=task)
        if form.is_valid():
            changed_fields = form.changed_data
            updated_task   = form.save(commit=False)
            if updated_task.TASK_DESCRIPTION:
                updated_task.TASK_DESCRIPTION = " ".join(updated_task.TASK_DESCRIPTION.split())

            if 'assigned_department' in changed_fields and updated_task.assigned_department:
                updated_task.assignment_type = 'MANUAL'
                updated_task.assigned_by     = request.user
                updated_task.assigned_at     = timezone.now()
                new_members = DepartmentMember.objects.filter(
                    department=updated_task.assigned_department, is_active=True
                )
                for member in new_members:
                    MyCart.objects.get_or_create(user=member.user, task=updated_task)
                    Notification.objects.create(
                        user=member.user, task=updated_task,
                        notification_type='TASK_ASSIGNED',
                        message=f'Task "{updated_task.TASK_TITLE}" reassigned to {updated_task.assigned_department.name}',
                    )
            if 'assigned_to' in changed_fields and updated_task.assigned_to:
                updated_task.assignment_type = 'MANUAL'
                updated_task.assigned_by = request.user
                updated_task.assigned_at = timezone.now()

            updated_task.save()
            form.save_m2m()

            if 'assigned_to' in changed_fields and updated_task.assigned_to:
                MyCart.objects.get_or_create(user=updated_task.assigned_to, task=updated_task)
                MyCart.objects.filter(task=updated_task).exclude(user=updated_task.assigned_to).delete()

            if 'assigned_department' in changed_fields:
                if old_department and old_department != updated_task.assigned_department:
                    old_member_ids = DepartmentMember.objects.filter(
                        department=old_department, is_active=True
                    ).values_list('user_id', flat=True)
                    if updated_task.assigned_department:
                        new_member_ids = DepartmentMember.objects.filter(
                            department=updated_task.assigned_department, is_active=True
                        ).values_list('user_id', flat=True)
                        MyCart.objects.filter(
                            task=updated_task, user_id__in=old_member_ids
                        ).exclude(user_id__in=new_member_ids).delete()
                    else:
                        MyCart.objects.filter(task=updated_task, user_id__in=old_member_ids).delete()

            for field in changed_fields:
                action_type = 'STATUS_CHANGED' if field == 'TASK_STATUS' else \
                              'PRIORITY_CHANGED' if field == 'priority' else 'UPDATED'
                TaskHistory.objects.create(
                    task=updated_task, changed_by=request.user,
                    action_type=action_type, field_name=field,
                    old_value=str(form.initial.get(field, '')),
                    new_value=str(form.cleaned_data.get(field, '')),
                    description=f'{field} changed by {request.user.username}',
                )

            notify_task_updated(task, request.user, changes=changed_fields)
            log_activity(request.user, 'UPDATED', f'Updated ticket: {updated_task.TASK_TITLE}', task=updated_task)
            messages.success(request, 'Task updated successfully!')
            return redirect('taskinfo', pk=pk)
    else:
        form = TaskUpdateForm(instance=task)
    return render(request, 'Updatetask.html', {'form': form, 'task': task})


@login_required
def deletetask(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    if task.TASK_CREATED != request.user and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to delete this task.')
        return redirect('base')

    TaskHistory.objects.create(
        task=task,
        changed_by=request.user,
        action_type='DELETED',
        description=f'Task deleted by {request.user.username}',
    )

    log_activity(
        request.user,
        'DELETED',
        f'Deleted ticket: {task.TASK_TITLE}'
    )

    task.delete()
    messages.success(request, 'Task deleted successfully!')
    return redirect(_get_dashboard_redirect_url(request.user))


@admin_required
def bulk_delete_tickets(request):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('base')

    raw_ids = request.POST.get('ticket_ids', '')
    ticket_ids = []
    for value in raw_ids.split(','):
        value = value.strip()
        if value.isdigit():
            ticket_ids.append(int(value))

    if not ticket_ids:
        messages.error(request, 'No tickets selected for deletion.')
        next_url = request.POST.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect('base')

    tasks = list(TaskDetail.objects.filter(id__in=ticket_ids))
    if not tasks:
        messages.error(request, 'Selected tickets were not found.')
        next_url = request.POST.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect('base')

    for task in tasks:
        TaskHistory.objects.create(
            task=task,
            changed_by=request.user,
            action_type='DELETED',
            description=f'Task deleted by {request.user.username} (bulk delete)',
        )
        log_activity(
            request.user,
            'DELETED',
            f'Deleted ticket: {task.TASK_TITLE}'
        )

    TaskDetail.objects.filter(id__in=[t.id for t in tasks]).delete()
    messages.success(request, f'Deleted {len(tasks)} ticket(s) successfully.')

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect('base')

@login_required
def RemoveTask(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    if not _can_view_task(request.user, task):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('taskinfo', pk=pk)
    if _is_non_rejectable_assignment(request.user, task):
        messages.error(request, "This assignment cannot be rejected.")
        return redirect('taskinfo', pk=pk)
    if not MyCart.objects.filter(task=task, user=request.user).exists() and task.assigned_to_id != request.user.id:
        messages.error(request, "Only the current assignee can reject this ticket.")
        return redirect('taskinfo', pk=pk)

    if request.method != 'POST':
        return render(request, 'reject_ticket.html', {'task': task})

    rejected = MyCart.objects.filter(task=task, user=request.user).exists()
    reason = request.POST.get('reject_reason', '').strip()
    if not reason:
        messages.error(request, "Rejection reason is required.")
        return redirect('taskinfo', pk=pk)
    MyCart.objects.filter(task=task, user=request.user).delete()

    auto_assignee = None
    if task.assigned_to_id == request.user.id:
        old_status = task.TASK_STATUS
        task.assigned_to = None
        task.TASK_HOLDER = ''
        if task.TASK_STATUS in ['In Progress', 'Reopen']:
            task.TASK_STATUS = 'Open'
        task.save(update_fields=['assigned_to', 'TASK_HOLDER', 'TASK_STATUS'])
        TaskHistory.objects.create(
            task=task,
            changed_by=request.user,
            action_type='STATUS_CHANGED',
            old_value=old_status,
            new_value=task.TASK_STATUS,
            description=f'Task released by {request.user.username}'
                        + (f'. Reason: {reason}' if reason else ''),
        )
        TaskHistory.objects.create(
            task=task,
            changed_by=request.user,
            action_type='REJECTED',
            description=f'Task rejected by {request.user.username}'
                        + (f'. Reason: {reason}' if reason else ''),
        )
        auto_assignee = _auto_assign_on_department_rejection(task, request.user)
    elif rejected:
        TaskHistory.objects.create(
            task=task,
            changed_by=request.user,
            action_type='REJECTED',
            description=f'Task rejected from queue by {request.user.username}'
                        + (f'. Reason: {reason}' if reason else ''),
        )
        auto_assignee = _auto_assign_on_department_rejection(task, request.user)
    if auto_assignee:
        messages.success(
            request,
            f"Ticket rejected and auto-assigned to {auto_assignee.get_full_name() or auto_assignee.username}."
        )
    else:
        messages.success(request, "Ticket rejected and removed from your queue.")
    return redirect('mycart')

@login_required
def CloseTask(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    if TaskHistory.objects.filter(
        task=task,
        action_type='REJECTED',
        changed_by=request.user,
    ).exists():
        messages.error(request, "You have already rejected this ticket and cannot close it now.")
        return redirect('taskinfo', pk=pk)
    if _is_admin_user(request.user):
        messages.error(request, "Admins cannot close tasks. You can delete the task if needed.")
        return redirect('taskinfo', pk=pk)
    if not _can_work_on_task(request.user, task):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('taskinfo', pk=pk)
    if not MyCart.objects.filter(task=task, user=request.user).exists() and task.assigned_to_id != request.user.id:
        messages.error(request, "Only the assigned department handler can close this ticket.")
        return redirect('taskinfo', pk=pk)
    task.assigned_to = request.user
    task.TASK_STATUS   = 'Closed'
    task.TASK_CLOSED   = request.user
    task.TASK_CLOSED_ON = timezone.now()
    task.save()
    TaskHistory.objects.create(
        task=task, changed_by=request.user,
        action_type='CLOSED',
        description=f'Task closed by {request.user.username}',
        old_value='In Progress', new_value='Closed',
    )
    log_activity(request.user, 'CLOSED', f'Closed ticket: {task.TASK_TITLE}', task=task)
    notify_task_closed(task, request.user)
    if task.assigned_department_id:
        dept_member_ids = DepartmentMember.objects.filter(
            department=task.assigned_department,
            is_active=True
        ).values_list('user_id', flat=True)
        MyCart.objects.filter(task=task, user_id__in=dept_member_ids).delete()
    else:
        MyCart.objects.filter(task=task).delete()
    messages.success(request, "Task closed successfully.")
    return redirect(_get_dashboard_redirect_url(request.user))

@login_required
def reopentask(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    is_admin = _is_admin_user(request.user)
    if (
        not is_admin
        and TaskHistory.objects.filter(
            task=task,
            action_type='REOPENED',
            changed_by=request.user,
        ).exists()
    ):
        messages.error(request, "You can reopen a ticket only once. Please create a new ticket.")
        return redirect('taskinfo', pk=pk)
    if task.TASK_CREATED_id != request.user.id and not is_admin:
        messages.error(request, "Only the ticket creator can reopen this ticket.")
        return redirect('taskinfo', pk=pk)
    if not is_admin and not _can_work_on_task(request.user, task):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('taskinfo', pk=pk)
    holder = task.TASK_CLOSED

    if not holder:
        messages.error(request, "Cannot reopen: no closer recorded.")
        return redirect('base')

    old_status = task.TASK_STATUS
    task.TASK_STATUS = 'Reopen'
    task.TASK_CLOSED_ON = None
    task.resolved_at = None
    task.assigned_to = holder
    task.TASK_HOLDER = holder.username
    task.save(update_fields=[
        'TASK_STATUS',
        'TASK_CLOSED_ON',
        'resolved_at',
        'assigned_to',
        'TASK_HOLDER',
    ])

    MyCart.objects.get_or_create(user=holder, task=task)

    TaskHistory.objects.create(
        task=task,
        changed_by=request.user,
        action_type='REOPENED',
        description=f'Task reopened by {request.user.username}',
        old_value=old_status,
        new_value='Reopen',
    )

    log_activity(
        request.user,
        'REOPENED',
        f'Reopened ticket: {task.TASK_TITLE}',
        task=task
    )

    notify_task_reopened(task, request.user)

    messages.success(request, "Task reopened successfully.")
    return redirect(_get_dashboard_redirect_url(request.user))

@login_required
def resolvedtask(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    is_admin = _is_admin_user(request.user)
    if task.TASK_STATUS == 'Closed' and task.TASK_CREATED_id != request.user.id and not is_admin:
        messages.error(request, "Only the ticket creator can resolve a closed ticket.")
        return redirect('taskinfo', pk=pk)
    if not is_admin and not _can_work_on_task(request.user, task):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('taskinfo', pk=pk)
    old_status = task.TASK_STATUS

    task.TASK_STATUS = 'Resolved'
    task.resolved_at = timezone.now()
    task.save()

    notify_task_resolved(task, request.user)

    TaskHistory.objects.create(
        task=task,
        changed_by=request.user,
        action_type='STATUS_CHANGED',
        description=f'Task resolved by {request.user.username}',
        old_value=old_status,
        new_value='Resolved',
    )

    log_activity(
        request.user,
        'RESOLVED',
        f'Resolved ticket: {task.TASK_TITLE}',
        task=task
    )

    messages.success(request, "Task resolved successfully.")
    return redirect('taskinfo', pk=pk)

def LoginView(request):
    if request.user.is_authenticated:
        return redirect(_get_dashboard_redirect_url(request.user))

    role = LoginRoleAuthorization.normalize_mode(request.GET.get('role'))

    if request.method == "POST":
        role = LoginRoleAuthorization.normalize_mode(request.POST.get('login_as', role))
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user:
                _ensure_userprofile_and_permissions(user)

                                                                                
                access_error = LoginRoleAuthorization.account_access_error(role, user)
                if access_error:
                    messages.error(request, access_error)
                    return render(request, 'Login.html', {
                        'form': form,
                        'role': role,
                        'allow_register': LoginRoleAuthorization.can_register(role),
                    })

                login(request, user)
                if not form.cleaned_data.get('remember_me'):
                    request.session.set_expiry(0)

                if role == LoginRoleAuthorization.ADMIN:
                    messages.success(request, f"Welcome, {user.username}! You are logged in as Admin.")
                else:
                    messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")

                                                                              
                return redirect(LoginRoleAuthorization.success_redirect(
                    role, user, _get_dashboard_redirect_url
                ))
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm(initial={'login_as': role})

    return render(request, 'Login.html', {
        'form': form,
        'role': role,
        'allow_register': LoginRoleAuthorization.can_register(role),
    })


def LogoutView(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('landing')


def RegisterView(request):
    if request.method == "POST":
        register_form = RegisterForm(request.POST)
        profile_form  = UserProfileForm(request.POST, request.FILES)
        if register_form.is_valid() and profile_form.is_valid():
            user         = register_form.save()
            profile      = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            messages.success(request, "Registered successfully! Please sign in.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        register_form = RegisterForm()
        profile_form  = UserProfileForm()
    return render(request, 'Register.html', {
        'Register_form': register_form,
        'UserProfile_form': profile_form,
    })


def Change_Password(request):
    if request.method == 'POST':
        fm = PasswordChangeForm(user=request.user, data=request.POST)
        if fm.is_valid():
            fm.save()
            update_session_auth_hash(request, fm.user)
            log_activity(request.user, 'UPDATED', 'Changed account password')
            messages.success(request, 'Password changed successfully.')
            return redirect('login')
    else:
        fm = PasswordChangeForm(user=request.user)
    return render(request, 'Change_Password.html', {'fm': fm})

def User_Profile(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must log in to view your profile.")
        return redirect('login')
    user = request.user
    profile_data = UserProfile.objects.filter(user=user)
    resolved_count = TaskDetail.objects.filter(
        assigned_to=user, TASK_STATUS__in=['Closed', 'Resolved']
    ).count()
    avg_rating = TaskRating.objects.filter(
        task__assigned_to=user
    ).aggregate(avg=Avg('rating'))['avg']
    return render(request, 'Userprofile.html', {
        'ProfileDatas':    profile_data,
        'resolved_count':  resolved_count,
        'avg_rating':      round(avg_rating, 1) if avg_rating else None,
    })


def update_profile(request, pk):
    if not request.user.is_authenticated:
        messages.error(request, "You must log in.")
        return redirect('login')
    profile = get_object_or_404(UserProfile, id=pk)
    form = UserProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('profile')
    return render(request, 'Update_Profile.html', {'form': form})

@login_required
def MyCarts(request):
    _sync_mycart_for_user(request.user)
    user_memberships = DepartmentMember.objects.filter(
        user=request.user, is_active=True
    ).select_related('department').order_by('department__name')
    user_department_ids = list(user_memberships.values_list('department_id', flat=True))

    carts = MyCart.objects.filter(user=request.user).select_related(
        'task', 'task__TASK_CREATED', 'task__assigned_department', 'task__category'
    ).order_by('-accepted_at')

    department_filter = request.GET.get('department', '').strip()
    if department_filter:
        try:
            dept_id = int(department_filter)
        except (TypeError, ValueError):
            dept_id = None
        if dept_id and dept_id in user_department_ids:
            carts = carts.filter(task__assigned_department_id=dept_id)

    sort = request.GET.get('sort', 'all')
    today = timezone.localdate()
    if sort == 'urgent':
        carts = carts.filter(task__priority='URGENT')
    elif sort == 'overdue':
        carts = carts.filter(task__TASK_DUE_DATE__lt=today).exclude(
            task__TASK_STATUS__in=['Closed', 'Resolved', 'Expired']
        )

    comments = UserComment.objects.filter(user=request.user)
    cart_task_ids = list(carts.values_list('task_id', flat=True))
    non_rejectable_task_ids = set()
    reopened_task_ids = set(
        carts.filter(task__TASK_STATUS='Reopen').values_list('task_id', flat=True)
    )
    non_rejectable_task_ids.update(reopened_task_ids)
    admin_assigned_task_ids = set(
        carts.filter(task__assigned_by__is_superuser=True).values_list('task_id', flat=True)
    )
    non_rejectable_task_ids.update(admin_assigned_task_ids)
    if cart_task_ids:
        latest_assigned_history = (
            TaskHistory.objects.filter(
                task_id__in=cart_task_ids,
                action_type='ASSIGNED',
            )
            .order_by('task_id', '-changed_at')
        )
        latest_reopened_history = (
            TaskHistory.objects.filter(
                task_id__in=cart_task_ids,
                action_type='REOPENED',
            )
            .order_by('task_id', '-changed_at')
        )

        latest_assigned_by_task = {}
        for row in latest_assigned_history:
            if row.task_id not in latest_assigned_by_task:
                latest_assigned_by_task[row.task_id] = row

        latest_reopened_by_task = {}
        for row in latest_reopened_history:
            if row.task_id not in latest_reopened_by_task:
                latest_reopened_by_task[row.task_id] = row

        for task_id, assigned_row in latest_assigned_by_task.items():
            reopened_row = latest_reopened_by_task.get(task_id)
            was_reopened_after_assignment = (
                reopened_row is not None and reopened_row.changed_at > assigned_row.changed_at
            )
            if (
                assigned_row.new_value == request.user.username
                and assigned_row.description
                and 'Auto-assigned to' in assigned_row.description
                and not was_reopened_after_assignment
            ):
                non_rejectable_task_ids.add(task_id)

    stats = {
        'assigned': carts.count(),
        'in_progress': carts.filter(task__TASK_STATUS='In Progress').count(),
        'overdue': carts.filter(task__TASK_DUE_DATE__lt=today).exclude(
            task__TASK_STATUS__in=['Closed', 'Resolved', 'Expired']
        ).count(),
    }
    return render(request, 'Mycart.html', {
        'Carts': carts,
        'comments': comments,
        'stats': stats,
        'sort': sort,
        'user_departments': [m.department for m in user_memberships],
        'selected_department_filter': department_filter,
        'non_rejectable_task_ids': non_rejectable_task_ids,
    })

@login_required
def activity_log(request):
    logs = ActivityLog.objects.filter(user=request.user).select_related('task')

    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = logs.filter(action=action_filter)

    search = request.GET.get('search', '').strip()
    if search:
        logs = logs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(task__TASK_TITLE__icontains=search)
        )

    paginator = Paginator(logs, 25)
    page_obj  = paginator.get_page(request.GET.get('page'))

    stats = {
        'total':    ActivityLog.objects.filter(user=request.user).count(),
        'resolved': ActivityLog.objects.filter(user=request.user, action='RESOLVED').count(),
        'comments': ActivityLog.objects.filter(user=request.user, action='COMMENTED').count(),
    }

    return render(request, 'activity_log.html', {
        'activities':    page_obj,
        'stats':         stats,
        'action_filter': action_filter,
        'search':        search,
    })

@login_required
def resolved_history(request):
    resolved = TaskDetail.objects.filter(
        TASK_STATUS='Resolved',
    )

    q = request.GET.get('q', '').strip()
    if q:
        resolved = resolved.filter(
            Q(TASK_TITLE__icontains=q) | Q(TASK_DESCRIPTION__icontains=q)
        )

    resolved = resolved.select_related(
        'category', 'assigned_to', 'TASK_CREATED', 'assigned_department'
    ).order_by('-TASK_CLOSED_ON')

    full_qs = TaskDetail.objects.filter(TASK_STATUS='Resolved')
    stats = {
        'total_resolved': full_qs.count(),
        'resolved':       full_qs.filter(TASK_STATUS='Resolved').count(),
        'avg_rating':     TaskRating.objects.filter(
            task__in=full_qs
        ).aggregate(avg=Avg('rating'))['avg'],
    }

    paginator = Paginator(resolved, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'resolved_history.html', {
        'resolved_tasks': page_obj,
        'stats':          stats,
    })

@admin_required
def account_settings(request):
    form = AccountSettingsForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        target_user = form.cleaned_data['target_user']
        action      = form.cleaned_data['action']

        if action == 'department':
            dept = form.cleaned_data.get('department')
            if dept:
                DepartmentMember.objects.get_or_create(
                    user=target_user, department=dept,
                    defaults={'role': 'MEMBER', 'added_by': request.user}
                )
                log_activity(
                    request.user, 'UPDATED',
                    f'Added {target_user.username} to {dept.name}',
                )
                messages.success(request, f'{target_user.username} added to {dept.name}.')

        elif action == 'toggle_status':
            target_user.is_active = not target_user.is_active
            target_user.save()
            status = 'activated' if target_user.is_active else 'deactivated'
            log_activity(
                request.user, 'UPDATED',
                f'Account {status}: {target_user.username}',
            )
            messages.success(request, f'{target_user.username} account {status}.')

        return redirect('account_settings')

    stats = {
        'total_users':    User.objects.count(),
        'superusers':     User.objects.filter(is_superuser=True).count(),
        'departments':    Department.objects.filter(is_active=True).count(),
    }

    return render(request, 'account_settings.html', {
        'form':  form,
        'stats': stats,
        'total_users': stats['total_users'],
        'superusers': stats['superusers'],
        'dept_count': stats['departments'],
    })

@admin_required
def dashboard_pie(request):
    statuses = ['Open', 'In Progress', 'Reopen', 'Resolved', 'Closed', 'Expired']
    counts = [TaskDetail.objects.filter(TASK_STATUS=s).count() for s in statuses]
    colors = ['#3B82F6', '#F59E0B', '#F97316', '#10B981', '#64748B', '#EF4444']
    total = sum(counts)

    fig, ax = plt.subplots(figsize=(12.5, 7.4), dpi=140)
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#F8FAFC')

    if total == 0:
        ax.text(0.5, 0.5, 'No task data available', ha='center', va='center',
                fontsize=13, color='#64748B', fontweight='semibold')
        ax.axis('off')
    else:
        wedges, _texts = ax.pie(
            counts,
            colors=colors,
            startangle=135,
            radius=1.18,
            labels=None,
            wedgeprops={
                'linewidth': 2.0,
                'edgecolor': 'white',
                'width': 0.52,                                                   
            },
        )
        ax.legend(
            wedges,
            [f'{s} ({c})' for s, c in zip(statuses, counts)],
            title='Ticket Status',
            loc='upper center',
            bbox_to_anchor=(0.5, -0.05),
            ncol=3,
            frameon=False,
            fontsize=11,
            title_fontsize=12,
        )
        ax.axis('equal')
    ax.set_title('Task Status Distribution', fontsize=17, color='#0F172A', pad=12, weight='bold')

    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format='png', bbox_inches='tight', transparent=False)
    plt.close(fig)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='image/png')


@admin_required
def pie_chart(request):
    return render(request, 'task_status_pie.html')


@admin_required
def Bar_chart(request):
    statuses = ['Open', 'In Progress', 'Reopen', 'Resolved', 'Closed', 'Expired']
    counts = [TaskDetail.objects.filter(TASK_STATUS=s).count() for s in statuses]
    colors = ['#3B82F6', '#F59E0B', '#F97316', '#10B981', '#64748B', '#EF4444']

    fig, ax = plt.subplots(figsize=(13.2, 7.6), dpi=140)
    fig.patch.set_facecolor('#F8FAFC')
    ax.set_facecolor('#F8FAFC')

    bars = ax.bar(statuses, counts, color=colors, edgecolor='white', linewidth=1.0)
    ax.set_title('Task Status Count', fontsize=17, color='#0F172A', pad=12, weight='bold')
    ax.set_ylabel('Tickets', color='#334155', fontsize=12, fontweight='bold')
    ax.tick_params(axis='x', rotation=0, labelsize=11.5, colors='#334155')
    ax.tick_params(axis='y', labelsize=11, colors='#475569')
    ax.grid(axis='y', color='#E2E8F0', linewidth=1.0, alpha=0.95)
    ax.set_axisbelow(True)
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['left'].set_color('#CBD5E1')
    ax.spines['bottom'].set_color('#CBD5E1')

    for bar, value in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(0.1, max(counts + [1]) * 0.015),
            str(value),
            ha='center',
            va='bottom',
            fontsize=11,
            color='#0F172A',
            fontweight='bold'
        )

    if sum(counts) == 0:
        ax.text(0.5, 0.5, 'No task data available', transform=ax.transAxes,
                ha='center', va='center', fontsize=12, color='#64748B', fontweight='semibold')

    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format='png', bbox_inches='tight', transparent=False)
    plt.close(fig)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='image/png')

@login_required
def comment_view(request, pk, action):
    task   = get_object_or_404(TaskDetail, id=pk)
    action = action.lower()
    if action not in ['closing_comment', 'reopen_comment']:
        messages.error(request, "Only close note and reopen reason are allowed.")
        return redirect('taskinfo', pk=pk)
    is_admin = _is_admin_user(request.user)
    if is_admin and action == 'closing_comment':
        messages.error(request, "Admins cannot perform close flow. You can delete the task if needed.")
        return redirect('taskinfo', pk=pk)
    if action == 'reopen_comment' and not (is_admin or task.TASK_CREATED_id == request.user.id):
        messages.error(request, "Only the ticket creator or admin can add reopen comment.")
        return redirect('taskinfo', pk=pk)
    if (
        action == 'closing_comment'
        and TaskHistory.objects.filter(
            task=task,
            action_type='REJECTED',
            changed_by=request.user,
        ).exists()
    ):
        messages.error(request, "You have already rejected this ticket and cannot close it now.")
        return redirect('taskinfo', pk=pk)
    if (
        action == 'reopen_comment'
        and not is_admin
        and TaskHistory.objects.filter(
            task=task,
            action_type='REOPENED',
            changed_by=request.user,
        ).exists()
    ):
        messages.error(request, "You can reopen a ticket only once. Please create a new ticket.")
        return redirect('taskinfo', pk=pk)
    if not is_admin and not _can_work_on_task(request.user, task):
        messages.error(request, "You do not have permission to comment on this ticket.")
        return redirect('taskinfo', pk=pk)

    is_dept_member = is_senior_dept_member = False
    if task.assigned_department:
        is_dept_member = DepartmentMember.objects.filter(
            user=request.user, department=task.assigned_department, is_active=True
        ).exists()
        is_senior_dept_member = DepartmentMember.objects.filter(
            user=request.user, department=task.assigned_department,
            role__in=['LEAD', 'MANAGER', 'HEAD'], is_active=True
        ).exists()

    is_agent = is_admin or is_senior_dept_member

    if request.method == 'POST':
        form = UserCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment          = form.save(commit=False)
            comment.task     = task
            comment.user     = request.user
            comment.save()

            canned_id = request.POST.get('canned_response_id')
            if canned_id:
                try:
                    CannedResponse.objects.get(id=canned_id).increment_usage()
                except CannedResponse.DoesNotExist:
                    pass

            TaskHistory.objects.create(
                task=task, changed_by=request.user,
                action_type='COMMENTED',
                description=f'Comment added by {request.user.username}',
            )
            log_activity(
                request.user, 'COMMENTED',
                f'Commented on ticket: {task.TASK_TITLE}', task=task,
            )

            notify_task_commented(
                task, request.user,
                comment.Closing_comment or comment.Reopen_comment or ''
            )

            if action == 'closing_comment':
                return CloseTask(request, pk)
            elif action == 'reopen_comment':
                return reopentask(request, pk)
    else:
        form = UserCommentForm()
        if action == 'closing_comment':
            form.fields['Reopen_comment'].widget = forms.HiddenInput()
        elif action == 'reopen_comment':
            form.fields['Closing_comment'].widget = forms.HiddenInput()

    canned_responses = []
    if is_agent:
        canned_responses = CannedResponse.objects.filter(is_active=True).filter(
            Q(is_public=True) | Q(department=task.assigned_department)
        )

    return render(request, 'Comment.html', {
        'form':             form,
        'task':             task,
        'action':           action,
        'is_admin':         is_admin,
        'is_agent':         is_agent,
        'canned_responses': canned_responses,
    })


@login_required
def download_file(request, pk):
    text_file = get_object_or_404(UserComment, id=pk)
    if not _can_view_task(request.user, text_file.task):
        messages.error(request, "You do not have permission to access this attachment.")
        return redirect('base')
    response  = FileResponse(open(text_file.TextFile.path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{text_file.TextFile.name}"'
    return response

@admin_required
def category_list(request):
    categories = Category.objects.all()
    for cat in categories:
        cat.keywords_list = [k.strip() for k in cat.ml_keywords.split(',')] if cat.ml_keywords else []
    return render(request, 'admin/category_list.html', {'categories': categories})


@admin_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        return redirect('category_list')
    return render(request, 'admin/category_form.html', {'form': form})


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(Category, id=pk)
    form     = CategoryForm(request.POST or None, instance=category)
    if form.is_valid():
        form.save()
        messages.success(request, f'Category "{category.name}" updated.')
        return redirect('category_list')
    return render(request, 'admin/category_form.html', {'form': form})


@admin_required
def category_delete(request, pk):
    category = get_object_or_404(Category, id=pk)
    name     = category.name
    category.delete()
    messages.success(request, f'Category "{name}" deleted.')
    return redirect('category_list')

@login_required
def advanced_dashboard(request):
    context = {
        'total_tasks':    TaskDetail.objects.count(),
        'open_tasks':     TaskDetail.objects.filter(TASK_STATUS='Open').count(),
        'in_progress':    TaskDetail.objects.filter(TASK_STATUS='In Progress').count(),
        'closed_tasks':   TaskDetail.objects.filter(TASK_STATUS='Closed').count(),
        'my_tasks':       TaskDetail.objects.filter(TASK_CREATED=request.user).count(),
        'urgent_tasks':   TaskDetail.objects.filter(priority='URGENT').count(),
        'high_priority':  TaskDetail.objects.filter(priority='HIGH').count(),
        'medium_priority':TaskDetail.objects.filter(priority='MEDIUM').count(),
        'low_priority':   TaskDetail.objects.filter(priority='LOW').count(),
        'recent_tasks':   TaskDetail.objects.order_by('-TASK_CREATED_ON')[:5],
    }
    return render(request, 'dashboard/advanced.html', context)

@login_required
@department_member_required
def department_dashboard(request, dept_id=None):
    if dept_id:
        department = get_object_or_404(Department, id=dept_id)
        if not request.user.is_superuser:
            if not DepartmentMember.objects.filter(
                user=request.user, department=department, is_active=True
            ).exists():
                messages.error(request, 'You are not a member of this department.')
                return redirect('base')
    else:
        membership = DepartmentMember.objects.filter(user=request.user, is_active=True).first()
        if not membership:
            messages.error(request, 'You are not a member of any department.')
            return redirect('base')
        department = membership.department

    tasks   = TaskDetail.objects.filter(assigned_department=department)\
                .select_related('TASK_CREATED', 'category', 'assigned_to')
    members = DepartmentMember.objects.filter(department=department, is_active=True)\
                .select_related('user')

    stats = {
        'total':      tasks.count(),
        'open':       tasks.filter(TASK_STATUS='Open').count(),
        'in_progress':tasks.filter(TASK_STATUS='In Progress').count(),
        'closed':     tasks.filter(TASK_STATUS='Closed').count(),
        'resolved':   tasks.filter(TASK_STATUS='Resolved').count(),
        'members':    members.count(),
    }
    user_membership = members.filter(user=request.user).first()
    return render(request, 'department_dashboard.html', {
        'department':      department,
        'tasks':           tasks[:20],
        'members':         members,
        'stats':           stats,
        'user_role':       user_membership.role if user_membership else None,
        'user_permissions':user_membership if user_membership else None,
    })


@login_required
def department_members(request, dept_id=None):
    user_departments = Department.objects.filter(
        departmentmember__user=request.user,
        departmentmember__is_active=True,
        is_active=True,
    ).distinct().order_by('name')

    if request.user.is_superuser:
        if dept_id is not None:
            scoped_departments = Department.objects.filter(id=dept_id, is_active=True)
        else:
            scoped_departments = Department.objects.filter(is_active=True).order_by('name')
    else:
        if not user_departments.exists():
            messages.error(request, 'You are not a member of any department.')
            return redirect('base')
        if dept_id is not None:
            scoped_departments = user_departments.filter(id=dept_id)
            if not scoped_departments.exists():
                messages.error(request, 'You are not a member of this department.')
                return redirect('department_members')
        else:
            scoped_departments = user_departments

    department = scoped_departments.first()
    scoped_department_ids = list(scoped_departments.values_list('id', flat=True))

    members = DepartmentMember.objects.filter(
        department_id__in=scoped_department_ids, is_active=True
    ).select_related('user', 'user__userprofile').order_by('department__name', 'role', 'user__username')

    dept_tasks = TaskDetail.objects.filter(
        assigned_department_id__in=scoped_department_ids
    ).select_related('assigned_to', 'category')
    open_statuses = ['Open', 'In Progress', 'Reopen']
    today = timezone.localdate()

    dept_stats = {
        'total': dept_tasks.count(),
        'open': dept_tasks.filter(TASK_STATUS='Open').count(),
        'in_progress': dept_tasks.filter(TASK_STATUS='In Progress').count(),
        'resolved': dept_tasks.filter(TASK_STATUS__in=['Closed', 'Resolved']).count(),
        'overdue': dept_tasks.filter(TASK_DUE_DATE__lt=today).exclude(
            TASK_STATUS__in=['Closed', 'Resolved', 'Expired']
        ).count(),
    }

    def _build_member_stats_for_scope(scope_members, scope_tasks):
        resolved_map = {
            row['assigned_to']: row['total']
            for row in scope_tasks.filter(TASK_STATUS__in=['Closed', 'Resolved'])
            .values('assigned_to').annotate(total=Count('id'))
        }
        active_map = {
            row['assigned_to']: row['total']
            for row in scope_tasks.filter(TASK_STATUS__in=open_statuses)
            .values('assigned_to').annotate(total=Count('id'))
        }
        overdue_map = {
            row['assigned_to']: row['total']
            for row in scope_tasks.filter(TASK_DUE_DATE__lt=today)
            .exclude(TASK_STATUS__in=['Closed', 'Resolved', 'Expired'])
            .values('assigned_to').annotate(total=Count('id'))
        }

        stats = []
        for m in scope_members:
            resolved = resolved_map.get(m.user_id, 0)
            active = active_map.get(m.user_id, 0)
            overdue = overdue_map.get(m.user_id, 0)
            total_worked = resolved + active
            completion_rate = int((resolved / total_worked) * 100) if total_worked > 0 else 0
            profile_image = ''
            try:
                if getattr(m.user, 'userprofile', None) and m.user.userprofile.Profile_Image:
                    profile_image = m.user.userprofile.Profile_Image.url
            except Exception:
                profile_image = ''

            stats.append({
                'membership':      m,
                'resolved':        resolved,
                'active':          active,
                'overdue':         overdue,
                'completion_rate': completion_rate,
                'profile_image':   profile_image,
                'is_current_user': m.user_id == request.user.id,
            })
        stats.sort(key=lambda x: (-x['resolved'], x['active'], x['membership'].user.username))
        return stats

    member_stats = _build_member_stats_for_scope(members, dept_tasks)
    role_counts = {r['role']: r['total'] for r in members.values('role').annotate(total=Count('id'))}
    recent_tickets = dept_tasks.order_by('-updated_at')[:8]

    department_sections = []
    for d in scoped_departments:
        dept_members = members.filter(department=d)
        dept_member_count = dept_members.count()
        d_tasks = dept_tasks.filter(assigned_department=d)
        d_role_counts = {r['role']: r['total'] for r in dept_members.values('role').annotate(total=Count('id'))}
        department_sections.append({
            'department': d,
            'total_members': dept_member_count,
            'member_stats': _build_member_stats_for_scope(dept_members, d_tasks),
            'role_counts': d_role_counts,
            'recent_tickets': d_tasks.order_by('-updated_at')[:8],
        })

    multi_departments = []
    for user_dept in user_departments:
        user_dept_tasks = TaskDetail.objects.filter(assigned_department=user_dept)
        multi_departments.append({
            'department': user_dept,
            'members': DepartmentMember.objects.filter(
                department=user_dept, is_active=True
            ).count(),
            'total': user_dept_tasks.count(),
            'open': user_dept_tasks.filter(
                TASK_STATUS__in=['Open', 'In Progress', 'Reopen']
            ).count(),
            'resolved': user_dept_tasks.filter(
                TASK_STATUS__in=['Closed', 'Resolved']
            ).count(),
        })

    return render(request, 'department_members.html', {
        'department':      department,
        'member_stats':    member_stats,
        'total_members':   members.count(),
        'dept_stats':      dept_stats,
        'recent_tickets':  recent_tickets,
        'role_counts':     role_counts,
        'multi_departments': multi_departments,
        'department_sections': department_sections,
        'is_multi_department_view': dept_id is None and len(scoped_department_ids) > 1,
        'department_display_name': ", ".join(
            scoped_departments.values_list('name', flat=True)
        ) if dept_id is None and len(scoped_department_ids) > 1 else (department.name if department else "Departments"),
    })

@admin_required
def admin_department_list(request):
    departments = Department.objects.filter(is_active=True).order_by('name')
    dept_data = []
    for dept in departments:
        members = DepartmentMember.objects.filter(
            department=dept, is_active=True, user__is_superuser=False
        ).select_related('user')
        tasks = TaskDetail.objects.filter(assigned_department=dept)
        dept_data.append({
            'department': dept,
            'members':    members,
            'total':      tasks.count(),
            'open':       tasks.filter(TASK_STATUS='Open').count(),
            'resolved':   tasks.filter(TASK_STATUS__in=['Closed', 'Resolved']).count(),
        })

    return render(request, 'admin_department_list.html', {
        'dept_data':    dept_data,
        'all_users':    User.objects.filter(is_active=True, is_superuser=False).order_by('username'),
        'departments':  departments,
    })


@admin_required
def admin_add_member(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role    = request.POST.get('role', 'MEMBER')
        try:
            user = User.objects.get(id=user_id)
            if user.is_superuser:
                messages.error(request, 'Admin users cannot be added to departments.')
                return redirect('admin_department_list')
            membership, created = DepartmentMember.objects.get_or_create(
                user=user, department=department,
                defaults={
                    'role':               role,
                    'added_by':           request.user,
                    'can_close_tickets':  True,
                    'can_assign_tickets': role in ['LEAD', 'MANAGER', 'HEAD'],
                    'can_delete_tickets': role in ['MANAGER', 'HEAD'],
                }
            )
            status_message = ''
            already_active_unchanged = False
            if not created:
                was_active = membership.is_active
                role_changed = membership.role != role
                membership.role = role
                membership.is_active = True
                membership.save(update_fields=['role', 'is_active'])
                if was_active and not role_changed:
                    status_message = f'{user.username} is already in {department.name}.'
                    already_active_unchanged = True
                elif was_active and role_changed:
                    status_message = f'{user.username} role updated in {department.name}.'
                else:
                    status_message = f'{user.username} re-activated in {department.name}.'
            else:
                status_message = f'{user.username} added to {department.name}.'

            for task in TaskDetail.objects.filter(
                assigned_department=department,
            ).exclude(TASK_STATUS__in=['Closed', 'Resolved', 'Expired']):
                MyCart.objects.get_or_create(user=user, task=task)

            log_activity(request.user, 'UPDATED',
                         f'Added {user.username} to {department.name} as {role}')
            if already_active_unchanged:
                messages.info(request, status_message)
            else:
                messages.success(request, status_message)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')

    return redirect('admin_department_list')


@admin_required
def admin_remove_member(request, dept_id, user_id):
    department = get_object_or_404(Department, id=dept_id)
    user       = get_object_or_404(User, id=user_id)

    DepartmentMember.objects.filter(user=user, department=department).update(is_active=False)

    dept_task_ids = TaskDetail.objects.filter(
        assigned_department=department
    ).values_list('id', flat=True)
    MyCart.objects.filter(user=user, task_id__in=dept_task_ids).delete()

    log_activity(request.user, 'UPDATED',
                 f'Removed {user.username} from {department.name}')
    messages.success(request, f'{user.username} removed from {department.name}.')
    return redirect('admin_department_list')

@login_required
def notifications_list(request):
    notifs      = _notifications_for_user(request.user)
    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'unread':
        notifs = notifs.filter(is_read=False)
    elif filter_type == 'read':
        notifs = notifs.filter(is_read=True)
    paginator = Paginator(notifs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))
    all_notifs = _notifications_for_user(request.user)
    stats = {
        'total':  all_notifs.count(),
        'unread': all_notifs.filter(is_read=False).count(),
        'read':   all_notifs.filter(is_read=True).count(),
    }
    return render(request, 'notifications_list.html', {
        'notifications': page_obj, 'stats': stats, 'filter_type': filter_type,
    })


@login_required
def mark_notification_read(request, notification_id):
    notif    = get_object_or_404(_notifications_for_user(request.user), id=notification_id)
    notif.mark_as_read()
    return redirect(request.GET.get('next', notif.get_url()))


@login_required
def mark_all_read(request):
    updated = _notifications_for_user(request.user).filter(is_read=False).update(is_read=True)
    messages.success(request, f'Marked {updated} notifications as read.')
    return redirect('notifications_list')


@login_required
def delete_notification(request, notification_id):
    notif = get_object_or_404(_notifications_for_user(request.user), id=notification_id)
    notif.delete()
    messages.success(request, 'Notification deleted.')
    return redirect('notifications_list')


@login_required
def delete_all_notifications(request):
    deleted, _ = _notifications_for_user(request.user).delete()
    messages.success(request, f'Deleted {deleted} notifications.')
    return redirect('notifications_list')


@login_required
def notification_count_api(request):
    count = _notifications_for_user(request.user).filter(is_read=False).count()
    return JsonResponse({'count': count})

@admin_required
def analytics_dashboard(request):
    range_type = request.GET.get('range', '30_days')
    start_date, end_date = get_date_range(range_type)
    start_dt = datetime.combine(start_date, time.min)
    end_dt   = datetime.combine(end_date,   time.max)

    if range_type == 'custom':
        try:
            start_date = datetime.strptime(request.GET.get('start_date', ''), '%Y-%m-%d').date()
            end_date   = datetime.strptime(request.GET.get('end_date',   ''), '%Y-%m-%d').date()
            start_dt   = datetime.combine(start_date, time.min)
            end_dt     = datetime.combine(end_date,   time.max)
        except ValueError:
            messages.error(request, 'Invalid date format.')
            start_date, end_date = get_date_range('30_days')

    department = None
    dept_id    = request.GET.get('department')
    if dept_id:
        try:
            department = Department.objects.get(id=dept_id)
        except Department.DoesNotExist:
            pass

    context = {
        'start_date':           start_date,
        'end_date':             end_date,
        'range_type':           range_type,
        'selected_department':  department,
        'departments':          Department.objects.filter(is_active=True),
        'stats':                get_task_statistics(start_dt, end_dt, department),
        'dept_stats':           get_department_statistics(start_dt, end_dt),
        'dept_comparison':      get_department_comparison(),
        'top_creators':         get_top_task_creators(5, start_dt, end_dt),
        'top_resolvers':        get_top_task_resolvers(5, start_dt, end_dt),
        'priority_dist':        get_priority_distribution(start_dt, end_dt, department),
        'category_dist':        get_category_distribution(start_dt, end_dt),
    }
    return render(request, 'analytics_dashboard.html', context)


@admin_required
def api_tasks_over_time(request):
    try:
        range_type       = request.GET.get('range', '30_days')
        start_date, end_date = get_date_range(range_type)
        dept_id          = request.GET.get('department')
        department       = Department.objects.get(id=dept_id) if dept_id else None
        data             = get_tasks_over_time(start_date, end_date, department)
        return JsonResponse({'labels': [i['date'] for i in data], 'data': [i['count'] for i in data]})
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc(), 'labels': [], 'data': []}, status=500)


@admin_required
def api_department_comparison(request):
    try:
        return JsonResponse(get_department_comparison())
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@admin_required
def api_priority_distribution(request):
    try:
        range_type       = request.GET.get('range', '30_days')
        start_date, end_date = get_date_range(range_type)
        data             = get_priority_distribution(start_date, end_date)
        return JsonResponse({
            'labels': ['Urgent','High','Medium','Low'],
            'data':   [data['URGENT'],data['HIGH'],data['MEDIUM'],data['LOW']],
            'colors': ['#ef4444','#f59e0b','#3b82f6','#94a3b8'],
        })
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@admin_required
def api_category_distribution(request):
    try:
        range_type       = request.GET.get('range', '30_days')
        start_date, end_date = get_date_range(range_type)
        data             = get_category_distribution(start_date, end_date)
        if not data:
            return JsonResponse({'labels':['No Categories'],'data':[1],'colors':['#94a3b8']})
        return JsonResponse({
            'labels': [i['name']  for i in data],
            'data':   [i['count'] for i in data],
            'colors': [i['color'] for i in data],
        })
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@admin_required
def export_analytics_excel(request):
    import openpyxl
    from openpyxl.styles import Font
    range_type       = request.GET.get('range', '30_days')
    start_date, end_date = get_date_range(range_type)
    start_dt = datetime.combine(start_date, time.min)
    end_dt   = datetime.combine(end_date,   time.max)
    data     = prepare_export_data(start_dt, end_dt)

    wb  = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Summary"
    ws1['A1'] = "Helpdesk Analytics Report"
    ws1['A1'].font = Font(size=16, bold=True)
    ws1['A2'] = f"Period: {start_dt} to {end_dt}"
    ws1['A3'] = f"Generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M')}"
    rows = [
        ('Total Tasks', data['statistics']['total']),
        ('Open',        data['statistics']['open']),
        ('In Progress', data['statistics']['in_progress']),
        ('Closed',      data['statistics']['closed']),
        ('Resolved',    data['statistics']['resolved']),
        ('Completion Rate', f"{data['statistics']['completion_rate']:.2f}%"),
        ('Avg Resolution (hrs)', data['statistics']['avg_resolution_hours']),
    ]
    for i, (label, val) in enumerate(rows, start=6):
        ws1.cell(row=i, column=1).value = label
        ws1.cell(row=i, column=2).value = val

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=analytics_{start_dt}_{end_dt}.xlsx'
    wb.save(response)
    return response

@login_required
def task_history(request, pk):
    if pk == 0:
        resolved_entry = TaskHistory.objects.filter(
            task=OuterRef('pk'),
            action_type__in=['RESOLVED', 'CLOSED']
        ).order_by('-changed_at')

        resolved_tasks = (
            TaskDetail.objects
            .filter(TASK_STATUS__in=['Resolved', 'Closed'])
            .filter(
                Q(TASK_CREATED=request.user) |
                Q(assigned_to=request.user) |
                Q(TASK_CLOSED=request.user)
            )
            .annotate(
                resolved_by=Subquery(resolved_entry.values('changed_by__username')[:1]),
                resolved_on=Subquery(resolved_entry.values('changed_at')[:1]),
            )
            .select_related('assigned_department', 'assigned_to', 'TASK_CREATED')
            .order_by('-resolved_on')
        )

        return render(request, 'task_history.html', {
            'resolved_history_mode': True,
            'resolved_tasks': resolved_tasks,
            'my_resolved_count': resolved_tasks.filter(TASK_CLOSED=request.user).count(),
        })

    task = get_object_or_404(TaskDetail, id=pk)
    history = (
        TaskHistory.objects
        .filter(task=task)
        .select_related('changed_by')
        .order_by('-changed_at')
    )

    return render(request, 'task_history.html', {
        'task': task,
        'history': history
    })

@login_required
def rate_task(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    if task.TASK_CREATED != request.user:
        messages.error(request, 'Only the task creator can rate this task.')
        return redirect('taskinfo', pk=pk)
    if task.TASK_STATUS not in ['Closed', 'Resolved']:
        messages.error(request, 'You can only rate completed tasks.')
        return redirect('taskinfo', pk=pk)
    if TaskRating.objects.filter(task=task).exists():
        messages.info(request, 'You have already rated this task.')
        return redirect('taskinfo', pk=pk)

    from .forms import TaskRatingForm
    if request.method == 'POST':
        form = TaskRatingForm(request.POST)
        if form.is_valid():
            rating          = form.save(commit=False)
            rating.task     = task
            rating.rated_by = request.user
            rating.save()
            notify_task_rated(task, rating)
            TaskHistory.objects.create(
                task=task, changed_by=request.user,
                action_type='UPDATED', field_name='rating',
                new_value=str(rating.rating),
                description=f'Task rated {rating.rating}⭐ by {request.user.username}',
            )
            messages.success(request, f'Thank you! You rated this task {rating.rating}⭐')
            return redirect('taskinfo', pk=pk)
    else:
        form = TaskRatingForm()
    return render(request, 'rate_task.html', {'form': form, 'task': task})

@admin_required
def send_overdue_note(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    if request.method != 'POST':
        return redirect('taskinfo', pk=pk)

    if task.TASK_STATUS in ['Closed', 'Resolved']:
        messages.error(request, 'This ticket is already completed.')
        return redirect('taskinfo', pk=pk)

    if not task.is_overdue:
        messages.error(request, 'Overdue note can be sent only for overdue tickets.')
        return redirect('taskinfo', pk=pk)

    note = request.POST.get('overdue_note', '').strip()
    if not note:
        messages.error(request, 'Please enter a note before sending.')
        return redirect('taskinfo', pk=pk)

    recipient_ids = set()
    if task.assigned_to_id:
        recipient_ids.add(task.assigned_to_id)
    if task.assigned_department_id:
        dept_member_ids = DepartmentMember.objects.filter(
            department=task.assigned_department,
            is_active=True
        ).values_list('user_id', flat=True)
        recipient_ids.update(dept_member_ids)

    recipient_ids.discard(request.user.id)
    recipients = User.objects.filter(id__in=recipient_ids, is_active=True)

    sent_count = 0
    for recipient in recipients:
        create_notification(
            user=recipient,
            notification_type='TASK_OVERDUE',
            title=f'Overdue reminder: #{task.id} {task.TASK_TITLE}',
            message=note,
            task=task,
            extra_data={
                'sent_by': request.user.username,
                'is_admin_note': True,
            },
        )
        sent_count += 1

    if sent_count:
        TaskHistory.objects.create(
            task=task,
            changed_by=request.user,
            action_type='UPDATED',
            field_name='admin_overdue_note',
            description=f'Admin sent overdue reminder to {sent_count} users.',
            new_value=note,
        )
        log_activity(
            request.user,
            'UPDATED',
            f'Sent overdue reminder for ticket #{task.id}',
            description=note,
            task=task,
        )
        messages.success(request, f'Overdue reminder sent to {sent_count} users.')
    else:
        messages.warning(request, 'No eligible recipients found for this ticket.')

    return redirect('taskinfo', pk=pk)


@login_required
def reply_overdue_note(request, pk):
    task = get_object_or_404(TaskDetail, id=pk)
    if request.method != 'POST':
        return redirect('taskinfo', pk=pk)

    if _is_admin_user(request.user):
        messages.error(request, 'Admin should use overdue note instead of member reply.')
        return redirect('taskinfo', pk=pk)

    can_reply = (
        task.assigned_to_id == request.user.id
        or _is_department_member(request.user, task)
    )
    if not can_reply:
        messages.error(request, 'You are not allowed to reply to this overdue note.')
        return redirect('taskinfo', pk=pk)

    reply_text = request.POST.get('overdue_note_reply', '').strip()
    if not reply_text:
        messages.error(request, 'Please enter a reply before sending.')
        return redirect('taskinfo', pk=pk)

    TaskHistory.objects.create(
        task=task,
        changed_by=request.user,
        action_type='UPDATED',
        field_name='admin_overdue_note_reply',
        description=f'Overdue note reply by {request.user.username}.',
        new_value=reply_text,
    )
    log_activity(
        request.user,
        'COMMENTED',
        f'Replied on overdue note for ticket #{task.id}',
        description=reply_text,
        task=task,
    )

    for admin_user in User.objects.filter(is_superuser=True, is_active=True):
        create_notification(
            user=admin_user,
            notification_type='TASK_COMMENTED',
            title=f'Overdue note reply: #{task.id} {task.TASK_TITLE}',
            message=reply_text,
            task=task,
            extra_data={
                'sent_by': request.user.username,
                'is_admin_note_reply': True,
            },
        )

    messages.success(request, 'Your reply was sent to admin.')
    return redirect('taskinfo', pk=pk)

@login_required
def department_analytics(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)

    range_type           = request.GET.get('range', '30_days')
    start_date, end_date = get_date_range(range_type)

    stats   = get_task_statistics(start_date, end_date, department)
    members = DepartmentMember.objects.filter(
        department=department, is_active=True
    ).select_related('user')

    member_stats = []
    for member in members:
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime   = timezone.make_aware(datetime.combine(end_date,   time.max))

        tasks_created  = TaskDetail.objects.filter(
            TASK_CREATED=member.user,
            TASK_CREATED_ON__range=(start_datetime, end_datetime)
        ).count()

        tasks_resolved = TaskDetail.objects.filter(
            assigned_to=member.user,
            TASK_STATUS__in=['Closed', 'Resolved'],
            TASK_CLOSED_ON__range=(start_datetime, end_datetime)
        ).count()

        active_tasks = TaskDetail.objects.filter(
            assigned_to=member.user,
            TASK_STATUS__in=['Open', 'In Progress', 'Reopen']
        ).count()

        member_stats.append({
            'member':         member,
            'tasks_created':  tasks_created,
            'tasks_resolved': tasks_resolved,
            'active_tasks':   active_tasks,
        })

    return render(request, 'department_dashboard.html', {
        'department':   department,
        'start_date':   start_date,
        'end_date':     end_date,
        'range_type':   range_type,
        'stats':        stats,
        'member_stats': member_stats,
    })

@admin_required
def export_analytics_pdf(request):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from io import BytesIO

    range_type           = request.GET.get('range', '30_days')
    start_date, end_date = get_date_range(range_type)
    start_dt = datetime.combine(start_date, time.min)
    end_dt   = datetime.combine(end_date,   time.max)
    data     = prepare_export_data(start_dt, end_dt)

    buffer = BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=30,
    )

    elements = [
        Paragraph("Helpdesk Analytics Report", title_style),
        Paragraph(
            f"Period: {start_dt} to {end_dt}<br/>"
            f"Generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M')}",
            styles['Normal']
        ),
        Spacer(1, 0.3 * inch),
    ]

    stats_data = [
        ['Metric', 'Value'],
        ['Total Tasks',          str(data['statistics']['total'])],
        ['Open',                 str(data['statistics']['open'])],
        ['In Progress',          str(data['statistics']['in_progress'])],
        ['Closed',               str(data['statistics']['closed'])],
        ['Resolved',             str(data['statistics']['resolved'])],
        ['Completion Rate',      f"{data['statistics']['completion_rate']:.2f}%"],
        ['Avg Resolution Time',  f"{data['statistics']['avg_resolution_hours']} hours"],
    ]

    stats_table = Table(stats_data)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1,  0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR',    (0, 0), (-1,  0), colors.whitesmoke),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME',     (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1,  0), 13),
        ('BOTTOMPADDING',(0, 0), (-1,  0), 12),
        ('BACKGROUND',   (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID',         (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
    ]))

    elements.append(stats_table)

    if data.get('department_stats'):
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(Paragraph("Department Breakdown", styles['Heading2']))
        elements.append(Spacer(1, 0.2 * inch))

        dept_rows = [['Department', 'Total', 'Open', 'Closed', 'Completion %', 'Members']]
        for dept in data['department_stats']:
            dept_rows.append([
                dept['name'],
                str(dept['total_tasks']),
                str(dept['open_tasks']),
                str(dept['closed_tasks']),
                f"{dept['completion_rate']:.1f}%",
                str(dept['members_count']),
            ])

        dept_table = Table(dept_rows)
        dept_table.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1,  0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR',    (0, 0), (-1,  0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1,  0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1,  0), 11),
            ('BOTTOMPADDING',(0, 0), (-1,  0), 10),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#F1F5F9')]),
            ('GRID',         (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        elements.append(dept_table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename=analytics_{start_date}_{end_date}.pdf'
    )
    return response

