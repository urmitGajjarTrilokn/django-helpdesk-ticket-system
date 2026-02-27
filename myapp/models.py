from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from datetime import timedelta

class Department(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    code        = models.CharField(max_length=10, unique=True,
                                   help_text="Short code (e.g., IT, HR, FIN)")
    email       = models.EmailField(blank=True, help_text="Department contact email")
    is_active   = models.BooleanField(default=True)
    color       = models.CharField(max_length=7, default='#3b82f6',
                                   help_text="Hex color code for UI")
    icon        = models.CharField(max_length=50, default='fas fa-building',
                                   help_text="FontAwesome icon class")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, related_name='departments_created')

    class Meta:
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return self.name

    def get_active_members_count(self):
        return self.departmentmember_set.filter(is_active=True).count()

    def get_open_tickets_count(self):
        return self.department_tasks.filter(TASK_STATUS='Open').count()

class DepartmentMember(models.Model):
    ROLE_CHOICES = [
        ('MEMBER',  'Member'),
        ('LEAD',    'Team Lead'),
        ('MANAGER', 'Manager'),
        ('HEAD',    'Department Head'),
    ]

    user                = models.ForeignKey(User, on_delete=models.CASCADE,
                                            related_name='department_memberships')
    department          = models.ForeignKey(Department, on_delete=models.CASCADE)
    role                = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    is_active           = models.BooleanField(default=True)
    can_assign_tickets  = models.BooleanField(default=False)
    can_close_tickets   = models.BooleanField(default=True)
    can_delete_tickets  = models.BooleanField(default=False)
    joined_at           = models.DateTimeField(auto_now_add=True)
    added_by            = models.ForeignKey(User, on_delete=models.SET_NULL,
                                            null=True, related_name='members_added')

    class Meta:
        unique_together = ['user', 'department']
        ordering = ['department', '-role', 'user__username']
        verbose_name = 'Department Member'
        verbose_name_plural = 'Department Members'

    def __str__(self):
        return f"{self.user.username} - {self.department.name} ({self.get_role_display()})"

    def is_manager_or_above(self):
        return self.role in ['MANAGER', 'HEAD']

class UserProfile(models.Model):
    user  = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    Address       = models.CharField(max_length=100, blank=True)
    City          = models.CharField(max_length=100, blank=True)
    State         = models.CharField(max_length=100, blank=True)
    Profile_Image = models.ImageField(null=True, blank=True, upload_to="images/")

    DEPARTMENT_CHOICES = [
        ('FIN', 'Finance'),
        ('IT',  'IT Support'),
        ('HR',  'HR'),
        ('MGR', 'Manager'),
        ('CS',  'Customer Support'),
        ('OPS', 'Operations'),
    ]
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES,
                                  null=True, blank=True,
                                  help_text="Deprecated — use DepartmentMember")

    phone                = models.CharField(max_length=15, blank=True)
    email_notifications  = models.BooleanField(default=True)
    created_at           = models.DateTimeField(auto_now_add=True, null=True)
    updated_at           = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} profile"

    def get_departments(self):
        return Department.objects.filter(
            departmentmember__user=self.user,
            departmentmember__is_active=True
        ).distinct()

class Category(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=50, default='fa-folder')
    color       = models.CharField(max_length=7, default='#007bff')
    is_active   = models.BooleanField(default=True)
    ml_keywords = models.TextField(blank=True,
                                   help_text="Comma-separated keywords for ML")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class SLAPolicy(models.Model):
    name            = models.CharField(max_length=100, unique=True)
    description     = models.TextField(blank=True)
    response_time   = models.IntegerField(help_text="Time to first response (hours)",
                                          validators=[MinValueValidator(1)])
    resolution_time = models.IntegerField(help_text="Time to resolve (hours)",
                                          validators=[MinValueValidator(1)])
    priority = models.CharField(
        max_length=10,
        choices=[('LOW','Low'),('MEDIUM','Medium'),('HIGH','High'),('URGENT','Urgent')],
        null=True, blank=True
    )
    department  = models.ForeignKey('Department', on_delete=models.CASCADE,
                                    null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'response_time']
        verbose_name = "SLA Policy"
        verbose_name_plural = "SLA Policies"

    def __str__(self):
        return f"{self.name} - Response: {self.response_time}h, Resolution: {self.resolution_time}h"

