from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

from .models import Notification, DepartmentMember

def create_notification(user, notification_type, title, message, task=None, extra_data=None):
    notification = Notification.objects.create(
        user=user,
        task=task,
        notification_type=notification_type,
        title=title,
        message=message,
        extra_data=extra_data or {},
    )

    if user.email:
        send_notification_email(notification)

    return notification


def send_notification_email(notification):
    try:
        context = {
            'notification': notification,
            'user':         notification.user,
            'task':         notification.task,
        }
        html_message  = render_to_string('notification.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject      = notification.title or 'Helpdesk Notification',
            message      = plain_message,
            from_email   = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [notification.user.email],
            html_message = html_message,
            fail_silently = True,
        )

        notification.email_sent    = True
        notification.email_sent_at = timezone.now()
        notification.save(update_fields=['email_sent', 'email_sent_at'])
        return True
    except Exception:
        return False


def notify_task_created(task):
    notifications = []

    if not task.assigned_department:
        return notifications

    members = DepartmentMember.objects.filter(
        department=task.assigned_department,
        is_active=True,
    ).exclude(user=task.TASK_CREATED)

    for member in members:
        notifications.append(create_notification(
            user=member.user,
            notification_type='TASK_CREATED',
            title=f'New task in {task.assigned_department.name}',
            message=f'{task.TASK_CREATED.username} created task "{task.TASK_TITLE}"',
            task=task,
            extra_data={'department': task.assigned_department.name, 'priority': task.priority},
        ))

    return notifications


def notify_task_assigned(task, assigned_to, assigned_by):
    if assigned_to == assigned_by:
        return None

    return create_notification(
        user=assigned_to,
        notification_type='TASK_ASSIGNED',
        title='Task assigned to you',
        message=f'{assigned_by.username} assigned you task "{task.TASK_TITLE}"',
        task=task,
        extra_data={'assigned_by': assigned_by.username, 'priority': task.priority},
    )


def notify_task_accepted(task, accepted_by):
    if task.TASK_CREATED == accepted_by:
        return None

    return create_notification(
        user=task.TASK_CREATED,
        notification_type='TASK_ACCEPTED',
        title='Your task was accepted',
        message=f'{accepted_by.username} accepted your task "{task.TASK_TITLE}"',
        task=task,
        extra_data={'accepted_by': accepted_by.username},
    )


def notify_task_updated(task, updated_by, changes=None):
    if task.TASK_CREATED == updated_by:
        return None

    return create_notification(
        user=task.TASK_CREATED,
        notification_type='TASK_UPDATED',
        title='Task updated',
        message=f'{updated_by.username} updated task "{task.TASK_TITLE}"',
        task=task,
        extra_data={'updated_by': updated_by.username, 'changes': changes or []},
    )


def notify_task_closed(task, closed_by):
    if task.TASK_CREATED == closed_by:
        return None

    return create_notification(
        user=task.TASK_CREATED,
        notification_type='TASK_CLOSED',
        title='Your task was closed',
        message=f'{closed_by.username} closed task "{task.TASK_TITLE}"',
        task=task,
        extra_data={'closed_by': closed_by.username},
    )


def notify_task_resolved(task, resolved_by):
    if task.TASK_CREATED == resolved_by:
        return None

    return create_notification(
        user=task.TASK_CREATED,
        notification_type='TASK_RESOLVED',
        title='Your task has been resolved',
        message=f'{resolved_by.username} resolved task "{task.TASK_TITLE}"',
        task=task,
        extra_data={'resolved_by': resolved_by.username},
    )


def notify_task_reopened(task, reopened_by, reason=None):
    if not task.TASK_CLOSED or task.TASK_CLOSED == reopened_by:
        return None

    return create_notification(
        user=task.TASK_CLOSED,
        notification_type='TASK_REOPENED',
        title='Task reopened',
        message=f'{reopened_by.username} reopened task "{task.TASK_TITLE}"',
        task=task,
        extra_data={'reopened_by': reopened_by.username, 'reason': reason or ''},
    )


def notify_task_commented(task, commenter, comment_text=''):
    notifications = []
    notified_users = set()

    recipients = []
    if task.TASK_CREATED and task.TASK_CREATED != commenter:
        recipients.append(task.TASK_CREATED)
    if task.assigned_to and task.assigned_to != commenter:
        recipients.append(task.assigned_to)

    for user in recipients:
        if user.id in notified_users:
            continue
        notifications.append(create_notification(
            user=user,
            notification_type='TASK_COMMENTED',
            title=f'New comment on "{task.TASK_TITLE}"',
            message=f'{commenter.username} commented: {comment_text[:100]}',
            task=task,
            extra_data={'commenter': commenter.username},
        ))
        notified_users.add(user.id)

    return notifications


def notify_task_rated(task, rating):
    if not task.assigned_to:
        return None

    stars  = '⭐' * rating.rating
    return create_notification(
        user=task.assigned_to,
        notification_type='SYSTEM',
        title=f'Task rated {stars}',
        message=f'"{task.TASK_TITLE}" received a {rating.rating}-star rating.',
        task=task,
        extra_data={
            'rating':   rating.rating,
            'feedback': rating.feedback[:200] if rating.feedback else '',
        },
    )


