from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("myapp", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="taskdetail",
            name="escalated_to",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="sla_policy",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="escalation_level",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="first_response_at",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="last_escalated_at",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="sla_resolution_breached",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="sla_resolution_deadline",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="sla_response_breached",
        ),
        migrations.RemoveField(
            model_name="taskdetail",
            name="sla_response_deadline",
        ),
        migrations.DeleteModel(
            name="TaskEscalation",
        ),
        migrations.DeleteModel(
            name="EscalationRule",
        ),
        migrations.DeleteModel(
            name="SLAPolicy",
        ),
    ]