class TaskDetail(models.Model):
    TASK_TITLE       = models.CharField(max_length=100)
    TASK_CREATED     = models.ForeignKey(User, related_name='CREATED_BY',
                                         on_delete=models.CASCADE, null=True)
    TASK_CLOSED      = models.ForeignKey(User, related_name='CLOSED_BY',
                                         on_delete=models.CASCADE, null=True)
    TASK_CREATED_ON  = models.DateField(auto_now_add=True, null=True)
    TASK_DUE_DATE    = models.DateField()
    TASK_CLOSED_ON   = models.DateField(null=True)
    TASK_DESCRIPTION = models.CharField(max_length=300)
    TASK_HOLDER      = models.CharField(max_length=100)

    choice = [
        ('Open', 'Open'), ('In Progress', 'In Progress'),
        ('Closed', 'Closed'), ('Reopen', 'Reopen'),
        ('Expired', 'Expired'), ('Resolved', 'Resolved'),
    ]
    TASK_STATUS = models.CharField(max_length=100, choices=choice, default='Open')

    PRIORITY_CHOICES = [
        ('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('URGENT', 'Urgent'),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES,
                                default='MEDIUM', null=True, blank=True)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='tasks')

    assigned_department = models.ForeignKey(Department, on_delete=models.SET_NULL,
                                            null=True, blank=True,
                                            related_name='department_tasks')

    DEPARTMENT_CHOICES = [
        ('HR','Human Resources'),('TECH','Technical Support'),
        ('ADMIN','Administration'),('SALES','Sales'),
        ('FINANCE','Finance'),('OTHER','Other'),
    ]
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES,
                                  null=True, blank=True,
                                  help_text="Deprecated — use assigned_department")

    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='assigned_tasks')

    ASSIGNMENT_TYPE_CHOICES = [
        ('UNASSIGNED',    'Unassigned'),
        ('AUTO_AI',       'Auto-assigned by AI'),
        ('AUTO_ML',       'Auto-assigned by ML'),
        ('MANUAL',        'Manually Assigned'),
        ('SELF_ASSIGNED', 'Self Assigned'),
    ]
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPE_CHOICES,
                                       default='UNASSIGNED', null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assignments_made')

    updated_at  = models.DateTimeField(auto_now=True, null=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    ai_suggested_category = models.ForeignKey(Category, on_delete=models.SET_NULL,
                                               null=True, blank=True,
                                               related_name='ai_suggested_tasks')
    ai_suggested_priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES,
                                             null=True, blank=True)

    ml_predicted_department = models.ForeignKey(Department, on_delete=models.SET_NULL,
                                                null=True, blank=True,
                                                related_name='ml_predicted_tasks')
    ml_predicted_department_old = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES,
                                                   null=True, blank=True)
    ml_confidence_score  = models.FloatField(null=True, blank=True)
    is_potential_duplicate = models.BooleanField(default=False)
    similar_to           = models.ForeignKey('self', on_delete=models.SET_NULL,
                                             null=True, blank=True)
    views_count          = models.IntegerField(default=0)

    sla_policy               = models.ForeignKey(SLAPolicy, on_delete=models.SET_NULL,
                                                  null=True, blank=True, related_name='tasks')
    sla_response_deadline    = models.DateTimeField(null=True, blank=True)
    sla_resolution_deadline  = models.DateTimeField(null=True, blank=True)
    sla_response_breached    = models.BooleanField(default=False)
    sla_resolution_breached  = models.BooleanField(default=False)
    first_response_at        = models.DateTimeField(null=True, blank=True)

    escalation_level   = models.IntegerField(default=0)
    last_escalated_at  = models.DateTimeField(null=True, blank=True)
    escalated_to       = models.ForeignKey(User, on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           related_name='escalated_tasks')

    class Meta:
        ordering = ['-TASK_CREATED_ON']
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    def __str__(self):
        return f"#{self.id} - {self.TASK_TITLE}"

    def calculate_sla_deadlines(self):
        if not self.sla_policy:
            self.sla_policy = SLAPolicy.objects.filter(
                priority=self.priority, department=self.assigned_department, is_active=True
            ).first() or SLAPolicy.objects.filter(
                priority=self.priority, department__isnull=True, is_active=True
            ).first() or SLAPolicy.objects.filter(
                priority__isnull=True, department__isnull=True, is_active=True
            ).first()

        if self.sla_policy and self.TASK_CREATED_ON:
            if isinstance(self.TASK_CREATED_ON, timezone.datetime):
                created = self.TASK_CREATED_ON
            else:
                created = timezone.make_aware(
                    timezone.datetime.combine(self.TASK_CREATED_ON, timezone.datetime.min.time())
                )
            self.sla_response_deadline   = created + timedelta(hours=self.sla_policy.response_time)
            self.sla_resolution_deadline = created + timedelta(hours=self.sla_policy.resolution_time)
            self.save(update_fields=['sla_policy', 'sla_response_deadline', 'sla_resolution_deadline'])

    def check_sla_breach(self):
        now = timezone.now()
        if not self.first_response_at and self.sla_response_deadline:
            if now > self.sla_response_deadline:
                self.sla_response_breached = True
        if self.TASK_STATUS in ['Open', 'In Progress', 'Reopen'] and self.sla_resolution_deadline:
            if now > self.sla_resolution_deadline:
                self.sla_resolution_breached = True
        if self.sla_response_breached or self.sla_resolution_breached:
            self.save(update_fields=['sla_response_breached', 'sla_resolution_breached'])
            return True
        return False

    @property
    def sla_status(self):
        if not self.sla_resolution_deadline:
            return 'No SLA'
        if self.sla_resolution_breached:
            return 'Breached'
        now = timezone.now()
        hours_remaining = (self.sla_resolution_deadline - now).total_seconds() / 3600
        if hours_remaining < 0:   return 'Breached'
        if hours_remaining < 2:   return 'Critical'
        if hours_remaining < 4:   return 'Warning'
        return 'On Track'

    @property
    def sla_time_remaining(self):
        if not self.sla_resolution_deadline:
            return None
        delta = self.sla_resolution_deadline - timezone.now()
        if delta.total_seconds() < 0:
            return "Overdue"
        hours   = int(delta.total_seconds() / 3600)
        minutes = int((delta.total_seconds() % 3600) / 60)
        if hours > 24:
            return f"{hours // 24}d {hours % 24}h"
        return f"{hours}h {minutes}m"

    @property
    def is_overdue(self):
        if self.TASK_STATUS in ['Closed', 'Resolved']:
            return False
        from datetime import date
        return date.today() > self.TASK_DUE_DATE

    @property
    def days_until_due(self):
        from datetime import date
        return (self.TASK_DUE_DATE - date.today()).days

    def can_be_accepted_by(self, user):
        if user.is_superuser:
            return True
        if self.assigned_department:
            return DepartmentMember.objects.filter(
                user=user, department=self.assigned_department, is_active=True
            ).exists()
        return True

    def assign_to_department(self, department, assigned_by=None, assignment_type='MANUAL'):
        self.assigned_department = department
        self.assignment_type     = assignment_type
        self.assigned_by         = assigned_by
        self.assigned_at         = timezone.now()
        self.save()

    def assign_to_user(self, user, assigned_by=None):
        self.assigned_to  = user
        self.assigned_by  = assigned_by
        self.assigned_at  = timezone.now()
        self.TASK_STATUS  = 'In Progress'
        self.save()

