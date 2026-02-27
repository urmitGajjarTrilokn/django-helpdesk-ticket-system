from django.db.models import Count, Avg, Q, F, Sum
from django.utils import timezone
from datetime import timedelta, datetime, date
from collections import defaultdict
from .models import TaskDetail, Department, DepartmentMember, ActivityLog, TaskHistory
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

def get_date_range(range_type='30_days'):
    today = date.today()

    if range_type == '7_days':
        return today - timedelta(days=7), today
    if range_type == '30_days':
        return today - timedelta(days=30), today
    if range_type == '90_days':
        return today - timedelta(days=90), today
    if range_type == 'this_month':
        return today.replace(day=1), today
    if range_type == 'last_month':
        last = today.replace(day=1) - timedelta(days=1)
        return last.replace(day=1), last
    if range_type == 'this_year':
        return today.replace(month=1, day=1), today
    return today - timedelta(days=30), today

def get_task_statistics(start_date=None, end_date=None, department=None):
    try:
        tasks = TaskDetail.objects.all()

        if start_date and end_date:
            tasks = tasks.filter(TASK_CREATED_ON__range=[start_date, end_date])
        if department:
            tasks = tasks.filter(assigned_department=department)

        stats = {
            'total':       tasks.count(),
            'open':        tasks.filter(TASK_STATUS='Open').count(),
            'in_progress': tasks.filter(TASK_STATUS='In Progress').count(),
            'closed':      tasks.filter(TASK_STATUS='Closed').count(),
            'resolved':    tasks.filter(TASK_STATUS='Resolved').count(),
        }
        stats['by_priority'] = {
            'urgent': tasks.filter(priority='URGENT').count(),
            'high':   tasks.filter(priority='HIGH').count(),
            'medium': tasks.filter(priority='MEDIUM').count(),
            'low':    tasks.filter(priority='LOW').count(),
        }

        completed = stats['closed'] + stats['resolved']
        stats['completion_rate'] = (
            completed / stats['total'] * 100 if stats['total'] > 0 else 0
        )

        resolved_tasks = tasks.filter(
            TASK_STATUS__in=['Closed', 'Resolved'],
            TASK_CLOSED_ON__isnull=False,
        )
        total_days = count = 0
        for task in resolved_tasks:
            if task.TASK_CLOSED_ON and task.TASK_CREATED_ON:
                total_days += (task.TASK_CLOSED_ON - task.TASK_CREATED_ON).days
                count += 1
        stats['avg_resolution_hours'] = round(total_days / count * 24, 2) if count else 0

        return stats
    except Exception as e:
        logger.error(f"get_task_statistics error: {e}")
        return {
            'total': 0, 'open': 0, 'in_progress': 0, 'closed': 0,
            'resolved': 0, 'completion_rate': 0, 'avg_resolution_hours': 0,
            'by_priority': {'urgent': 0, 'high': 0, 'medium': 0, 'low': 0},
        }

def get_tasks_over_time(start_date=None, end_date=None, department=None):
    try:
        tasks = TaskDetail.objects.all()
        if start_date and end_date:
            tasks = tasks.filter(TASK_CREATED_ON__range=[start_date, end_date])
        if department:
            tasks = tasks.filter(assigned_department=department)

        tasks_by_date = tasks.values('TASK_CREATED_ON').annotate(
            count=Count('id')
        ).order_by('TASK_CREATED_ON')
        count_map = {
            item['TASK_CREATED_ON']: item['count']
            for item in tasks_by_date
            if item['TASK_CREATED_ON'] is not None
        }

        if not start_date or not end_date:
            return [
                {'date': str(d), 'count': c}
                for d, c in sorted(count_map.items(), key=lambda x: x[0])
            ]

        series = []
        day = start_date
        while day <= end_date:
            series.append({
                'date': day.strftime('%b %d'),
                'count': count_map.get(day, 0),
            })
            day += timedelta(days=1)
        return series
    except Exception as e:
        logger.error(f"get_tasks_over_time error: {e}")
        return []

