from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import DepartmentMember, Department, TaskDetail


def is_admin_user(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser

def user_is_department_member(user, department):
    if not user.is_authenticated or user.is_superuser:
        return False
    return DepartmentMember.objects.filter(
        user=user, department=department, is_active=True
    ).exists()


def user_department_role(user, department):
    try:
        return DepartmentMember.objects.get(
            user=user, department=department, is_active=True
        ).role
    except DepartmentMember.DoesNotExist:
        return None


def user_has_department_permission(user, department, permission_type):
    try:
        member = DepartmentMember.objects.get(
            user=user, department=department, is_active=True
        )
        return getattr(member, permission_type, False)
    except DepartmentMember.DoesNotExist:
        return False


def get_user_departments(user):
    if not user.is_authenticated or user.is_superuser:
        return Department.objects.none()

    return Department.objects.filter(
        departmentmember__user=user,
        departmentmember__is_active=True,
        is_active=True,
    ).distinct()
    
def is_department_lead_or_higher(user, department):
    role = user_department_role(user, department)
    return role in ['LEAD', 'MANAGER', 'HEAD']

def can_user_accept_task(user, task):
    if user.is_superuser:
        return False, 'Superuser cannot accept or reject tasks'

    if task.TASK_STATUS != 'Open':
        return False, 'Task is not open for acceptance'

    if task.TASK_CREATED == user:
        return False, 'You cannot accept your own task'

    from .models import MyCart
    if MyCart.objects.filter(task=task, user=user).exists():
        return False, 'Task already in your queue'

    if task.assigned_department:
        if not user_is_department_member(user, task.assigned_department):
            return False, f'This task belongs to {task.assigned_department.name} department'

    return True, 'OK'


def can_user_update_task(user, task):
    if user.is_superuser:
        return True, 'OK'
    if task.TASK_CREATED == user:
        return True, 'OK'
    if task.assigned_to == user:
        return True, 'OK'
    if task.assigned_department:
        if user_has_department_permission(user, task.assigned_department, 'can_assign_tickets'):
            return True, 'OK'
    return False, 'You do not have permission to update this task'


def can_user_close_task(user, task):
    if user.is_superuser:
        return True, 'OK'
    if task.assigned_to == user:
        return True, 'OK'
    if task.assigned_department:
        if user_has_department_permission(user, task.assigned_department, 'can_close_tickets'):
            return True, 'OK'
    return False, 'You do not have permission to close this task'


def filter_tasks_by_department_access(queryset, user):
    if user.is_superuser:
        return queryset
    from django.db.models import Q
    user_departments = get_user_departments(user)
    return queryset.filter(
        Q(TASK_CREATED=user) |
        Q(assigned_to=user) |
        Q(assigned_department__in=user_departments) |
        Q(assigned_department__isnull=True)
    ).distinct()


def get_department_statistics(department):
    """Per-department stats dict — used in department_dashboard view."""
    tasks = TaskDetail.objects.filter(assigned_department=department)
    return {
        'total':       tasks.count(),
        'open':        tasks.filter(TASK_STATUS='Open').count(),
        'in_progress': tasks.filter(TASK_STATUS='In Progress').count(),
        'closed':      tasks.filter(TASK_STATUS='Closed').count(),
        'resolved':    tasks.filter(TASK_STATUS='Resolved').count(),
        'overdue':     tasks.filter(
            TASK_STATUS='Open', TASK_DUE_DATE__lt=timezone.now().date()
        ).count(),
    }

def get_user_department_context(user):
    if not user.is_authenticated:
        return {
            'user_departments':       Department.objects.none(),
            'user_department_count':  0,
            'is_department_member':   False,
            'is_department_lead':     False,
            'is_department_manager':  False,
            'department_open_tasks':  0,
            'department_count':       0,
            'department_tasks_count': 0,
        }

    user_depts = get_user_departments(user)

    is_lead = DepartmentMember.objects.filter(
        user=user, role__in=['LEAD', 'MANAGER', 'HEAD'], is_active=True
    ).exists()

    is_manager = DepartmentMember.objects.filter(
        user=user, role__in=['MANAGER', 'HEAD'], is_active=True
    ).exists()

    dept_open_tasks  = TaskDetail.objects.filter(
        assigned_department__in=user_depts, TASK_STATUS='Open'
    ).count()

    dept_total_tasks = TaskDetail.objects.filter(
        assigned_department__in=user_depts
    ).count()

    return {
        'user_departments':       user_depts,
        'user_department_count':  user_depts.count(),
        'is_department_member':   user_depts.exists(),
        'is_department_lead':     is_lead,
        'is_department_manager':  is_manager,
        'department_open_tasks':  dept_open_tasks,
        'department_count':       user_depts.count(),
        'department_tasks_count': dept_total_tasks,
    }

def department_member_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            messages.error(
                request,
                "Superuser is not a department member."
            )
            return redirect('analytics_dashboard')                          

        if not get_user_departments(request.user).exists():
            messages.error(
                request,
                'You must be a member of a department to access this page. '
                'Please contact an administrator.',
            )
            return redirect('base')

        return view_func(request, *args, **kwargs)
    return wrapper


def task_department_access_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, pk, *args, **kwargs):
        task = get_object_or_404(TaskDetail, id=pk)
        if request.user.is_superuser:
            return view_func(request, pk, *args, **kwargs)
        if task.TASK_CREATED == request.user:
            return view_func(request, pk, *args, **kwargs)
        if task.assigned_to == request.user:
            return view_func(request, pk, *args, **kwargs)
        if task.assigned_department:
            if user_is_department_member(request.user, task.assigned_department):
                return view_func(request, pk, *args, **kwargs)
            messages.error(
                request,
                f'Access denied. This task is assigned to {task.assigned_department.name} department.',
            )
            return redirect('base')
        return view_func(request, pk, *args, **kwargs)
    return wrapper


