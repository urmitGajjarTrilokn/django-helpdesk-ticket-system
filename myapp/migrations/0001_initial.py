                                                

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                ("icon", models.CharField(default="fa-folder", max_length=50)),
                ("color", models.CharField(default="#007bff", max_length=7)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "ml_keywords",
                    models.TextField(
                        blank=True, help_text="Comma-separated keywords for ML"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Category",
                "verbose_name_plural": "Categories",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Department",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "code",
                    models.CharField(
                        help_text="Short code (e.g., IT, HR, FIN)",
                        max_length=10,
                        unique=True,
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, help_text="Department contact email", max_length=254
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "color",
                    models.CharField(
                        default="#3b82f6",
                        help_text="Hex color code for UI",
                        max_length=7,
                    ),
                ),
                (
                    "icon",
                    models.CharField(
                        default="fas fa-building",
                        help_text="FontAwesome icon class",
                        max_length=50,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="departments_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Department",
                "verbose_name_plural": "Departments",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="EscalationRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                (
                    "trigger_type",
                    models.CharField(
                        choices=[
                            ("SLA_BREACH", "SLA Breach"),
                            ("TIME_BASED", "Time Based"),
                            ("STATUS_BASED", "Status Based"),
                            ("PRIORITY_BASED", "Priority Based"),
                        ],
                        default="SLA_BREACH",
                        max_length=20,
                    ),
                ),
                ("hours_threshold", models.IntegerField(blank=True, null=True)),
                (
                    "priority",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("URGENT", "Urgent"),
                        ],
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    "escalate_to_role",
                    models.CharField(
                        choices=[
                            ("LEAD", "Team Lead"),
                            ("MANAGER", "Manager"),
                            ("HEAD", "Department Head"),
                        ],
                        default="LEAD",
                        max_length=20,
                    ),
                ),
                ("send_notification", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="myapp.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "Escalation Rule",
                "verbose_name_plural": "Escalation Rules",
                "ordering": ["priority", "-hours_threshold"],
            },
        ),
        migrations.CreateModel(
            name="SLAPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "response_time",
                    models.IntegerField(
                        help_text="Time to first response (hours)",
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "resolution_time",
                    models.IntegerField(
                        help_text="Time to resolve (hours)",
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("URGENT", "Urgent"),
                        ],
                        max_length=10,
                        null=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="myapp.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "SLA Policy",
                "verbose_name_plural": "SLA Policies",
                "ordering": ["priority", "response_time"],
            },
        ),
        migrations.CreateModel(
            name="TaskDetail",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("TASK_TITLE", models.CharField(max_length=100)),
                ("TASK_CREATED_ON", models.DateField(auto_now_add=True, null=True)),
                ("TASK_DUE_DATE", models.DateField()),
                ("TASK_CLOSED_ON", models.DateField(null=True)),
                ("TASK_DESCRIPTION", models.CharField(max_length=300)),
                ("TASK_HOLDER", models.CharField(max_length=100)),
                (
                    "TASK_STATUS",
                    models.CharField(
                        choices=[
                            ("Open", "Open"),
                            ("In Progress", "In Progress"),
                            ("Closed", "Closed"),
                            ("Reopen", "Reopen"),
                            ("Expired", "Expired"),
                            ("Resolved", "Resolved"),
                        ],
                        default="Open",
                        max_length=100,
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("URGENT", "Urgent"),
                        ],
                        default="MEDIUM",
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    "department",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("HR", "Human Resources"),
                            ("TECH", "Technical Support"),
                            ("ADMIN", "Administration"),
                            ("SALES", "Sales"),
                            ("FINANCE", "Finance"),
                            ("OTHER", "Other"),
                        ],
                        help_text="Deprecated — use assigned_department",
                        max_length=20,
                        null=True,
                    ),
                ),
                (
                    "assignment_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("UNASSIGNED", "Unassigned"),
                            ("AUTO_AI", "Auto-assigned by AI"),
                            ("AUTO_ML", "Auto-assigned by ML"),
                            ("MANUAL", "Manually Assigned"),
                            ("SELF_ASSIGNED", "Self Assigned"),
                        ],
                        default="UNASSIGNED",
                        max_length=20,
                        null=True,
                    ),
                ),
                ("assigned_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "ai_suggested_priority",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LOW", "Low"),
                            ("MEDIUM", "Medium"),
                            ("HIGH", "High"),
                            ("URGENT", "Urgent"),
                        ],
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    "ml_predicted_department_old",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("HR", "Human Resources"),
                            ("TECH", "Technical Support"),
                            ("ADMIN", "Administration"),
                            ("SALES", "Sales"),
                            ("FINANCE", "Finance"),
                            ("OTHER", "Other"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("ml_confidence_score", models.FloatField(blank=True, null=True)),
                ("is_potential_duplicate", models.BooleanField(default=False)),
                ("views_count", models.IntegerField(default=0)),
                ("sla_response_deadline", models.DateTimeField(blank=True, null=True)),
                (
                    "sla_resolution_deadline",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("sla_response_breached", models.BooleanField(default=False)),
                ("sla_resolution_breached", models.BooleanField(default=False)),
                ("first_response_at", models.DateTimeField(blank=True, null=True)),
                ("escalation_level", models.IntegerField(default=0)),
                ("last_escalated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "TASK_CLOSED",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="CLOSED_BY",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "TASK_CREATED",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="CREATED_BY",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ai_suggested_category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_suggested_tasks",
                        to="myapp.category",
                    ),
                ),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assignments_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "assigned_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="department_tasks",
                        to="myapp.department",
                    ),
                ),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tasks",
                        to="myapp.category",
                    ),
                ),
                (
                    "escalated_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="escalated_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ml_predicted_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ml_predicted_tasks",
                        to="myapp.department",
                    ),
                ),
                (
                    "similar_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="myapp.taskdetail",
                    ),
                ),
                (
                    "sla_policy",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tasks",
                        to="myapp.slapolicy",
                    ),
                ),
            ],
            options={
                "verbose_name": "Task",
                "verbose_name_plural": "Tasks",
                "ordering": ["-TASK_CREATED_ON"],
            },
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("Address", models.CharField(blank=True, max_length=100)),
                ("City", models.CharField(blank=True, max_length=100)),
                ("State", models.CharField(blank=True, max_length=100)),
                (
                    "Profile_Image",
                    models.ImageField(blank=True, null=True, upload_to="images/"),
                ),
                (
                    "department",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("FIN", "Finance"),
                            ("IT", "IT Support"),
                            ("HR", "HR"),
                            ("MGR", "Manager"),
                            ("CS", "Customer Support"),
                            ("OPS", "Operations"),
                        ],
                        help_text="Deprecated — use DepartmentMember",
                        max_length=20,
                        null=True,
                    ),
                ),
                ("phone", models.CharField(blank=True, max_length=15)),
                ("email_notifications", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "User Profile",
                "verbose_name_plural": "User Profiles",
            },
        ),
        migrations.CreateModel(
            name="UserComment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("Closing_comment", models.TextField(blank=True, null=True)),
                ("Reopen_comment", models.TextField(blank=True, null=True)),
                (
                    "TextFile",
                    models.FileField(
                        blank=True, null=True, upload_to="accepted_attachments/"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="myapp.taskdetail",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="TaskRating",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "rating",
                    models.IntegerField(
                        choices=[
                            (1, "⭐ Very Dissatisfied"),
                            (2, "⭐⭐ Dissatisfied"),
                            (3, "⭐⭐⭐ Neutral"),
                            (4, "⭐⭐⭐⭐ Satisfied"),
                            (5, "⭐⭐⭐⭐⭐ Very Satisfied"),
                        ]
                    ),
                ),
                ("feedback", models.TextField(blank=True)),
                (
                    "resolution_quality",
                    models.IntegerField(
                        blank=True,
                        choices=[(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")],
                        null=True,
                    ),
                ),
                (
                    "response_time_rating",
                    models.IntegerField(
                        blank=True,
                        choices=[(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")],
                        null=True,
                    ),
                ),
                (
                    "agent_helpfulness",
                    models.IntegerField(
                        blank=True,
                        choices=[(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")],
                        null=True,
                    ),
                ),
                ("rated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "rated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "task",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rating",
                        to="myapp.taskdetail",
                    ),
                ),
            ],
            options={
                "verbose_name": "Task Rating",
                "verbose_name_plural": "Task Ratings",
                "ordering": ["-rated_at"],
            },
        ),
        migrations.CreateModel(
            name="TaskEscalation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("escalation_level", models.IntegerField()),
                ("reason", models.CharField(max_length=200)),
                ("is_auto_escalated", models.BooleanField(default=True)),
                ("escalated_at", models.DateTimeField(auto_now_add=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "escalated_from",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="escalations_from",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "escalated_to",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="escalations_to",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "escalation_rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="myapp.escalationrule",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escalations",
                        to="myapp.taskdetail",
                    ),
                ),
            ],
            options={
                "verbose_name": "Task Escalation",
                "verbose_name_plural": "Task Escalations",
                "ordering": ["-escalated_at"],
            },
        ),
        migrations.CreateModel(
            name="MyCart",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("task_count", models.IntegerField(default=1)),
                ("accepted_at", models.DateTimeField(auto_now_add=True, null=True)),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="myapp.taskdetail",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="KnowledgeBase",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("content", models.TextField()),
                ("keywords", models.TextField(help_text="Comma-separated keywords")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("views", models.IntegerField(default=0)),
                ("helpful_count", models.IntegerField(default=0)),
                ("is_published", models.BooleanField(default=True)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_articles",
                        to="myapp.category",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Knowledge Base Article",
                "verbose_name_plural": "Knowledge Base",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CannedResponse",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                (
                    "content",
                    models.TextField(
                        help_text="Use {{task_id}}, {{user_name}}, {{task_title}}"
                    ),
                ),
                ("is_public", models.BooleanField(default=True)),
                ("usage_count", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="canned_responses",
                        to="myapp.category",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="canned_responses_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="canned_responses",
                        to="myapp.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "Canned Response",
                "verbose_name_plural": "Canned Responses",
                "ordering": ["-usage_count", "title"],
            },
        ),
        migrations.CreateModel(
            name="AIMLLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "log_type",
                    models.CharField(
                        choices=[
                            ("CHATBOT", "AI Chatbot"),
                            ("CATEGORY", "Category Suggestion"),
                            ("PRIORITY", "Priority Suggestion"),
                            ("DEPARTMENT", "Department Assignment"),
                            ("DUPLICATE", "Duplicate Detection"),
                        ],
                        max_length=20,
                    ),
                ),
                ("input_data", models.TextField()),
                ("output_data", models.TextField()),
                ("confidence", models.FloatField(blank=True, null=True)),
                ("was_correct", models.BooleanField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_logs",
                        to="myapp.taskdetail",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI/ML Log",
                "verbose_name_plural": "AI/ML Logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TaskHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("UPDATED", "Updated"),
                            ("ASSIGNED", "Assigned"),
                            ("STATUS_CHANGED", "Status Changed"),
                            ("PRIORITY_CHANGED", "Priority Changed"),
                            ("COMMENTED", "Commented"),
                            ("ESCALATED", "Escalated"),
                            ("SLA_BREACHED", "SLA Breached"),
                            ("CLOSED", "Closed"),
                            ("REOPENED", "Reopened"),
                        ],
                        max_length=50,
                    ),
                ),
                ("field_name", models.CharField(blank=True, max_length=100)),
                ("old_value", models.TextField(blank=True)),
                ("new_value", models.TextField(blank=True)),
                ("description", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history",
                        to="myapp.taskdetail",
                    ),
                ),
            ],
            options={
                "verbose_name": "Task History",
                "verbose_name_plural": "Task History",
                "ordering": ["-changed_at"],
                "indexes": [
                    models.Index(
                        fields=["task", "-changed_at"],
                        name="myapp_taskh_task_id_bae3f8_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "notification_type",
                    models.CharField(
                        choices=[
                            ("TASK_CREATED", "Task Created"),
                            ("TASK_ASSIGNED", "Task Assigned"),
                            ("TASK_ACCEPTED", "Task Accepted"),
                            ("TASK_UPDATED", "Task Updated"),
                            ("TASK_CLOSED", "Task Closed"),
                            ("TASK_RESOLVED", "Task Resolved"),
                            ("TASK_REOPENED", "Task Reopened"),
                            ("TASK_COMMENTED", "Task Commented"),
                            ("TASK_OVERDUE", "Task Overdue"),
                            ("DEPARTMENT_ASSIGNED", "Department Assigned"),
                            ("MENTION", "Mentioned in Task"),
                            ("SYSTEM", "System Notification"),
                        ],
                        default="SYSTEM",
                        max_length=50,
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=200)),
                ("message", models.TextField()),
                ("extra_data", models.JSONField(blank=True, default=dict)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("email_sent", models.BooleanField(default=False)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="myapp.taskdetail",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "-created_at"],
                        name="myapp_notif_user_id_025f20_idx",
                    ),
                    models.Index(
                        fields=["user", "is_read"],
                        name="myapp_notif_user_id_da55a8_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DepartmentMember",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("MEMBER", "Member"),
                            ("LEAD", "Team Lead"),
                            ("MANAGER", "Manager"),
                            ("HEAD", "Department Head"),
                        ],
                        default="MEMBER",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("can_assign_tickets", models.BooleanField(default=False)),
                ("can_close_tickets", models.BooleanField(default=True)),
                ("can_delete_tickets", models.BooleanField(default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="members_added",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="myapp.department",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="department_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Department Member",
                "verbose_name_plural": "Department Members",
                "ordering": ["department", "-role", "user__username"],
                "unique_together": {("user", "department")},
            },
        ),
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATED", "Ticket Created"),
                            ("ASSIGNED", "Ticket Assigned"),
                            ("RESOLVED", "Ticket Resolved"),
                            ("COMMENTED", "Comment Added"),
                            ("ESCALATED", "Ticket Escalated"),
                            ("REOPENED", "Ticket Reopened"),
                            ("CLOSED", "Ticket Closed"),
                            ("UPDATED", "Ticket Updated"),
                            ("STATUS", "Status Changed"),
                            ("PRIORITY", "Priority Changed"),
                            ("SYSTEM", "System Event"),
                        ],
                        default="SYSTEM",
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("old_value", models.CharField(blank=True, max_length=200)),
                ("new_value", models.CharField(blank=True, max_length=200)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_logs",
                        to="myapp.taskdetail",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Activity Log",
                "verbose_name_plural": "Activity Logs",
                "ordering": ["-timestamp"],
                "indexes": [
                    models.Index(
                        fields=["user", "-timestamp"],
                        name="myapp_activ_user_id_39b568_idx",
                    ),
                    models.Index(
                        fields=["task", "-timestamp"],
                        name="myapp_activ_task_id_970c87_idx",
                    ),
                ],
            },
        ),
    ]