def get_department_statistics(start_date=None, end_date=None):
    try:
        departments = Department.objects.filter(is_active=True)
        result = []

        for dept in departments:
            tasks = TaskDetail.objects.filter(assigned_department=dept)
            if start_date and end_date:
                tasks = tasks.filter(TASK_CREATED_ON__range=[start_date, end_date])

            total  = tasks.count()
            closed = tasks.filter(TASK_STATUS__in=['Closed', 'Resolved']).count()
            open_t = tasks.filter(TASK_STATUS='Open').count()

            total_days = count = 0
            for task in tasks.filter(TASK_STATUS__in=['Closed','Resolved'], TASK_CLOSED_ON__isnull=False):
                if task.TASK_CLOSED_ON and task.TASK_CREATED_ON:
                    total_days += (task.TASK_CLOSED_ON - task.TASK_CREATED_ON).days
                    count += 1

            result.append({
                'name':                  dept.name,
                'color':                 dept.color,
                'total_tasks':           total,
                'open_tasks':            open_t,
                'closed_tasks':          closed,
                'completion_rate':       round(closed / total * 100, 2) if total else 0,
                'avg_resolution_hours':  round(total_days / count * 24, 2) if count else 0,
                'members_count':         dept.get_active_members_count(),
            })

        return result
    except Exception as e:
        logger.error(f"get_department_statistics error: {e}")
        return []


def get_department_comparison():
    try:
        departments = Department.objects.filter(is_active=True)
        result = {
            'labels':      [],
            'total_tasks': [],
            'open_tasks':  [],
            'closed_tasks':[],
            'colors':      [],
        }
        for dept in departments:
            tasks = TaskDetail.objects.filter(assigned_department=dept)
            result['labels'].append(dept.name)
            result['total_tasks'].append(tasks.count())
            result['open_tasks'].append(tasks.filter(TASK_STATUS='Open').count())
            result['closed_tasks'].append(tasks.filter(TASK_STATUS__in=['Closed','Resolved']).count())
            result['colors'].append(dept.color)
        return result
    except Exception as e:
        logger.error(f"get_department_comparison error: {e}")
        return {'labels': [], 'total_tasks': [], 'open_tasks': [], 'closed_tasks': [], 'colors': []}

def get_top_task_creators(limit=10, start_date=None, end_date=None):
    try:
        tasks = TaskDetail.objects.filter(TASK_CREATED__isnull=False)
        if start_date and end_date:
            tasks = tasks.filter(TASK_CREATED_ON__range=[start_date, end_date])

        top = tasks.values('TASK_CREATED__username', 'TASK_CREATED__id').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        result = []
        for item in top:
            try:
                user = User.objects.get(id=item['TASK_CREATED__id'])
                result.append({'user': user, 'username': item['TASK_CREATED__username'],
                               'count': item['count']})
            except User.DoesNotExist:
                pass
        return result
    except Exception as e:
        logger.error(f"get_top_task_creators error: {e}")
        return []


def get_top_task_resolvers(limit=10, start_date=None, end_date=None):
    try:
        resolver_events = TaskHistory.objects.filter(
            changed_by__isnull=False
        ).filter(
            Q(action_type='CLOSED') |
            Q(action_type='STATUS_CHANGED', new_value='Resolved')
        )
        if start_date and end_date:
            resolver_events = resolver_events.filter(changed_at__range=[start_date, end_date])

        top = resolver_events.values('changed_by__username', 'changed_by__id').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        result = []
        for item in top:
            try:
                user = User.objects.get(id=item['changed_by__id'])
                resolved_task_ids = resolver_events.filter(
                    changed_by=user
                ).values_list('task_id', flat=True).distinct()
                user_tasks = TaskDetail.objects.filter(
                    id__in=resolved_task_ids
                )
                total_days = count = 0
                for t in user_tasks:
                    completed_on = t.resolved_at or t.TASK_CLOSED_ON
                    if completed_on and t.TASK_CREATED_ON:
                        total_days += (completed_on - t.TASK_CREATED_ON).days
                        count += 1
                avg_hours = round(total_days / count * 24, 2) if count else 0
                result.append({
                    'user':                user,
                    'username':            item['changed_by__username'],
                    'count':               item['count'],
                    'avg_resolution_hours':avg_hours,
                })
            except User.DoesNotExist:
                pass
        return result
    except Exception as e:
        logger.error(f"get_top_task_resolvers error: {e}")
        return []

