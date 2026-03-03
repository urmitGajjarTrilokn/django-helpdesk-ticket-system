from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from myapp.models import Department, DepartmentMember, MyCart, TaskDetail


class RolePermissionBehaviorTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="IT Ops",
            code="ITOPS",
            description="Ops",
            color="#3b82f6",
            icon="fas fa-laptop-code",
        )
        self.creator = User.objects.create_user(username="creator", password="pass12345")
        self.member = User.objects.create_user(username="member1", password="pass12345")
        self.lead = User.objects.create_user(username="lead1", password="pass12345")
        self.manager = User.objects.create_user(username="manager1", password="pass12345")

        DepartmentMember.objects.create(user=self.member, department=self.department, role="MEMBER", is_active=True)
        DepartmentMember.objects.create(user=self.lead, department=self.department, role="LEAD", is_active=True)
        DepartmentMember.objects.create(user=self.manager, department=self.department, role="MANAGER", is_active=True)

    def _create_open_task(self):
        return TaskDetail.objects.create(
            TASK_TITLE="Shared printer outage in finance wing",
            TASK_CREATED=self.creator,
            TASK_DUE_DATE=timezone.now().date() + timedelta(days=3),
            TASK_DESCRIPTION="Multiple users report printer queue failures and no output.",
            TASK_HOLDER="",
            TASK_STATUS="Open",
            priority="MEDIUM",
            assigned_department=self.department,
        )

    def test_member_cannot_close_unassigned_department_ticket(self):
        task = self._create_open_task()
        MyCart.objects.create(user=self.member, task=task)

        self.client.login(username="member1", password="pass12345")
        response = self.client.get(reverse("closetask", kwargs={"pk": task.id}))

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.TASK_STATUS, "Open")

    def test_lead_can_close_unassigned_department_ticket(self):
        task = self._create_open_task()
        MyCart.objects.create(user=self.lead, task=task)

        self.client.login(username="lead1", password="pass12345")
        response = self.client.get(reverse("closetask", kwargs={"pk": task.id}))

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.TASK_STATUS, "Closed")

    def test_member_cannot_delete_department_ticket(self):
        task = self._create_open_task()
        self.client.login(username="member1", password="pass12345")

        response = self.client.get(reverse("deletetask", kwargs={"pk": task.id}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TaskDetail.objects.filter(id=task.id).exists())

    def test_manager_can_delete_department_ticket(self):
        task = self._create_open_task()
        self.client.login(username="manager1", password="pass12345")

        response = self.client.get(reverse("deletetask", kwargs={"pk": task.id}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TaskDetail.objects.filter(id=task.id).exists())
