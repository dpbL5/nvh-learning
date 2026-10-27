from datetime import timedelta
import io
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import StudentProfile, User
from ai_core.models import ClassInsight
from classes.models import Class, ClassStudent
from classes.serializers import ClassSerializer
from exams.models import Question, Quiz, QuizAttempt, QuizQuestion, StudentAnswer
from notifications.models import Notification
from tests.support import PASSWORD, seed_lms


class CookieAuthTests(APITestCase):
    def setUp(self):
        self.d = seed_lms()

    def login(self):
        res = self.client.post('/api/accounts/login/', {
            'username': self.d.student.username, 'password': PASSWORD,
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        return res

    @override_settings(DEBUG=False)
    def test_cookie_flags_paths_and_cookie_only_auth(self):
        res = self.login()
        for key, path in (('access_token', '/'), ('refresh_token', '/api/accounts/')):
            cookie = res.cookies[key]
            self.assertTrue(cookie['httponly'])
            self.assertTrue(cookie['secure'])
            self.assertEqual(cookie['samesite'], 'Lax')
            self.assertEqual(cookie['path'], path)
        me = self.client.get('/api/accounts/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['id'], str(self.d.student.pk))

    def test_refresh_rotation_rejects_old_token_and_logout_clears_cookies(self):
        old = self.login().data['refresh']
        res = self.client.post('/api/accounts/token/refresh/', {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        new = res.cookies['refresh_token'].value
        self.assertNotEqual(old, new)
        self.assertEqual(APIClient().post('/api/accounts/token/refresh/', {'refresh': old}, format='json').status_code, 401)
        logout = self.client.post('/api/accounts/logout/', {}, format='json')
        self.assertEqual(logout.status_code, 205)
        for key in ('access_token', 'refresh_token'):
            self.assertEqual(logout.cookies[key]['max-age'], 0)
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)
        self.assertEqual(APIClient().post('/api/accounts/token/refresh/', {'refresh': new}, format='json').status_code, 401)

    def test_expired_access_refresh_and_invalid_header_fallback(self):
        self.login()
        token = AccessToken.for_user(self.d.student)
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.cookies['access_token'] = str(token)
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)
        self.assertEqual(self.client.post('/api/accounts/token/refresh/', {}, format='json').status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer broken')
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 200)
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)

    def test_registration_cannot_request_admin_and_rejects_case_duplicate(self):
        for extra in ({'role_name': 'admin'}, {'email': self.d.student.email.upper()},
                      {'username': self.d.student.username.upper()}, {'password': '123'}):
            with self.subTest(extra=extra):
                res = self.client.post('/api/accounts/register/', {
                    'username': 'newuser', 'email': 'new@example.com', 'password': PASSWORD, **extra,
                }, format='json')
                self.assertEqual(res.status_code, 400, res.data)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_profile_cannot_promote_role_and_case_duplicate_email_rejected(self):
        self.login()
        res = self.client.patch('/api/accounts/me/', {
            'role_name': 'admin', 'role': self.d.admin.role.pk, 'first_name': 'Updated',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.d.student.refresh_from_db()
        self.assertEqual(self.d.student.role.name, 'student')
        self.assertEqual(self.d.student.first_name, 'Updated')
        self.assertEqual(self.client.patch('/api/accounts/me/', {
            'email': self.d.outsider.email.upper(),
        }, format='json').status_code, 400)

    def test_cookie_auth_rejects_cross_origin_mutation(self):
        login = self.login()
        client = APIClient(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        res = client.patch('/api/accounts/me/', {'first_name': 'Injected'},
                           format='json', HTTP_ORIGIN='https://untrusted.example', secure=True)
        self.assertEqual(res.status_code, 403)
        self.d.student.refresh_from_db()
        self.assertNotEqual(self.d.student.first_name, 'Injected')


class ClassQuizAndReportTests(APITestCase):
    def setUp(self):
        self.d = seed_lms()
        self.client.force_authenticate(self.d.teacher)

    def test_join_normalizes_code_prevents_duplicate_and_notifies_late_member(self):
        self.client.force_authenticate(self.d.outsider)
        payload = {'invite_code': f' {self.d.classroom.invite_code.lower()} '}
        self.assertEqual(self.client.post('/api/classes/join/', payload, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/classes/join/', payload, format='json').status_code, 400)
        self.assertEqual(ClassStudent.objects.filter(classroom=self.d.classroom, student=self.d.outsider).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.d.outsider, target_id=self.d.quiz.pk).count(), 1)

    def test_class_stats_prefetch_and_fallback_agree_including_zero(self):
        QuizAttempt.objects.create(quiz=self.d.quiz, student=self.d.student, score=0, is_completed=True)
        QuizAttempt.objects.create(quiz=self.d.quiz, student=self.d.outsider, score=8, is_completed=True)
        QuizAttempt.objects.create(quiz=self.d.quiz, student=self.d.admin, score=10, is_completed=False)
        plain = ClassSerializer(Class.objects.get(pk=self.d.classroom.pk)).data
        loaded = ClassSerializer(Class.objects.prefetch_related('quizzes__attempts').get(pk=self.d.classroom.pk)).data
        self.assertEqual(plain, loaded)
        self.assertEqual(plain['total_attempts'], 2)
        self.assertEqual(plain['avg_score'], 4)

    def test_quiz_duration_schedule_and_other_class_validation(self):
        for extra in ({'duration_minutes': 0}, {'duration_minutes': 601},
                      {'publish_at': timezone.now(), 'due_date': timezone.now() - timedelta(days=1)}):
            with self.subTest(extra=extra):
                res = self.client.post('/api/exams/', {
                    'title': 'Invalid', 'classroom': str(self.d.classroom.pk), **extra,
                }, format='json')
                self.assertEqual(res.status_code, 400, res.data)
        self.assertEqual(self.client.post('/api/exams/', {
            'title': 'Forbidden', 'classroom': str(self.d.other_class.pk),
        }, format='json').status_code, 403)

    def test_duplicate_quiz_question_and_rebalance_after_add_delete(self):
        url = f'/api/exams/{self.d.quiz.pk}/questions/'
        self.assertEqual(self.client.post(url, {'question_id': self.d.mc.pk}, format='json').status_code, 400)
        q = Question.objects.create(text='New', subject=self.d.subject, created_by=self.d.teacher)
        added = self.client.post(url, {'question_id': q.pk, 'order': 2}, format='json')
        self.assertEqual(added.status_code, 201, added.data)
        self.assertEqual(list(self.d.quiz.quiz_questions.values_list('points', flat=True)), [5, 5])
        self.assertEqual(self.client.delete(f'{url}{added.data["id"]}/').status_code, 204)
        self.d.qq.refresh_from_db()
        self.assertEqual(self.d.qq.points, 10)

    def test_true_false_points_are_fixed_and_mcq_share_remaining_budget(self):
        url = f'/api/exams/{self.d.quiz.pk}/questions/'
        tf = Question.objects.create(
            question_type='true_false', text='TF', subject=self.d.subject,
            created_by=self.d.teacher,
        )
        added = self.client.post(url, {'question_id': tf.pk, 'order': 2}, format='json')
        self.assertEqual(added.status_code, 201, added.data)
        self.assertEqual(added.data['points'], 1.0)
        self.d.qq.refresh_from_db()
        self.assertEqual(self.d.qq.points, 9.0)

        mc = Question.objects.create(text='MC 2', subject=self.d.subject, created_by=self.d.teacher)
        self.assertEqual(self.client.post(url, {'question_id': mc.pk, 'order': 3}, format='json').status_code, 201)
        self.d.qq.refresh_from_db()
        self.assertEqual(self.d.qq.points, 4.5)
        self.assertEqual(
            list(self.d.quiz.quiz_questions.order_by('order').values_list('points', flat=True)),
            [4.5, 1.0, 4.5],
        )

    def test_manual_point_override_is_kept_and_can_be_reset(self):
        detail_url = f'/api/exams/{self.d.quiz.pk}/questions/{self.d.qq.pk}/'
        res = self.client.patch(detail_url, {'points': 2.0}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.d.qq.refresh_from_db()
        self.assertEqual(self.d.qq.points, 2.0)
        self.assertTrue(self.d.qq.is_points_overridden)

        question = Question.objects.create(text='New', subject=self.d.subject, created_by=self.d.teacher)
        added = self.client.post(
            f'/api/exams/{self.d.quiz.pk}/questions/',
            {'question_id': question.pk, 'order': 2}, format='json',
        )
        self.assertEqual(added.data['points'], 5.0)
        self.d.qq.refresh_from_db()
        self.assertEqual(self.d.qq.points, 2.0)

        self.assertEqual(
            self.client.delete(f'/api/exams/{self.d.quiz.pk}/questions/{added.data["id"]}/').status_code, 204
        )
        self.d.qq.refresh_from_db()
        self.assertEqual(self.d.qq.points, 2.0)

        reset = self.client.post(
            f'/api/exams/{self.d.quiz.pk}/questions/{self.d.qq.pk}/reset-points/', {}, format='json'
        )
        self.assertEqual(reset.status_code, 200, reset.data)
        self.assertEqual(reset.data['points'], 10.0)
        self.d.qq.refresh_from_db()
        self.assertFalse(self.d.qq.is_points_overridden)

    def test_copy_quiz_to_multiple_classes_skips_foreign_classes(self):
        extra_class = Class.objects.create(
            name='Lớp sao chép', subject=self.d.subject, teacher=self.d.teacher
        )
        tf = Question.objects.create(
            question_type='true_false', text='TF copy', subject=self.d.subject,
            created_by=self.d.teacher,
        )
        self.client.post(
            f'/api/exams/{self.d.quiz.pk}/questions/', {'question_id': tf.pk, 'order': 2}, format='json'
        )
        source_points = list(self.d.quiz.quiz_questions.order_by('order').values_list('points', flat=True))

        res = self.client.post(f'/api/exams/{self.d.quiz.pk}/copy/', {
            'classroom_ids': [str(extra_class.pk), str(self.d.other_class.pk)],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(len(res.data['created']), 1)
        self.assertEqual(res.data['skipped'], [
            {'classroom_id': str(self.d.other_class.pk), 'reason': 'permission_denied'},
        ])

        copied = Quiz.objects.get(pk=res.data['created'][0]['id'])
        self.assertEqual(copied.classroom_id, extra_class.pk)
        self.assertFalse(copied.is_published)
        self.assertEqual(copied.title, f'{self.d.quiz.title} (bản sao)')
        self.assertEqual(QuizAttempt.objects.filter(quiz=copied).count(), 0)
        self.assertEqual(copied.quiz_questions.count(), 2)
        self.assertEqual(
            list(copied.quiz_questions.order_by('order').values_list('points', flat=True)),
            source_points,
        )

    def test_question_bank_filters_by_grade(self):
        q10 = Question.objects.create(
            text='Lớp 10', subject=self.d.subject, created_by=self.d.teacher, grade='10'
        )
        q11 = Question.objects.create(
            text='Lớp 11', subject=self.d.subject, created_by=self.d.teacher, grade='11'
        )
        res = self.client.get('/api/exams/questions/', {'grade': '11'})
        self.assertEqual(res.status_code, 200)
        ids = {item['id'] for item in res.data['results']}
        self.assertIn(q11.pk, ids)
        self.assertNotIn(q10.pk, ids)
        self.assertNotIn(self.d.mc.pk, ids)

    def test_other_teacher_cannot_mutate_question_quiz_or_read_progress(self):
        self.client.force_authenticate(self.d.other_teacher)
        self.assertEqual(self.client.patch(f'/api/exams/questions/{self.d.mc.pk}/', {'text': 'Stolen'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/exams/{self.d.quiz.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/exams/analytics/{self.d.classroom.pk}/').status_code, 403)
        self.assertEqual(self.client.get('/api/exams/student-progress/', {
            'student_id': str(self.d.student.pk), 'class_id': str(self.d.classroom.pk),
        }).status_code, 403)
        self.d.mc.refresh_from_db()
        self.assertNotEqual(self.d.mc.text, 'Stolen')

    def test_removed_member_loses_quiz_access(self):
        res = self.client.delete(f'/api/classes/{self.d.classroom.pk}/students/{self.d.student.pk}/')
        self.assertEqual(res.status_code, 200, res.data)
        self.client.force_authenticate(self.d.student)
        self.assertEqual(self.client.get(f'/api/exams/{self.d.quiz.pk}/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/exams/{self.d.quiz.pk}/start/', {}, format='json').status_code, 403)

    def test_report_and_export_contain_correct_completed_score(self):
        StudentProfile.objects.create(user=self.d.student, student_code='REG-001')
        QuizAttempt.objects.create(quiz=self.d.quiz, student=self.d.student, score=0, is_completed=True)
        self.client.force_authenticate(self.d.admin)
        report = self.client.get('/api/accounts/admin/report/', {'class_id': str(self.d.classroom.pk)})
        self.assertEqual(report.status_code, 200, report.data)
        self.assertEqual(report.data['count'], 1)
        export = self.client.get('/api/accounts/admin/export/')
        self.assertEqual(export.status_code, 200)
        rows = list(load_workbook(io.BytesIO(export.content), read_only=True).active.values)
        self.assertIn('REG-001', str(rows))
        self.assertIn(self.d.quiz.title, str(rows))

    def test_malformed_filter_ids_do_not_raise_server_errors(self):
        for url in ('/api/exams/?class_id=bad', '/api/exams/questions/?subject=bad',
                    '/api/exams/student-progress/?class_id=bad', '/api/classes/not-a-uuid/'):
            with self.subTest(url=url):
                self.assertLess(self.client.get(url).status_code, 500)


class NotificationLifecycleTests(APITestCase):
    def setUp(self):
        self.d = seed_lms()

    def test_scheduled_publish_cron_is_idempotent_and_late_join_gets_notification(self):
        future = Quiz.objects.create(title='Hẹn giờ', classroom=self.d.classroom,
                                     created_by=self.d.teacher, is_published=True,
                                     publish_at=timezone.now() + timedelta(hours=1))
        self.assertFalse(Notification.objects.filter(target_id=future.pk).exists())
        Quiz.objects.filter(pk=future.pk).update(publish_at=timezone.now() - timedelta(seconds=1))
        for _ in range(2):
            call_command('notify_due_quizzes', stdout=io.StringIO())
        self.assertEqual(Notification.objects.filter(target_id=future.pk).count(), 1)
        ClassStudent.objects.create(classroom=self.d.classroom, student=self.d.outsider)
        self.assertEqual(Notification.objects.filter(target_id=future.pk).count(), 2)
        future.delete()
        self.assertFalse(Notification.objects.filter(target_id=future.pk).exists())

    def test_private_quiz_does_not_notify_classmates(self):
        quiz = Quiz.objects.create(title='Riêng', classroom=self.d.classroom,
                                   assigned_to=self.d.student, is_published=True, created_by=self.d.student)
        call_command('notify_due_quizzes', stdout=io.StringIO())
        self.assertFalse(Notification.objects.filter(target_id=quiz.pk).exclude(recipient=self.d.student).exists())

    def test_unpublish_removes_stale_notification(self):
        self.d.quiz.is_published = False
        self.d.quiz.save()
        self.assertFalse(Notification.objects.filter(target_id=self.d.quiz.pk).exists())

    @patch.dict(os.environ, {'CRON_SECRET': 'regression-cron'})
    def test_cron_rejects_missing_wrong_secret_and_invokes_command(self):
        self.assertEqual(self.client.get('/api/notifications/run-due/').status_code, 403)
        self.assertEqual(self.client.get('/api/notifications/run-due/', HTTP_AUTHORIZATION='Bearer wrong').status_code, 403)
        with patch('notifications.views.call_command') as command:
            self.assertEqual(self.client.get('/api/notifications/run-due/', HTTP_AUTHORIZATION='Bearer regression-cron').status_code, 200)
            command.assert_called_once_with('notify_due_quizzes')

    def test_pagination_unread_and_mark_all_are_scoped_to_user(self):
        Notification.objects.bulk_create([
            Notification(recipient=self.d.student, verb=Notification.VERB_PUBLISHED_QUIZ,
                         target_id=10000 + i, message=f'Test {i}') for i in range(25)
        ])
        other = Notification.objects.create(recipient=self.d.outsider, verb=Notification.VERB_PUBLISHED_QUIZ,
                                             target_id=9999, message='Private')
        self.client.force_authenticate(self.d.student)
        res = self.client.get('/api/notifications/')
        self.assertEqual(res.data['count'], 26)
        self.assertEqual(len(res.data['results']), 20)
        self.assertEqual(self.client.patch(f'/api/notifications/{other.pk}/read/').status_code, 404)
        self.assertEqual(self.client.post('/api/notifications/mark-all-read/').status_code, 200)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['count'], 0)
        other.refresh_from_db()
        self.assertFalse(other.is_read)


class AILifecycleTests(APITestCase):
    def setUp(self):
        self.d = seed_lms()
        self.client.force_authenticate(self.d.student)

    def test_quick_test_is_private_and_outsider_cannot_start(self):
        res = self.client.post('/api/ai/quick-test/', {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        quiz = Quiz.objects.get(pk=res.data['quiz_id'])
        self.assertEqual(quiz.assigned_to, self.d.student)
        self.assertTrue(quiz.quiz_questions.exists())
        self.client.force_authenticate(self.d.outsider)
        self.assertEqual(self.client.post(f'/api/exams/{quiz.pk}/start/', {}, format='json').status_code, 403)
        self.assertFalse(Notification.objects.filter(target_id=quiz.pk, recipient=self.d.outsider).exists())

    def test_quick_test_requires_class_membership(self):
        self.client.force_authenticate(self.d.outsider)
        self.assertEqual(self.client.post('/api/ai/quick-test/', {}, format='json').status_code, 400)

    def test_teacher_quick_test_is_shared_with_the_whole_class(self):
        self.client.force_authenticate(self.d.teacher)
        res = self.client.post('/api/ai/quick-test/', {'class_id': str(self.d.classroom.pk)}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        quiz = Quiz.objects.get(pk=res.data['quiz_id'])
        self.assertIsNone(quiz.assigned_to)
        self.assertEqual(quiz.classroom, self.d.classroom)
        self.assertEqual(quiz.created_by, self.d.teacher)

        self.client.force_authenticate(self.d.student)
        self.assertEqual(self.client.post(f'/api/exams/{quiz.pk}/start/', {}, format='json').status_code, 200)
        self.client.force_authenticate(self.d.outsider)
        self.assertEqual(self.client.post(f'/api/exams/{quiz.pk}/start/', {}, format='json').status_code, 403)

    def test_teacher_quick_test_rejects_another_teachers_class(self):
        self.client.force_authenticate(self.d.teacher)
        res = self.client.post('/api/ai/quick-test/', {'class_id': str(self.d.other_class.pk)}, format='json')
        self.assertEqual(res.status_code, 403)

    @patch('ai_core.views.ai_client.generate_content', return_value=SimpleNamespace(text='Lộ trình test'))
    def test_path_uses_only_current_students_completed_answers(self, generate):
        self.assertEqual(self.client.get('/api/ai/path/').status_code, 200)
        generate.assert_not_called()
        attempt = QuizAttempt.objects.create(quiz=self.d.quiz, student=self.d.student, is_completed=True, score=0)
        StudentAnswer.objects.create(attempt=attempt, quiz_question=self.d.qq, selected_option=self.d.wrong)
        res = self.client.get('/api/ai/path/')
        self.assertEqual(res.data['insight'], 'Lộ trình test')
        self.assertIn(self.d.mc.text, generate.call_args.args[0])

    @patch('ai_core.views.ai_client.generate_content', return_value=SimpleNamespace(text='Insight test'))
    def test_insight_cooldown_and_other_teacher_scope(self, generate):
        self.client.force_authenticate(self.d.teacher)
        payload = {'class_id': str(self.d.classroom.pk), 'analytics_data': {'average_score': 5}}
        self.assertEqual(self.client.post('/api/ai/insight/', payload, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/ai/insight/', payload, format='json').status_code, 429)
        self.assertEqual(generate.call_count, 1)
        ClassInsight.objects.filter(classroom=self.d.classroom).update(updated_at=timezone.now() - timedelta(days=6))
        self.assertEqual(self.client.post('/api/ai/insight/', payload, format='json').status_code, 200)
        self.client.force_authenticate(self.d.other_teacher)
        self.assertEqual(self.client.get('/api/ai/insight/', {'class_id': str(self.d.classroom.pk)}).status_code, 403)

    @patch('ai_core.views.AIGeneratorService.explain_wrong_answer', return_value='Giải thích test')
    def test_explanation_validation_and_output(self, explain):
        self.assertEqual(self.client.post('/api/ai/explain-wrong-answer/', {}, format='json').status_code, 400)
        res = self.client.post('/api/ai/explain-wrong-answer/', {
            'question_text': self.d.mc.text, 'correct_answer': '2', 'student_answer': '3',
        }, format='json')
        self.assertEqual(res.data['explanation'], 'Giải thích test')
        explain.assert_called_once()

    @patch('ai_core.views.AIGeneratorService.generate_from_rag', return_value=[{'text': 'Question'}])
    def test_selected_document_cannot_belong_to_another_class(self, generate):
        from ai_core.models import Document
        document = Document.objects.create(classroom=self.d.other_class, title='Private')
        self.client.force_authenticate(self.d.teacher)
        res = self.client.post('/api/ai/generate/from-rag/', {
            'class_id': str(self.d.classroom.pk), 'document_id': document.pk, 'topic': 'Mạng máy tính',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        generate.assert_not_called()
