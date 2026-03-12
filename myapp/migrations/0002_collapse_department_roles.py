from django.db import migrations, models


def collapse_department_roles(apps, schema_editor):
    DepartmentMember = apps.get_model('myapp', 'DepartmentMember')
    DepartmentMember.objects.update(
        role='MEMBER',
        can_assign_tickets=True,
        can_close_tickets=True,
        can_delete_tickets=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(collapse_department_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='departmentmember',
            name='can_assign_tickets',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='departmentmember',
            name='role',
            field=models.CharField(
                choices=[('MEMBER', 'Member')],
                default='MEMBER',
                max_length=20,
            ),
        ),
    ]
