from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ticketdetail",
            name="TICKET_STATUS",
            field=models.CharField(
                choices=[
                    ("Open", "Open"),
                    ("In Progress", "In Progress"),
                    ("Closed", "Closed"),
                    ("Reopen", "Reopen"),
                    ("Resolved", "Resolved"),
                ],
                default="Open",
                max_length=100,
            ),
        ),
    ]
