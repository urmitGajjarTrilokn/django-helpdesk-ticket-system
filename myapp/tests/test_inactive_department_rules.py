from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from myapp.models import Department, DepartmentMember, TicketDetail


class InactiveDepartmentRuleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="inactive_admin",
            email="inactive_admin@example.com",
            password="pass12345",
        )
        self.creator = User.objects.create_user(username="inactive_creator", password="pass12345")
        self.member = User.objects.create_user(username="inactive_member", password="pass12345")
        self.other_member = User.objects.create_user(username="inactive_other", password="pass12345")

        self.active_department = Department.objects.create(
            name="Active Support",
            code="ASUP",
            description="Active support department",
            color="#2563eb",
            icon="fas fa-life-ring",
        )
        self.inactive_department = Department.objects.create(
            name="Inactive Support",
            code="ISUP",
            description="Inactive support department",
            color="#f59e0b",
            icon="fas fa-box-archive",
            is_active=False,
        )

        DepartmentMember.objects.create(
            user=self.creator,
            department=self.inactive_department,
            role="MEMBER",
            is_active=True,
        )
        DepartmentMember.objects.create(
            user=self.member,
            department=self.active_department,
            role="MEMBER",
            is_active=True,
        )
        DepartmentMember.objects.create(
            user=self.other_member,
            department=self.active_department,
            role="LEAD",
            is_active=True,
        )

    def _create_ticket(self, department, creator=None, **kwargs):
        defaults = {
            "TICKET_TITLE": "Inactive department rule ticket",
            "TICKET_CREATED": creator or self.member,
            "TICKET_DUE_DATE": timezone.now().date() + timedelta(days=3),
            "TICKET_DESCRIPTION": "Detailed description for inactive department rule coverage.",
            "TICKET_HOLDER": "",
            "TICKET_STATUS": "Open",
            "priority": "MEDIUM",
            "assigned_department": department,
        }
        defaults.update(kwargs)
        return TicketDetail.objects.create(**defaults)

    def test_user_with_inactive_department_membership_cannot_create_ticket(self):
        self.client.login(username="inactive_creator", password="pass12345")
        before_count = TicketDetail.objects.count()

        response = self.client.post(
            reverse("ticketdetail"),
            data={
                "TICKET_TITLE": "Blocked inactive department ticket",
                "TICKET_DESCRIPTION": "This ticket should not be created while the department is inactive.",
                "TICKET_DUE_DATE": (timezone.now().date() + timedelta(days=2)).isoformat(),
                "category": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TicketDetail.objects.count(), before_count)
        messages = [message.message for message in response.context["messages"]]
        self.assertIn(
            "You cannot create tickets while your department is inactive. Contact an administrator.",
            messages,
        )

    def test_admin_cannot_assign_ticket_to_inactive_department(self):
        ticket = self._create_ticket(self.active_department, creator=self.other_member)

        self.client.login(username="inactive_admin", password="pass12345")
        response = self.client.post(
            reverse("updateticket", kwargs={"pk": ticket.id}),
            data={
                "priority": ticket.priority,
                "assigned_department": str(self.inactive_department.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_department_id, self.active_department.id)
        self.assertIn("assigned_department", response.context["form"].errors)

    def test_inactive_department_tickets_are_hidden_from_normal_users(self):
        ticket = self._create_ticket(
            self.inactive_department,
            creator=self.creator,
            assigned_to=self.creator,
            TICKET_HOLDER=self.creator.username,
        )

        self.client.login(username="inactive_creator", password="pass12345")

        dashboard_response = self.client.get(reverse("base"))
        self.assertEqual(dashboard_response.status_code, 200)
        visible_ticket_ids = {item.id for item in dashboard_response.context["Ticketdatas"].object_list}
        self.assertNotIn(ticket.id, visible_ticket_ids)

        ticket_response = self.client.get(reverse("ticketinfo", kwargs={"pk": ticket.id}), follow=True)
        self.assertEqual(ticket_response.status_code, 200)
        redirect_chain = [url for url, _status in ticket_response.redirect_chain]
        self.assertTrue(any(reverse("base") in url for url in redirect_chain))
        messages = [message.message for message in ticket_response.context["messages"]]
        self.assertIn("You do not have permission to view this ticket.", messages)

    def test_members_are_preserved_after_department_inactive_and_reactivate(self):
        managed_department = Department.objects.create(
            name="Managed Ops",
            code="MOPS",
            description="Managed ops department",
            color="#14b8a6",
            icon="fas fa-building",
        )
        DepartmentMember.objects.create(
            user=self.member,
            department=managed_department,
            role="MEMBER",
            is_active=True,
        )
        DepartmentMember.objects.create(
            user=self.other_member,
            department=managed_department,
            role="MANAGER",
            is_active=True,
        )

        self.client.login(username="inactive_admin", password="pass12345")

        inactive_response = self.client.post(
            reverse("admin_delete_department", kwargs={"dept_id": managed_department.id})
        )
        self.assertEqual(inactive_response.status_code, 302)
        managed_department.refresh_from_db()
        self.assertFalse(managed_department.is_active)
        self.assertEqual(
            DepartmentMember.objects.filter(department=managed_department, is_active=True).count(),
            2,
        )

        reactivate_response = self.client.post(
            reverse("admin_reactivate_department", kwargs={"dept_id": managed_department.id})
        )
        self.assertEqual(reactivate_response.status_code, 302)
        managed_department.refresh_from_db()
        self.assertTrue(managed_department.is_active)
        self.assertEqual(
            DepartmentMember.objects.filter(department=managed_department, is_active=True).count(),
            2,
        )