class MyCart(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    task        = models.ForeignKey(TaskDetail, on_delete=models.CASCADE)
    task_count  = models.IntegerField(default=1)
    accepted_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.task.TASK_TITLE}"

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('CREATED',    'Ticket Created'),
        ('ASSIGNED',   'Ticket Assigned'),
        ('RESOLVED',   'Ticket Resolved'),
        ('COMMENTED',  'Comment Added'),
        ('ESCALATED',  'Ticket Escalated'),
        ('REOPENED',   'Ticket Reopened'),
        ('CLOSED',     'Ticket Closed'),
        ('UPDATED',    'Ticket Updated'),
        ('STATUS',     'Status Changed'),
        ('PRIORITY',   'Priority Changed'),
        ('SYSTEM',     'System Event'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    task       = models.ForeignKey(TaskDetail, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='activity_logs')
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES, default='SYSTEM')
    title      = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    old_value  = models.CharField(max_length=200, blank=True)
    new_value  = models.CharField(max_length=200, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['task', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.action} — {self.timestamp:%Y-%m-%d %H:%M}"

    @property
    def time_since(self):
        from django.utils.timesince import timesince
        return timesince(self.timestamp)

    def get_icon(self):
        icons = {
            'CREATED':   'fas fa-plus-circle',
            'ASSIGNED':  'fas fa-user-check',
            'RESOLVED':  'fas fa-check-circle',
            'COMMENTED': 'fas fa-comment',
            'ESCALATED': 'fas fa-arrow-up',
            'REOPENED':  'fas fa-redo',
            'CLOSED':    'fas fa-times-circle',
            'UPDATED':   'fas fa-edit',
            'STATUS':    'fas fa-exchange-alt',
            'PRIORITY':  'fas fa-flag',
            'SYSTEM':    'fas fa-cog',
        }
        return icons.get(self.action, 'fas fa-circle')

    def get_color(self):
        colors = {
            'CREATED':   '#4F46E5',
            'ASSIGNED':  '#0EA5E9',
            'RESOLVED':  '#10B981',
            'COMMENTED': '#6366F1',
            'ESCALATED': '#EF4444',
            'REOPENED':  '#F59E0B',
            'CLOSED':    '#64748B',
            'UPDATED':   '#8B5CF6',
            'STATUS':    '#F59E0B',
            'PRIORITY':  '#DC2626',
            'SYSTEM':    '#94A3B8',
        }
        return colors.get(self.action, '#94A3B8')

class UserComment(models.Model):
    user            = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    task            = models.ForeignKey(TaskDetail, related_name='comments',
                                        on_delete=models.CASCADE, null=True, blank=True)
    Closing_comment = models.TextField(null=True, blank=True)
    Reopen_comment  = models.TextField(null=True, blank=True)
    TextFile        = models.FileField(upload_to='accepted_attachments/', null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.username if self.user else 'Unknown'}"

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('TASK_CREATED',       'Task Created'),
        ('TASK_ASSIGNED',      'Task Assigned'),
        ('TASK_ACCEPTED',      'Task Accepted'),
        ('TASK_UPDATED',       'Task Updated'),
        ('TASK_CLOSED',        'Task Closed'),
        ('TASK_RESOLVED',      'Task Resolved'),
        ('TASK_REOPENED',      'Task Reopened'),
        ('TASK_COMMENTED',     'Task Commented'),
        ('TASK_OVERDUE',       'Task Overdue'),
        ('DEPARTMENT_ASSIGNED','Department Assigned'),
        ('MENTION',            'Mentioned in Task'),
        ('SYSTEM',             'System Notification'),
    )

    user              = models.ForeignKey(User, on_delete=models.CASCADE,
                                          related_name='notifications')
    task              = models.ForeignKey('TaskDetail', on_delete=models.CASCADE,
                                          null=True, blank=True, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES,
                                         default='SYSTEM')
    title             = models.CharField(max_length=200, blank=True)
    message           = models.TextField()
    extra_data        = models.JSONField(default=dict, blank=True)
    is_read           = models.BooleanField(default=False, db_index=True)
    read_at           = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True, db_index=True)
    email_sent        = models.BooleanField(default=False)
    email_sent_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.notification_type}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def mark_as_unread(self):
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=['is_read', 'read_at'])

    def get_icon(self):
        icons = {
            'TASK_CREATED':        'fas fa-plus-circle',
            'TASK_ASSIGNED':       'fas fa-user-check',
            'TASK_ACCEPTED':       'fas fa-hand-holding',
            'TASK_UPDATED':        'fas fa-edit',
            'TASK_CLOSED':         'fas fa-times-circle',
            'TASK_RESOLVED':       'fas fa-check-circle',
            'TASK_REOPENED':       'fas fa-redo',
            'TASK_COMMENTED':      'fas fa-comment',
            'TASK_OVERDUE':        'fas fa-exclamation-triangle',
            'DEPARTMENT_ASSIGNED': 'fas fa-building',
            'MENTION':             'fas fa-at',
            'SYSTEM':              'fas fa-bell',
        }
        return icons.get(self.notification_type, 'fas fa-bell')

    def get_color_class(self):
        colors = {
            'TASK_CREATED':        'primary',
            'TASK_ASSIGNED':       'info',
            'TASK_ACCEPTED':       'success',
            'TASK_UPDATED':        'warning',
            'TASK_CLOSED':         'secondary',
            'TASK_RESOLVED':       'success',
            'TASK_REOPENED':       'warning',
            'TASK_COMMENTED':      'info',
            'TASK_OVERDUE':        'danger',
            'DEPARTMENT_ASSIGNED': 'primary',
            'MENTION':             'info',
            'SYSTEM':              'secondary',
        }
        return colors.get(self.notification_type, 'secondary')

    def get_url(self):
        if self.task:
            from django.urls import reverse
            return reverse('taskinfo', kwargs={'pk': self.task.id})
        return '#'

    @property
    def time_since(self):
        from django.utils.timesince import timesince
        return timesince(self.created_at)

