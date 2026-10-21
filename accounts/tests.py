from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, StudentProfile, User


class AccountsAuthTests(APITestCase):
    def setUp(self):
        self.student_role, _ = Role.objects.get_or_create(name=Role.STUDENT)
        self.teacher_role, _ = Role.objects.get_or_create(name=Role.TEACHER)
        self.admin_role, _ = Role.objects.get_or_create(name=Role.ADMIN)

        self.admin_user = User.objects.create_user(
            username="admin1",
            email="admin1@example.com",
            password="AdminPass123",
            role=self.admin_role,
            is_staff=True,
        )

        self.student_user = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="StudentPass123",
            role=self.student_role,
        )

    def _login(self, username, password):
        return self.client.post(
            "/api/accounts/login/",
            {"username": username, "password": password},
            format="json",
        )

    def test_register_creates_student_and_profile(self):
        payload = {
            "email": "new_student@example.com",
            "username": "new_student",
            "password": "NewStudentPass123",
            "first_name": "New",
            "last_name": "Student",
        }
        res = self.client.post("/api/accounts/register/", payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="new_student")
        self.assertEqual(user.role.name, Role.STUDENT)
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())

    def test_login_with_username_returns_tokens(self):
        res = self._login("student1", "StudentPass123")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_login_with_email_returns_tokens(self):
        res = self.client.post(
            "/api/accounts/login/",
            {"email": "student1@example.com", "password": "StudentPass123"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_logout_blacklists_refresh_token(self):
        login_res = self._login("student1", "StudentPass123")
        access = login_res.data["access"]
        refresh = login_res.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout_res = self.client.post("/api/accounts/logout/", {"refresh": refresh}, format="json")
        self.assertEqual(logout_res.status_code, status.HTTP_205_RESET_CONTENT)

        refresh_res = self.client.post("/api/accounts/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileTests(APITestCase):
    def setUp(self):
        self.student_role, _ = Role.objects.get_or_create(name=Role.STUDENT)
        self.user = User.objects.create_user(
            username="profile_user",
            email="profile_user@example.com",
            password="ProfilePass123",
            role=self.student_role,
            first_name="Old",
            last_name="Name",
        )
        self.other_user = User.objects.create_user(
            username="profile_other",
            email="profile_other@example.com",
            password="OtherPass123",
            role=self.student_role,
        )

    def _auth(self):
        login_res = self.client.post(
            "/api/accounts/login/",
            {"username": "profile_user", "password": "ProfilePass123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['access']}")

    def test_update_profile(self):
        self._auth()
        res = self.client.patch(
            "/api/accounts/me/",
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "new_email@example.com",
                "avatar_url": "https://res.cloudinary.com/demo/image/upload/avatar.png",
            },
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Student")
        self.assertEqual(self.user.email, "new_email@example.com")
        self.assertEqual(self.user.role.name, Role.STUDENT)

    def test_update_profile_rejects_duplicate_email(self):
        self._auth()
        res = self.client.patch(
            "/api/accounts/me/",
            {"email": self.other_user.email},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "profile_user@example.com")

    def test_change_password(self):
        self._auth()
        res = self.client.post(
            "/api/accounts/me/password/",
            {"current_password": "ProfilePass123", "new_password": "NewProfilePass456"},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewProfilePass456"))

    def test_change_password_rejects_wrong_current_password(self):
        self._auth()
        res = self.client.post(
            "/api/accounts/me/password/",
            {"current_password": "WrongPass123", "new_password": "NewProfilePass456"},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ProfilePass123"))

    def test_change_password_rejects_weak_password(self):
        self._auth()
        res = self.client.post(
            "/api/accounts/me/password/",
            {"current_password": "ProfilePass123", "new_password": "123"},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ProfilePass123"))


class AccountsAdminPermissionTests(APITestCase):
    def setUp(self):
        self.student_role, _ = Role.objects.get_or_create(name=Role.STUDENT)
        self.admin_role, _ = Role.objects.get_or_create(name=Role.ADMIN)

        self.admin_user = User.objects.create_user(
            username="admin2",
            email="admin2@example.com",
            password="AdminPass123",
            role=self.admin_role,
            is_staff=True,
        )
        self.normal_user = User.objects.create_user(
            username="normal1",
            email="normal1@example.com",
            password="NormalPass123",
            role=self.student_role,
        )

    def _auth(self, username, password):
        login_res = self.client.post(
            "/api/accounts/login/",
            {"username": username, "password": password},
            format="json",
        )
        token = login_res.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_user_list_forbidden_for_non_admin(self):
        self._auth("normal1", "NormalPass123")
        res = self.client.get("/api/accounts/users/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_list_allowed_for_admin(self):
        self._auth("admin2", "AdminPass123")
        res = self.client.get("/api/accounts/users/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 2)

    def test_admin_can_update_user_role_by_role_name(self):
        self._auth("admin2", "AdminPass123")

        target = self.normal_user
        res = self.client.patch(
            f"/api/accounts/users/{target.id}/",
            {"role_name": Role.ADMIN},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertEqual(target.role.name, Role.ADMIN)

    def test_dashboard_stats_requires_auth(self):
        res = self.client.get("/api/accounts/stats/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_stats_admin_has_detailed_stats(self):
        self._auth("admin2", "AdminPass123")
        res = self.client.get("/api/accounts/stats/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("total_teachers", res.data["stats"])
        self.assertIn("total_students", res.data["stats"])
        self.assertIn("total_attempts", res.data["stats"])
        self.assertIn("avg_score_system", res.data["stats"])


class AdminReportTests(APITestCase):
    def setUp(self):
        self.admin_role, _ = Role.objects.get_or_create(name=Role.ADMIN)
        self.teacher_role, _ = Role.objects.get_or_create(name=Role.TEACHER)
        self.student_role, _ = Role.objects.get_or_create(name=Role.STUDENT)

        self.admin = User.objects.create_user(username="admin_rep", email="admin_rep@ex.com", password="Pass", role=self.admin_role, is_staff=True)
        self.teacher = User.objects.create_user(username="teacher_rep", email="teacher_rep@ex.com", password="Pass", role=self.teacher_role)
        self.student = User.objects.create_user(username="student_rep", email="student_rep@ex.com", password="Pass", role=self.student_role)
        
        from classes.models import Subject, Class
        from exams.models import Quiz, QuizAttempt
        from django.utils import timezone
        import uuid

        subj = Subject.objects.create(name="Math")
        self.classroom = Class.objects.create(name="12A", subject=subj, teacher=self.teacher)
        quiz = Quiz.objects.create(title="Final Exam", classroom=self.classroom, created_by=self.teacher)
        
        # Create successful attempt
        self.attempt = QuizAttempt.objects.create(
            quiz=quiz, student=self.student, score=9.5, is_completed=True, 
            end_time=timezone.now()
        )

    def _auth(self, user):
        login_res = self.client.post("/api/accounts/login/", {"username": user.username, "password": "Pass"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['access']}")

    def test_report_forbidden_for_student(self):
        self._auth(self.student)
        res = self.client.get("/api/accounts/admin/report/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_report_allowed_for_admin(self):
        self._auth(self.admin)
        res = self.client.get("/api/accounts/admin/report/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["student_name"], self.student.full_name)

    def test_report_filter_by_class(self):
        self._auth(self.admin)
        res = self.client.get(f"/api/accounts/admin/report/?class_id={self.classroom.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

    def test_export_returns_xlsx(self):
        self._auth(self.admin)
        res = self.client.get("/api/accounts/admin/export/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
