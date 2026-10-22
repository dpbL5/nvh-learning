"""Browser E2E smoke tests for the main NVH Learning workflows.

Run with the isolated test settings:
DJANGO_SETTINGS_MODULE=nvh_learning.test_settings .venv/bin/python manage.py test tests.e2e
"""

import os
from unittest.mock import patch

# Playwright's synchronous bridge owns an event loop in this test process.
# Django DB calls remain synchronous; this only prevents a false async-context guard.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from accounts.models import Role, User
from ai_core.models import Document
from classes.models import Class, ClassStudent, Subject
from exams.models import Option, Question, Quiz, QuizQuestion
from notifications.models import Notification


PASSWORD = "BrowserE2EPass987!"


class BrowserE2ETestCase(StaticLiveServerTestCase):
    """Runs a real Chromium browser against Django's live test server."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self._seed()

    def tearDown(self):
        self.context.close()
        super().tearDown()

    def _seed(self):
        roles = {name: Role.objects.create(name=name) for name in ("teacher", "student", "admin")}
        self.teacher = User.objects.create_user(
            username="teacher_e2e", email="teacher.e2e@example.com", password=PASSWORD, role=roles["teacher"],
        )
        self.student = User.objects.create_user(
            username="student_e2e", email="student.e2e@example.com", password=PASSWORD, role=roles["student"],
        )
        self.admin = User.objects.create_user(
            username="admin_e2e", email="admin.e2e@example.com", password=PASSWORD, role=roles["admin"],
        )
        self.subject = Subject.objects.create(name="Tin học E2E")
        self.classroom = Class.objects.create(name="Lớp 10 E2E", subject=self.subject, teacher=self.teacher)
        ClassStudent.objects.create(classroom=self.classroom, student=self.student)
        self.quiz = Quiz.objects.create(
            title="Đề E2E", classroom=self.classroom, created_by=self.teacher,
            is_published=True, duration_minutes=30,
        )
        self.question = Question.objects.create(
            subject=self.subject, created_by=self.teacher, question_type="multiple_choice",
            text="2 + 2 bằng bao nhiêu?", explanation="Hai cộng hai bằng bốn.",
        )
        self.correct = Option.objects.create(question=self.question, text="4", is_correct=True)
        Option.objects.create(question=self.question, text="5", is_correct=False)
        QuizQuestion.objects.create(quiz=self.quiz, question=self.question, order=1, points=10)

    def url(self, path):
        return f"{self.live_server_url}{path}"

    def login(self, user):
        self.page.goto(self.url("/login/"))
        self.page.locator("#username").fill(user.username)
        self.page.locator("#password").fill(PASSWORD)
        self.page.locator("#loginForm button[type=submit]").click()
        self.page.wait_for_url("**/dashboard/")

    def reset_browser_session(self):
        self.page.evaluate("localStorage.clear(); sessionStorage.clear();")
        self.context.clear_cookies()

    def test_public_auth_profile_and_logout(self):
        self.page.goto(self.url("/"))
        self.page.get_by_text("Nguyễn Văn Huyên Learning").first.wait_for()
        self.page.goto(self.url("/register/"))
        self.page.locator("body").wait_for()

        self.login(self.student)
        self.page.goto(self.url("/profile/"))
        self.page.locator("#profileContent").wait_for(state="visible")
        self.page.locator("#profileFirstName").fill("E2E")
        self.page.locator("#profileForm").get_by_role("button", name="Lưu thay đổi").click()
        self.page.reload()
        self.page.locator("#profileContent").wait_for(state="visible")
        self.assertEqual(self.page.locator("#profileFirstName").input_value(), "E2E")

        # Logout is verified through the authenticated endpoint; a separate UI regression
        # should cover clearing the browser's local auth hint before redirecting to /login/.
        response = self.page.evaluate(
            """async () => {
                const response = await fetch('/api/accounts/logout/', {method: 'POST'});
                return response.status;
            }"""
        )
        self.assertEqual(response, 205)

    def test_teacher_class_question_bank_quiz_builder_and_ai_dialog(self):
        self.login(self.teacher)
        self.page.goto(self.url("/classes/"))
        self.page.locator("#classList").wait_for(state="visible")
        self.page.get_by_text("Lớp 10 E2E").wait_for()
        self.page.goto(self.url(f"/classes/{self.classroom.pk}/"))
        self.page.get_by_role("button", name="AI Trợ Giảng").click()
        self.page.locator("#aiContent").wait_for(state="visible")
        self.page.get_by_text("Tài liệu tham khảo").wait_for()

        self.page.goto(self.url("/exams/question-bank/"))
        self.page.get_by_role("heading", name="Ngân hàng câu hỏi").wait_for()
        self.page.get_by_role("button", name="Tạo bằng AI").click()
        self.page.locator("#aiGeneratorModal").wait_for(state="visible")
        self.page.locator("#ai-rag-tab").click()
        self.page.locator("#aiRagContent").wait_for(state="visible")
        self.assertIn("sinh câu hỏi theo nội dung tài liệu", self.page.locator("#ragTopicHelp").inner_text())

        self.page.goto(self.url(f"/exams/builder/{self.quiz.pk}/"))
        self.page.locator("body").wait_for()
        self.page.get_by_text("Đề E2E").first.wait_for()

    def test_student_notification_quiz_submission_and_dashboard(self):
        self.assertTrue(Notification.objects.filter(recipient=self.student, target_id=self.quiz.pk).exists())
        self.login(self.student)
        self.page.goto(self.url("/notifications/"))
        self.page.get_by_text("Đề E2E").first.wait_for()

        self.page.goto(self.url(f"/exams/taker/{self.quiz.pk}/"))
        self.page.get_by_role("button", name="Bắt đầu làm bài").wait_for()
        self.page.get_by_role("button", name="Bắt đầu làm bài").click()
        self.page.locator(".quiz-option").first.wait_for()
        self.page.locator(".quiz-option").first.click()
        self.page.locator("#submitExamBtn").click()
        self.page.locator("#submitConfirmModal").get_by_role("button", name="Nộp bài").click()
        self.page.locator("#resultState").wait_for(state="visible")
        self.assertEqual(self.page.locator("#finalScore").inner_text(), "10.0")

        self.page.goto(self.url("/dashboard/"))
        self.page.locator("body").wait_for()
        self.page.get_by_text("Bảng điều khiển").first.wait_for()

    def test_admin_panel_and_ai_api_error_are_visible_to_authorized_users(self):
        self.login(self.admin)
        self.page.goto(self.url("/admin-panel/"))
        self.page.locator("body").wait_for()
        self.page.get_by_text("Tổng người dùng").wait_for()

        self.reset_browser_session()
        self.login(self.teacher)
        Document.objects.create(classroom=self.classroom, title="Tài liệu E2E")
        with patch("ai_core.views.AIGeneratorService.generate_from_rag", return_value=[]):
            response = self.page.evaluate(
                """async ({classId}) => {
                    const response = await fetch('/api/ai/generate/from-rag/', {
                      method: 'POST', headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({class_id: classId, topic: 'Mạng máy tính', count: 1})
                    });
                    return {status: response.status, data: await response.json()};
                }""",
                {"classId": str(self.classroom.pk)},
            )
        self.assertEqual(response["status"], 422)
        self.assertIn("AI chưa tạo được câu hỏi", response["data"]["error"])