class KnowledgeBase(models.Model):
    title       = models.CharField(max_length=200)
    content     = models.TextField()
    category    = models.ForeignKey(Category, on_delete=models.CASCADE,
                                    related_name='kb_articles', null=True, blank=True)
    keywords    = models.TextField(help_text="Comma-separated keywords")
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    views       = models.IntegerField(default=0)
    helpful_count = models.IntegerField(default=0)
    is_published  = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Knowledge Base Article"
        verbose_name_plural = "Knowledge Base"

    def __str__(self):
        return self.title

class AIMLLog(models.Model):
    TYPE_CHOICES = [
        ('CHATBOT',    'AI Chatbot'),
        ('CATEGORY',   'Category Suggestion'),
        ('PRIORITY',   'Priority Suggestion'),
        ('DEPARTMENT', 'Department Assignment'),
        ('DUPLICATE',  'Duplicate Detection'),
    ]
    task        = models.ForeignKey(TaskDetail, on_delete=models.CASCADE, related_name='ai_logs')
    log_type    = models.CharField(max_length=20, choices=TYPE_CHOICES)
    input_data  = models.TextField()
    output_data = models.TextField()
    confidence  = models.FloatField(null=True, blank=True)
    was_correct = models.BooleanField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "AI/ML Log"
        verbose_name_plural = "AI/ML Logs"

    def __str__(self):
        return f"{self.log_type} - Task #{self.task.id}"

