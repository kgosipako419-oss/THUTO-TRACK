"""End-to-end tests for the parents app (WhatsApp webhook + web portal)."""

import base64
import hmac
from datetime import date
from hashlib import sha1

from django.test import TestCase, override_settings

from core.factories import (
    make_class,
    make_parent_account,
    make_school,
    make_student,
    make_subject,
    make_teacher,
)
from core.models import Mark


class WebhookBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = make_school()
        cls.teacher = make_teacher(cls.school)
        cls.cg = make_class(cls.school, class_teacher=cls.teacher)
        cls.math = make_subject(cls.school, code="MATH", name="Mathematics")
        cls.student = make_student(
            cls.school, cls.cg, student_number="W-1",
            first_name="Naledi", last_name="Tau",
            parent_phone="+267 71 222 001",
        )


class WebhookBasicTests(WebhookBase):
    def test_get_returns_health_message(self):
        resp = self.client.get("/whatsapp/webhook/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"ThutoTrack", resp.content)

    def test_post_returns_twiml(self):
        resp = self.client.post(
            "/whatsapp/webhook/",
            {"From": "whatsapp:+26771222001", "Body": "hi"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("application/xml"))
        self.assertIn(b"<Response><Message>", resp.content)
        self.assertIn(b"Naledi", resp.content)

    def test_unknown_phone_gets_onboarding(self):
        resp = self.client.post(
            "/whatsapp/webhook/",
            {"From": "whatsapp:+26799999999", "Body": "hi"},
        )
        self.assertIn(b"isn", resp.content)  # "isn't linked"

    def test_marks_command_returns_marks(self):
        Mark.objects.create(
            student=self.student, subject=self.math, teacher=self.teacher,
            assessment_type="TEST", title="Mid-term", score=80, max_score=100,
            term=1, academic_year=date.today().year,
        )
        resp = self.client.post(
            "/whatsapp/webhook/",
            {"From": "whatsapp:+26771222001", "Body": "marks"},
        )
        self.assertIn(b"Mathematics", resp.content)
        self.assertIn(b"Mid-term", resp.content)


class WebhookSignatureTests(WebhookBase):
    @override_settings(WHATSAPP_AUTH_TOKEN="testtoken")
    def test_unsigned_post_rejected(self):
        resp = self.client.post(
            "/whatsapp/webhook/",
            {"From": "whatsapp:+26771222001", "Body": "hi"},
        )
        self.assertEqual(resp.status_code, 403)

    @override_settings(WHATSAPP_AUTH_TOKEN="testtoken")
    def test_correctly_signed_post_accepted(self):
        params = {"From": "whatsapp:+26771222001", "Body": "hi"}
        url = "http://testserver/whatsapp/webhook/"
        payload = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
        sig = base64.b64encode(
            hmac.new(b"testtoken", payload.encode("utf-8"), sha1).digest()
        ).decode("ascii")
        resp = self.client.post(
            "/whatsapp/webhook/", params, HTTP_X_TWILIO_SIGNATURE=sig,
        )
        self.assertEqual(resp.status_code, 200)


class ParentLoginTests(WebhookBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parent = make_parent_account("+267 71 222 001", "1234")

    def test_landing_renders_for_anonymous(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sign in as parent")
        self.assertContains(resp, "Sign in as teacher")

    def test_login_with_various_phone_formats(self):
        for raw in ["+267 71 222 001", "26771222001", "071222001", "71222001"]:
            cli = self.client_class()
            resp = cli.post("/parents/login/", {"phone": raw, "pin": "1234"})
            self.assertEqual(resp.status_code, 302, f"format failed: {raw}")
            self.assertIn("/parents/", resp["Location"])

    def test_wrong_pin_rejected(self):
        resp = self.client.post(
            "/parents/login/", {"phone": "+267 71 222 001", "pin": "9999"},
        )
        self.assertContains(resp, "find a parent account")

    def test_empty_submission_rejected(self):
        resp = self.client.post("/parents/login/", {"phone": "", "pin": ""})
        self.assertContains(resp, "Enter your phone")


class ParentPortalTests(WebhookBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parent = make_parent_account("+267 71 222 001", "1234")

    def _login_parent(self):
        self.assertTrue(self.client.login(username="26771222001", password="1234"))

    def test_dashboard_lists_children(self):
        self._login_parent()
        resp = self.client.get("/parents/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Naledi Tau")

    def test_student_detail_renders(self):
        self._login_parent()
        resp = self.client.get(f"/parents/students/{self.student.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Naledi Tau")
        self.assertContains(resp, "All marks")

    def test_foreign_student_404(self):
        self._login_parent()
        other_school = make_school(name="Other", code="OTH-X")
        other_cg = make_class(other_school)
        other_stu = make_student(other_school, other_cg, student_number="X-1",
                                 first_name="Not", last_name="Mine")
        resp = self.client.get(f"/parents/students/{other_stu.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_pdf_report_download(self):
        self._login_parent()
        Mark.objects.create(
            student=self.student, subject=self.math, teacher=self.teacher,
            assessment_type="TEST", title="T1", score=80, max_score=100,
            term=1, academic_year=2026,
        )
        resp = self.client.get(
            f"/parents/students/{self.student.id}/report/?term=1&year=2026",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_logout_returns_to_landing(self):
        self._login_parent()
        resp = self.client.post("/parents/logout/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "/")

    def test_anonymous_bounced_from_dashboard(self):
        resp = self.client.get("/parents/")
        self.assertEqual(resp.status_code, 302)


class SmartRedirectTests(WebhookBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.parent = make_parent_account("+267 71 222 001", "1234")
        from core.factories import make_school_admin
        cls.admin = make_school_admin(cls.school, username="admin1", password="adminpw1")

    def test_logged_in_teacher_redirected_to_teacher_portal(self):
        # make_teacher's default password is "teachpass1"
        self.assertTrue(self.client.login(username=self.teacher.user.username, password="teachpass1"))
        resp = self.client.get("/", follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/teachers/", resp["Location"])

    def test_logged_in_admin_redirected_to_admin_portal(self):
        self.client.login(username="admin1", password="adminpw1")
        resp = self.client.get("/", follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin-portal/", resp["Location"])

    def test_logged_in_parent_redirected_to_parent_portal(self):
        self.client.login(username="26771222001", password="1234")
        resp = self.client.get("/", follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/parents/", resp["Location"])

    def test_anonymous_user_sees_landing(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sign in as teacher")