def department_lead_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if DepartmentMember.objects.filter(
            user=request.user, role__in=['LEAD', 'MANAGER', 'HEAD'], is_active=True
        ).exists():
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access denied. Department leadership role required.')
        return redirect('base')
    return wrapper


def can_assign_tasks_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, pk, *args, **kwargs):
        task = get_object_or_404(TaskDetail, id=pk)
        if request.user.is_superuser or task.TASK_CREATED == request.user:
            return view_func(request, pk, *args, **kwargs)
        if task.assigned_department and user_has_department_permission(
            request.user, task.assigned_department, 'can_assign_tickets'
        ):
            return view_func(request, pk, *args, **kwargs)
        messages.error(request, 'Access denied. You cannot assign tasks in this department.')
        return redirect('taskinfo', pk=pk)
    return wrapper


def can_delete_tasks_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, pk, *args, **kwargs):
        task = get_object_or_404(TaskDetail, id=pk)
        if request.user.is_superuser or task.TASK_CREATED == request.user:
            return view_func(request, pk, *args, **kwargs)
        if task.assigned_department and user_has_department_permission(
            request.user, task.assigned_department, 'can_delete_tickets'
        ):
            return view_func(request, pk, *args, **kwargs)
        messages.error(request, 'Access denied. You cannot delete tasks in this department.')
        return redirect('taskinfo', pk=pk)
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if is_admin_user(request.user):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Admin access required.")
        return redirect('base')
    return wrapper


class LoginRoleAuthorization:
    USER = 'user'
    ADMIN = 'admin'
    DEFAULT = USER

    MODE_CONFIG = {
        USER:  {'allow_register': True},
        ADMIN: {'allow_register': False},
    }

    @classmethod
    def normalize_mode(cls, mode):
        mode = (mode or '').strip().lower()
        return mode if mode in cls.MODE_CONFIG else cls.DEFAULT

    @classmethod
    def can_register(cls, mode):
        return cls.MODE_CONFIG[cls.normalize_mode(mode)]['allow_register']

    @classmethod
    def account_access_error(cls, mode, user):
        """
        USER login page  → block superusers (must use admin login page).
        ADMIN login page → block non-superusers (must use user login page).
        Returns an error string, or '' if access is allowed.
        """
        mode = cls.normalize_mode(mode)
        if mode == cls.ADMIN:
            if not user.is_superuser:
                return "This login page is for administrators only. Please use the user login page."
        else:
            if user.is_superuser:
                return "Superuser accounts must log in via the Admin login page."
        return ""

    @classmethod
    def success_redirect(cls, mode, user, dashboard_url_fn):
        """
        Both USER and ADMIN pages redirect to our custom dashboard.
        Django /admin/ panel is accessed directly, not through our login flow.
        """
        return dashboard_url_fn(user)