class EscalationRule(models.Model):
    name         = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=20, choices=[
        ('SLA_BREACH',    'SLA Breach'),
        ('TIME_BASED',    'Time Based'),
        ('STATUS_BASED',  'Status Based'),
        ('PRIORITY_BASED','Priority Based'),
    ], default='SLA_BREACH')
    hours_threshold  = models.IntegerField(null=True, blank=True)
    priority         = models.CharField(max_length=10, choices=[
        ('LOW','Low'),('MEDIUM','Medium'),('HIGH','High'),('URGENT','Urgent'),
    ], null=True, blank=True)
    department       = models.ForeignKey('Department', on_delete=models.CASCADE,
                                         null=True, blank=True)
    escalate_to_role = models.CharField(max_length=20, choices=[
        ('LEAD','Team Lead'),('MANAGER','Manager'),('HEAD','Department Head'),
    ], default='LEAD')
    send_notification = models.BooleanField(default=True)
    is_active         = models.BooleanField(default=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority', '-hours_threshold']
        verbose_name = "Escalation Rule"
        verbose_name_plural = "Escalation Rules"

    def __str__(self):
        return f"{self.name} - {self.get_trigger_type_display()}"


class TaskEscalation(models.Model):
    task             = models.ForeignKey('TaskDetail', on_delete=models.CASCADE,
                                         related_name='escalations')
    escalation_level = models.IntegerField()
    escalated_from   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                         null=True, related_name='escalations_from')
    escalated_to     = models.ForeignKey(User, on_delete=models.SET_NULL,
                                         null=True, related_name='escalations_to')
    reason           = models.CharField(max_length=200)
    escalation_rule  = models.ForeignKey(EscalationRule, on_delete=models.SET_NULL,
                                         null=True, blank=True)
    is_auto_escalated = models.BooleanField(default=True)
    escalated_at      = models.DateTimeField(auto_now_add=True)
    notes             = models.TextField(blank=True)

    class Meta:
        ordering = ['-escalated_at']
        verbose_name = "Task Escalation"
        verbose_name_plural = "Task Escalations"

    def __str__(self):
        return f"Task #{self.task.id} - Level {self.escalation_level}"

