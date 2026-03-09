import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from myapp.models import AIMLLog, TaskDetail


class TicketPriorityFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="creator", password="pass12345")
        self.client.login(username="creator", password="pass12345")

    def _ticket_payload(self, **overrides):
        payload = {
            "TASK_TITLE": "Printer outage at front office",
            "TASK_DESCRIPTION": "All front office printers are down and users cannot print invoices.",
            "TASK_DUE_DATE": (timezone.now().date() + timedelta(days=3)).isoformat(),
            "priority": "",
            "category": "",
            "assigned_department": "",
        }
        payload.update(overrides)
        return payload

    @patch("myapp.views.predict_ticket_priority_with_meta")
    def test_create_ticket_uses_ai_priority_when_blank(self, mock_predict):
        mock_predict.return_value = {
            "priority": "HIGH",
            "reason": "Production workflow blocked",
            "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
            "error": "",
        }
        response = self.client.post(reverse("taskdetail"), data=self._ticket_payload())
        self.assertEqual(response.status_code, 302)

        task = TaskDetail.objects.latest("id")
        self.assertEqual(task.priority, "HIGH")
        self.assertEqual(task.ai_suggested_priority, "HIGH")

        ai_log = AIMLLog.objects.filter(task=task, log_type="PRIORITY").latest("id")
        output = json.loads(ai_log.output_data)
        self.assertEqual(output["priority"], "HIGH")

    @patch("myapp.views.predict_ticket_priority_with_meta")
    def test_manual_priority_input_is_ignored_and_ai_still_runs(self, mock_predict):
        mock_predict.return_value = {
            "priority": "MEDIUM",
            "reason": "AI-only priority flow",
            "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
            "error": "",
        }
        response = self.client.post(
            reverse("taskdetail"),
            data=self._ticket_payload(priority="LOW"),
        )
        self.assertEqual(response.status_code, 302)
        mock_predict.assert_called_once()

        task = TaskDetail.objects.latest("id")
        self.assertEqual(task.priority, "MEDIUM")
        self.assertEqual(task.ai_suggested_priority, "MEDIUM")
        self.assertTrue(AIMLLog.objects.filter(task=task, log_type="PRIORITY").exists())

    def test_priority_override_marks_ai_feedback(self):
        task = TaskDetail.objects.create(
            TASK_TITLE="Email server intermittent failures",
            TASK_CREATED=self.user,
            TASK_DUE_DATE=timezone.now().date() + timedelta(days=2),
            TASK_DESCRIPTION="Users report frequent send failures and delayed inbox sync.",
            TASK_HOLDER=self.user.username,
            TASK_STATUS="Open",
            priority="HIGH",
            ai_suggested_priority="HIGH",
        )
        ai_log = AIMLLog.objects.create(
            task=task,
            log_type="PRIORITY",
            input_data="{}",
            output_data="{}",
            confidence=None,
            was_correct=None,
        )

        response = self.client.post(
            reverse("updatetask", kwargs={"pk": task.id}),
            data={
                "TASK_TITLE": task.TASK_TITLE,
                "TASK_DESCRIPTION": task.TASK_DESCRIPTION,
                "TASK_DUE_DATE": task.TASK_DUE_DATE.isoformat(),
                "priority": "LOW",
                "category": "",
                "assigned_department": "",
            },
        )
        self.assertEqual(response.status_code, 302)

        ai_log.refresh_from_db()
        self.assertFalse(ai_log.was_correct)
        output = json.loads(ai_log.output_data)
        self.assertEqual(output["suggested_priority"], "HIGH")
        self.assertEqual(output["user_selected_priority"], "LOW")
