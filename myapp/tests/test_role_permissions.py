from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from myapp.models import Department, DepartmentMember, MyCart, TaskDetail, TaskHistory


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

    def test_member_can_close_department_ticket_from_queue(self):
        task = self._create_open_task()
        MyCart.objects.create(user=self.member, task=task)

        self.client.login(username="member1", password="pass12345")
        response = self.client.get(reverse("closetask", kwargs={"pk": task.id}))

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.TASK_STATUS, "Closed")

    def test_rejected_member_cannot_close_until_auto_reassigned(self):
        task = self._create_open_task()
        MyCart.objects.create(user=self.member, task=task)
        TaskHistory.objects.create(
            task=task,
            changed_by=self.member,
            action_type="REJECTED",
            description="Task rejected by member1. Reason: Not available.",
        )

        self.client.login(username="member1", password="pass12345")
        response = self.client.get(reverse("closetask", kwargs={"pk": task.id}))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.TASK_STATUS, "Open")

        TaskHistory.objects.create(
            task=task,
            changed_by=self.lead,
            action_type="ASSIGNED",
            old_value="Unassigned",
            new_value=self.member.username,
            description=f"Auto-assigned to {self.member.username} after department rejections.",
        )

        response = self.client.get(reverse("closetask", kwargs={"pk": task.id}))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.TASK_STATUS, "Closed")

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

    def test_single_member_department_cannot_reject_ticket(self):
        solo_department = Department.objects.create(
            name="Solo Ops",
            code="SOLO",
            description="Single member department",
            color="#16a34a",
            icon="fas fa-user",
        )
        DepartmentMember.objects.create(
            user=self.member,
            department=solo_department,
            role="MEMBER",
            is_active=True,
        )
        task = TaskDetail.objects.create(
            TASK_TITLE="Solo queue ticket",
            TASK_CREATED=self.creator,
            TASK_DUE_DATE=timezone.now().date() + timedelta(days=2),
            TASK_DESCRIPTION="Only one member should not be able to reject this.",
            TASK_HOLDER="",
            TASK_STATUS="Open",
            priority="MEDIUM",
            assigned_department=solo_department,
        )
        MyCart.objects.create(user=self.member, task=task)

        self.client.login(username="member1", password="pass12345")
        response = self.client.post(
            reverse("removetask", kwargs={"pk": task.id}),
            data={"reject_reason": "No backup member."},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(MyCart.objects.filter(user=self.member, task=task).exists())
        self.assertFalse(
            TaskHistory.objects.filter(
                task=task,
                changed_by=self.member,
                action_type="REJECTED",
            ).exists()
        )

    @patch("myapp.views.predict_department")
    @patch("myapp.views.predict_ticket_priority_with_meta")
    def test_ticket_auto_assigned_when_department_has_one_member(self, mock_predict_priority, mock_predict_department):
        solo_department = Department.objects.create(
            name="Lone Desk",
            code="LONE",
            description="One active member only",
            color="#0ea5e9",
            icon="fas fa-user-check",
        )
        mock_predict_department.return_value = "Lone Desk"
        mock_predict_priority.return_value = {
            "priority": "MEDIUM",
            "reason": "Default",
            "model": "test",
            "error": "",
        }
        DepartmentMember.objects.create(
            user=self.member,
            department=solo_department,
            role="MEMBER",
            is_active=True,
        )

        self.client.login(username="creator", password="pass12345")
        response = self.client.post(
            reverse("taskdetail"),
            data={
                "TASK_TITLE": "Single member assignment",
                "TASK_DESCRIPTION": "Should auto assign to only department member.",
                "TASK_DUE_DATE": (timezone.now().date() + timedelta(days=2)).isoformat(),
                "category": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        task = TaskDetail.objects.latest("id")
        self.assertEqual(task.assigned_department_id, solo_department.id)
        self.assertEqual(task.assigned_to_id, self.member.id)