class TaskHistory(models.Model):
    task       = models.ForeignKey('TaskDetail', on_delete=models.CASCADE,
                                   related_name='history')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action_type = models.CharField(max_length=50, choices=[
        ('CREATED',          'Created'),
        ('UPDATED',          'Updated'),
        ('ASSIGNED',         'Assigned'),
        ('STATUS_CHANGED',   'Status Changed'),
        ('PRIORITY_CHANGED', 'Priority Changed'),
        ('COMMENTED',        'Commented'),
        ('ESCALATED',        'Escalated'),
        ('SLA_BREACHED',     'SLA Breached'),
        ('CLOSED',           'Closed'),
        ('REOPENED',         'Reopened'),
    ])
    field_name  = models.CharField(max_length=100, blank=True)
    old_value   = models.TextField(blank=True)
    new_value   = models.TextField(blank=True)
    description = models.TextField(blank=True)
    changed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Task History"
        verbose_name_plural = "Task History"
        indexes = [models.Index(fields=['task', '-changed_at'])]

    def __str__(self):
        return f"Task #{self.task.id} - {self.action_type} by {self.changed_by}"

class CannedResponse(models.Model):
    title      = models.CharField(max_length=200)
    content    = models.TextField(help_text="Use {{task_id}}, {{user_name}}, {{task_title}}")
    category   = models.ForeignKey('Category', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='canned_responses')
    department = models.ForeignKey('Department', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='canned_responses')
    is_public  = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='canned_responses_created')
    usage_count = models.IntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-usage_count', 'title']
        verbose_name = "Canned Response"
        verbose_name_plural = "Canned Responses"

    def __str__(self):
        return self.title

    def render(self, context):
        content = self.content
        for key, value in context.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
        return content

    def increment_usage(self):
        self.usage_count += 1
        self.save(update_fields=['usage_count'])