def get_priority_distribution(start_date=None, end_date=None, department=None):
    try:
        tasks = TaskDetail.objects.all()
        if start_date and end_date:
            tasks = tasks.filter(TASK_CREATED_ON__range=[start_date, end_date])
        if department:
            tasks = tasks.filter(assigned_department=department)
        return {
            'URGENT': tasks.filter(priority='URGENT').count(),
            'HIGH':   tasks.filter(priority='HIGH').count(),
            'MEDIUM': tasks.filter(priority='MEDIUM').count(),
            'LOW':    tasks.filter(priority='LOW').count(),
        }
    except Exception as e:
        logger.error(f"get_priority_distribution error: {e}")
        return {'URGENT': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}


def get_category_distribution(start_date=None, end_date=None):
    try:
        tasks = TaskDetail.objects.filter(category__isnull=False)
        if start_date and end_date:
            tasks = tasks.filter(TASK_CREATED_ON__range=[start_date, end_date])
        cats = tasks.values(
            'category__name', 'category__color', 'category__icon'
        ).annotate(count=Count('id')).order_by('-count')
        return [
            {'name': c['category__name'], 'count': c['count'],
             'color': c['category__color'], 'icon': c['category__icon']}
            for c in cats
        ]
    except Exception as e:
        logger.error(f"get_category_distribution error: {e}")
        return []


def get_sla_compliance(start_date=None, end_date=None):
    try:
        tasks = TaskDetail.objects.filter(
            TASK_STATUS__in=['Closed', 'Resolved'],
            TASK_DUE_DATE__isnull=False,
            TASK_CLOSED_ON__isnull=False,
        )
        if start_date and end_date:
            tasks = tasks.filter(TASK_CLOSED_ON__range=[start_date, end_date])

        total = tasks.count()
        if total == 0:
            return {'total': 0, 'on_time': 0, 'overdue': 0, 'compliance_rate': 0}

        on_time = overdue = 0
        for task in tasks:
            if task.TASK_CLOSED_ON <= task.TASK_DUE_DATE:
                on_time += 1
            else:
                overdue += 1

        return {
            'total':           total,
            'on_time':         on_time,
            'overdue':         overdue,
            'compliance_rate': round(on_time / total * 100, 2),
        }
    except Exception as e:
        logger.error(f"get_sla_compliance error: {e}")
        return {'total': 0, 'on_time': 0, 'overdue': 0, 'compliance_rate': 0}

def get_top_active_users(limit=10, start_date=None, end_date=None):
    
    try:
        logs = ActivityLog.objects.all()
        if start_date and end_date:
            logs = logs.filter(timestamp__date__range=[start_date, end_date])

        top = logs.values('user__username', 'user__id').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        result = []
        for item in top:
            try:
                user = User.objects.get(id=item['user__id'])
                result.append({'user': user, 'username': item['user__username'],
                               'count': item['count']})
            except User.DoesNotExist:
                pass
        return result
    except Exception as e:
        logger.error(f"get_top_active_users error: {e}")
        return []

def prepare_export_data(start_date, end_date, department=None):
    try:
        return {
            'date_range':           f"{start_date} to {end_date}",
            'generated_at':         timezone.now(),
            'statistics':           get_task_statistics(start_date, end_date, department),
            'department_stats':     get_department_statistics(start_date, end_date),
            'priority_distribution':get_priority_distribution(start_date, end_date, department),
            'category_distribution':get_category_distribution(start_date, end_date),
            'top_creators':         get_top_task_creators(10, start_date, end_date),
            'top_resolvers':        get_top_task_resolvers(10, start_date, end_date),
            'sla_compliance':       get_sla_compliance(start_date, end_date),
        }
    except Exception as e:
        logger.error(f"prepare_export_data error: {e}")
        return {}
