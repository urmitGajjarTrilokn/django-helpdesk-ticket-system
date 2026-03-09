from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("myapp", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ticketdetail",
            name="escalated_to",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="sla_policy",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="escalation_level",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="first_response_at",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="last_escalated_at",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="sla_resolution_breached",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="sla_resolution_deadline",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="sla_response_breached",
        ),
        migrations.RemoveField(
            model_name="ticketdetail",
            name="sla_response_deadline",
        ),
        migrations.DeleteModel(
            name="TicketEscalation",
        ),
        migrations.DeleteModel(
            name="EscalationRule",
        ),
        migrations.DeleteModel(
            name="SLAPolicy",
        ),
    ]
