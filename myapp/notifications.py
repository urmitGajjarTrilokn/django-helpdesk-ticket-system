from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

from .models import Notification, DepartmentMember

def create_notification(user, notification_type, title, message, ticket=None, extra_data=None):
    notification = Notification.objects.create(
        user=user,
        ticket=ticket,
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
            'ticket':         notification.ticket,
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


def notify_ticket_created(ticket):
    notifications = []

    if not ticket.assigned_department:
        return notifications

    members = DepartmentMember.objects.filter(
        department=ticket.assigned_department,
        is_active=True,
    ).exclude(user=ticket.TICKET_CREATED)

    for member in members:
        notifications.append(create_notification(
            user=member.user,
            notification_type='TICKET_CREATED',
            title=f'New ticket in {ticket.assigned_department.name}',
            message=f'{ticket.TICKET_CREATED.username} created ticket "{ticket.TICKET_TITLE}"',
            ticket=ticket,
            extra_data={'department': ticket.assigned_department.name, 'priority': ticket.priority},
        ))

    return notifications


def notify_ticket_assigned(ticket, assigned_to, assigned_by):
    if assigned_to == assigned_by:
        return None

    return create_notification(
        user=assigned_to,
        notification_type='TICKET_ASSIGNED',
        title='Ticket assigned to you',
        message=f'{assigned_by.username} assigned you ticket "{ticket.TICKET_TITLE}"',
        ticket=ticket,
        extra_data={'assigned_by': assigned_by.username, 'priority': ticket.priority},
    )


def notify_ticket_accepted(ticket, accepted_by):
    if ticket.TICKET_CREATED == accepted_by:
        return None

    return create_notification(
        user=ticket.TICKET_CREATED,
        notification_type='TICKET_ACCEPTED',
        title='Your ticket was accepted',
        message=f'{accepted_by.username} accepted your ticket "{ticket.TICKET_TITLE}"',
        ticket=ticket,
        extra_data={'accepted_by': accepted_by.username},
    )


def notify_ticket_updated(ticket, updated_by, changes=None):
    if ticket.TICKET_CREATED == updated_by:
        return None

    return create_notification(
        user=ticket.TICKET_CREATED,
        notification_type='TICKET_UPDATED',
        title='Ticket updated',
        message=f'{updated_by.username} updated ticket "{ticket.TICKET_TITLE}"',
        ticket=ticket,
        extra_data={'updated_by': updated_by.username, 'changes': changes or []},
    )


def notify_ticket_closed(ticket, closed_by):
    if ticket.TICKET_CREATED == closed_by:
        return None

    return create_notification(
        user=ticket.TICKET_CREATED,
        notification_type='TICKET_CLOSED',
        title='Your ticket was closed',
        message=f'{closed_by.username} closed ticket "{ticket.TICKET_TITLE}"',
        ticket=ticket,
        extra_data={'closed_by': closed_by.username},
    )


def notify_ticket_resolved(ticket, resolved_by):
    if ticket.TICKET_CREATED == resolved_by:
        return None

    return create_notification(
        user=ticket.TICKET_CREATED,
        notification_type='TICKET_RESOLVED',
        title='Your ticket has been resolved',
        message=f'{resolved_by.username} resolved ticket "{ticket.TICKET_TITLE}"',
        ticket=ticket,
        extra_data={'resolved_by': resolved_by.username},
    )


def notify_ticket_reopened(ticket, reopened_by, reason=None):
    if not ticket.TICKET_CLOSED or ticket.TICKET_CLOSED == reopened_by:
        return None

    return create_notification(
        user=ticket.TICKET_CLOSED,
        notification_type='TICKET_REOPENED',
        title='Ticket reopened',
        message=f'{reopened_by.username} reopened ticket "{ticket.TICKET_TITLE}"',
        ticket=ticket,
        extra_data={'reopened_by': reopened_by.username, 'reason': reason or ''},
    )


def notify_ticket_commented(ticket, commenter, comment_text=''):
    notifications = []
    notified_users = set()

    recipients = []
    if ticket.TICKET_CREATED and ticket.TICKET_CREATED != commenter:
        recipients.append(ticket.TICKET_CREATED)
    if ticket.assigned_to and ticket.assigned_to != commenter:
        recipients.append(ticket.assigned_to)

    for user in recipients:
        if user.id in notified_users:
            continue
        notifications.append(create_notification(
            user=user,
            notification_type='TICKET_COMMENTED',
            title=f'New comment on "{ticket.TICKET_TITLE}"',
            message=f'{commenter.username} commented: {comment_text[:100]}',
            ticket=ticket,
            extra_data={'commenter': commenter.username},
        ))
        notified_users.add(user.id)

    return notifications


def notify_ticket_rated(ticket, rating):
    if not ticket.assigned_to:
        return None

    stars  = '⭐' * rating.rating
    return create_notification(
        user=ticket.assigned_to,
        notification_type='SYSTEM',
        title=f'Ticket rated {stars}',
        message=f'"{ticket.TICKET_TITLE}" received a {rating.rating}-star rating.',
        ticket=ticket,
        extra_data={
            'rating':   rating.rating,
            'feedback': rating.feedback[:200] if rating.feedback else '',
        },
    )