class TaskRating(models.Model):
    task    = models.OneToOneField('TaskDetail', on_delete=models.CASCADE, related_name='rating')
    rated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    rating  = models.IntegerField(choices=[
        (1,'⭐ Very Dissatisfied'),(2,'⭐⭐ Dissatisfied'),
        (3,'⭐⭐⭐ Neutral'),(4,'⭐⭐⭐⭐ Satisfied'),(5,'⭐⭐⭐⭐⭐ Very Satisfied'),
    ])
    feedback             = models.TextField(blank=True)
    resolution_quality   = models.IntegerField(choices=[(i,str(i)) for i in range(1,6)],
                                               null=True, blank=True)
    response_time_rating = models.IntegerField(choices=[(i,str(i)) for i in range(1,6)],
                                               null=True, blank=True)
    agent_helpfulness    = models.IntegerField(choices=[(i,str(i)) for i in range(1,6)],
                                               null=True, blank=True)
    rated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-rated_at']
        verbose_name = "Task Rating"
        verbose_name_plural = "Task Ratings"

    def __str__(self):
        return f"Task #{self.task.id} - {self.rating}⭐ by {self.rated_by.username}"

@receiver(post_migrate)
def create_default_departments(sender, **kwargs):
    if sender.name != 'myapp':
        return
    defaults = [
        {'name':'Finance',          'code':'FIN', 'color':'#10b981','icon':'fas fa-dollar-sign',
         'description':'Handles billing, payments and financial queries',
         'email':'finance@helpdesk.com'},
        {'name':'IT Support',       'code':'IT',  'color':'#3b82f6','icon':'fas fa-laptop-code',
         'description':'Handles technical issues, software problems and network troubleshooting',
         'email':'it@helpdesk.com'},
        {'name':'HR',               'code':'HR',  'color':'#8b5cf6','icon':'fas fa-users',
         'description':'Handles employee relations, payroll and HR policies',
         'email':'hr@helpdesk.com'},
        {'name':'Manager',          'code':'MGR', 'color':'#6366f1','icon':'fas fa-user-tie',
         'description':'Handles management-level approvals and escalations',
         'email':'manager@helpdesk.com'},
        {'name':'Customer Support', 'code':'CS',  'color':'#06b6d4','icon':'fas fa-headset',
         'description':'Handles customer queries, complaints and general support',
         'email':'support@helpdesk.com'},
        {'name':'Operations',       'code':'OPS', 'color':'#f59e0b','icon':'fas fa-cogs',
         'description':'Handles facility management, logistics and procurement',
         'email':'operations@helpdesk.com'},
    ]
    created = 0
    updated = 0
    for d in defaults:
        _, was_created = Department.objects.update_or_create(
            code=d['code'],
            defaults=d,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    if created or updated:
        print(f"Departments seeded: created={created}, updated={updated}")


@receiver(post_migrate)
def create_default_categories(sender, **kwargs):
    if sender.name != 'myapp':
        return
    defaults = [
        {'name':'Bug Report',      'icon':'fa-bug',            'color':'#dc3545',
         'ml_keywords':'bug,error,crash,not working,broken,issue,problem,fail',
         'description':'Software bugs and technical issues that need fixing'},
        {'name':'Feature Request', 'icon':'fa-lightbulb',      'color':'#0dcaf0',
         'ml_keywords':'feature,enhancement,improvement,new,add,request,suggestion',
         'description':'New feature suggestions and enhancements'},
        {'name':'Support',         'icon':'fa-question-circle','color':'#ffc107',
         'ml_keywords':'help,support,how to,question,guide,tutorial,assistance',
         'description':'User support and help requests'},
        {'name':'Maintenance',     'icon':'fa-tools',          'color':'#6c757d',
         'ml_keywords':'maintenance,update,upgrade,patch,system,server',
         'description':'System maintenance and updates'},
        {'name':'Documentation',   'icon':'fa-book',           'color':'#0d6efd',
         'ml_keywords':'documentation,docs,readme,guide,manual,instructions',
         'description':'Documentation related tasks and improvements'},
        {'name':'Security',        'icon':'fa-shield-alt',     'color':'#d63384',
         'ml_keywords':'security,vulnerability,permission,access,password,authentication',
         'description':'Security issues, vulnerabilities and access control'},
    ]
    created = sum(
        1 for d in defaults
        if Category.objects.get_or_create(name=d['name'], defaults=d)[1]
    )
    if created:
        print(f"Created {created} categories")
