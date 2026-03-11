from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from myapp.models import Department, DepartmentMember, TicketDetail, TicketHistory


class AccessControlRegressionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="access_admin",
            email="access_admin@example.com",
            password="pass12345",
        )
        self.member = User.objects.create_user(username="access_member", password="pass12345")
        self.other_user = User.objects.create_user(username="access_other", password="pass12345")
        self.creator = User.objects.create_user(username="access_creator", password="pass12345")

        self.department = Department.objects.create(
            name="Access IT",
            code="AIT",
            description="Access control department",
            color="#2563eb",
            icon="fas fa-laptop-code",
        )
        self.other_department = Department.objects.create(
            name="Access HR",
            code="AHR",
            description="Other department",
            color="#8b5cf6",
            icon="fas fa-users",
        )

        DepartmentMember.objects.create(
            user=self.member,
            department=self.department,
            role="MEMBER",
            is_active=True,
        )

    def _create_ticket(self, **kwargs):
        defaults = {
            "TICKET_TITLE": "Access control ticket",
            "TICKET_CREATED": self.creator,
            "TICKET_DUE_DATE": timezone.now().date() + timedelta(days=2),
            "TICKET_DESCRIPTION": "Detailed description for access control coverage.",
            "TICKET_HOLDER": "",
            "TICKET_STATUS": "Open",
            "priority": "MEDIUM",
            "assigned_department": self.department,
        }
        defaults.update(kwargs)
        return TicketDetail.objects.create(**defaults)

    def test_ticket_history_requires_ticket_access(self):
        ticket = self._create_ticket()
        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=self.creator,
            action_type="CREATED",
            description="Created by creator",
        )

        self.client.login(username="access_other", password="pass12345")
        response = self.client.get(
            reverse("ticket_history", kwargs={"pk": ticket.id}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("base"))
        messages = [message.message for message in response.context["messages"]]
        self.assertIn("You do not have permission to view this ticket history.", messages)

    def test_non_member_cannot_view_department_analytics(self):
        self.client.login(username="access_other", password="pass12345")
        response = self.client.get(
            reverse("department_analytics", kwargs={"dept_id": self.department.id}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("base"))
        messages = [message.message for message in response.context["messages"]]
        self.assertIn("You are not allowed to view analytics for this department.", messages)

    def test_member_cannot_open_inactive_department_dashboard(self):
        inactive_department = Department.objects.create(
            name="Inactive Access",
            code="IACC",
            description="Inactive department",
            color="#f59e0b",
            icon="fas fa-box",
            is_active=False,
        )
        DepartmentMember.objects.create(
            user=self.member,
            department=inactive_department,
            role="MEMBER",
            is_active=True,
        )

        self.client.login(username="access_member", password="pass12345")
        response = self.client.get(
            reverse("department_dashboard_id", kwargs={"dept_id": inactive_department.id}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("base"))
        messages = [message.message for message in response.context["messages"]]
        self.assertIn("This department is inactive.", messages)

    def test_creator_cannot_delete_inactive_department_ticket(self):
        inactive_department = Department.objects.create(
            name="Archived Access",
            code="ARCH",
            description="Archived department",
            color="#f59e0b",
            icon="fas fa-box-archive",
            is_active=False,
        )
        DepartmentMember.objects.create(
            user=self.creator,
            department=inactive_department,
            role="MEMBER",
            is_active=True,
        )
        ticket = self._create_ticket(
            assigned_department=inactive_department,
            TICKET_CREATED=self.creator,
        )

        self.client.login(username="access_creator", password="pass12345")
        response = self.client.post(
            reverse("deleteticket", kwargs={"pk": ticket.id}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("base"))
        self.assertTrue(TicketDetail.objects.filter(id=ticket.id).exists())
        messages = [message.message for message in response.context["messages"]]
        self.assertIn("You do not have permission to delete this ticket.", messages)
