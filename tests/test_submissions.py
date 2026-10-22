from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from itertools import product
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from exams.models import Option, Question, QuizAttempt, QuizQuestion, StudentAnswer
from tests.support import seed_lms


class ShortAnswerTests(SimpleTestCase):
    def test_numeric_and_text_equivalence(self):
        for expected, actual, correct in (
            ('0.5', ' 1 / 2 ', True), ('0,5', '0.50', True), ('ABC', ' aBc ', True),
            ('0', '0', True), ('1', '1/0', False), ('2', '', False), ('', '', False),
            ('2', '3', False),
        ):
            with self.subTest(expected=expected, actual=actual):
                answer = StudentAnswer(answer_text=actual)
                answer.quiz_question = QuizQuestion(question=Question(
                    question_type='short_answer', correct_answer_text=expected,
                ))
                self.assertEqual(answer.is_correct(), correct)


class SubmissionTests(APITestCase):
    def setUp(self):
        self.d = seed_lms()
        self.client.force_authenticate(self.d.student)

    def start(self):
        res = self.client.post(f'/api/exams/{self.d.quiz.pk}/start/', {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        return res

    def submit(self, answers, attempt=None):
        attempt = attempt or self.start().data['attempt_id']
        return self.client.post(f'/api/exams/attempt/{attempt}/submit/', {'answers': answers}, format='json')

    def answer(self, option=None):
        return {'quiz_question_id': self.d.qq.pk, 'selected_option_id': (option or self.d.correct).pk}

    def test_start_is_resumable_and_does_not_leak_answer_keys(self):
        first, second = self.start().data, self.start().data
        self.assertEqual(first['attempt_id'], second['attempt_id'])
        self.assertEqual(first['start_time'], second['start_time'])
        self.assertEqual(QuizAttempt.objects.count(), 1)
        for row in first['questions']:
            self.assertNotIn('correct_answer_text', row['question'])
            self.assertNotIn('explanation', row['question'])
            for option in row['question']['options']:
                self.assertNotIn('is_correct', option)
                self.assertNotIn('explanation', option)

    def test_success_review_progress_and_second_submission(self):
        attempt_id = self.start().data['attempt_id']
        res = self.submit([self.answer()], attempt_id)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['score'], 10)
        self.assertTrue(res.data['answers'][0]['is_correct'])
        attempt = QuizAttempt.objects.get(pk=attempt_id)
        self.assertTrue(attempt.is_completed)
        self.assertEqual(attempt.score, 10)
        self.assertIsNotNone(attempt.end_time)
        self.assertEqual(self.start().data['score'], 10)
        self.assertEqual(self.submit([self.answer(self.d.wrong)], attempt_id).status_code, 400)
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 10)
        self.client.force_authenticate(self.d.teacher)
        stats = self.client.get(f'/api/exams/analytics/{self.d.classroom.pk}/')
        self.assertEqual(stats.data['quizzes'][0]['average_score'], 10)

    def test_duplicate_and_foreign_options_cannot_inflate_score(self):
        foreign_q = Question.objects.create(subject=self.d.subject, text='Ngoài đề')
        foreign_option = Option.objects.create(question=foreign_q, text='Ngoài đề', is_correct=True)
        res = self.submit([self.answer(foreign_option), self.answer(), self.answer(),
                           {'quiz_question_id': 999999, 'selected_option_id': foreign_option.pk},
                           None, {'quiz_question_id': 'bad'}])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], 10)
        self.assertEqual(StudentAnswer.objects.count(), 1)
        self.assertEqual(StudentAnswer.objects.get().selected_option_id, self.d.correct.pk)

    def test_empty_wrong_and_foreign_answers_score_zero(self):
        for answers in ([], [self.answer(self.d.wrong)], [{'quiz_question_id': self.d.qq.pk, 'selected_option_id': -1}]):
            with self.subTest(answers=answers):
                QuizAttempt.objects.all().delete()
                res = self.submit(answers)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.data['score'], 0)

    def test_malformed_or_oversized_payload_does_not_complete_attempt(self):
        attempt_id = self.start().data['attempt_id']
        for answers in ({}, 'bad', None, [self.answer()] * 501):
            with self.subTest(payload_type=type(answers).__name__):
                self.assertEqual(self.submit(answers, attempt_id).status_code, 400)
                self.assertFalse(QuizAttempt.objects.get(pk=attempt_id).is_completed)
                self.assertFalse(StudentAnswer.objects.exists())

    def test_cannot_submit_someone_elses_attempt(self):
        attempt_id = self.start().data['attempt_id']
        self.client.force_authenticate(self.d.outsider)
        self.assertEqual(self.submit([self.answer()], attempt_id).status_code, 404)
        self.assertFalse(QuizAttempt.objects.get(pk=attempt_id).is_completed)

    def test_failure_mid_save_rolls_back_answers_and_attempt(self):
        attempt_id = self.start().data['attempt_id']
        original = StudentAnswer.objects.create(
            attempt_id=attempt_id, quiz_question=self.d.qq, selected_option=self.d.wrong,
        )
        with patch('exams.views.StudentAnswer.objects.create', side_effect=RuntimeError('injected write failure')):
            with self.assertRaisesMessage(RuntimeError, 'injected write failure'):
                self.submit([self.answer()], attempt_id)
        self.assertFalse(QuizAttempt.objects.get(pk=attempt_id).is_completed)
        self.assertTrue(StudentAnswer.objects.filter(pk=original.pk).exists())

    def test_start_requires_membership_publication_and_assignment(self):
        for changes, user, status in (
            ({'is_published': False}, self.d.student, 404),
            ({'is_published': True}, self.d.outsider, 403),
            ({'assigned_to': self.d.outsider}, self.d.student, 403),
        ):
            with self.subTest(changes=changes):
                for key, value in changes.items():
                    setattr(self.d.quiz, key, value)
                self.d.quiz.save()
                self.client.force_authenticate(user)
                res = self.client.post(f'/api/exams/{self.d.quiz.pk}/start/', {}, format='json')
                self.assertEqual(res.status_code, status)
                self.assertFalse(QuizAttempt.objects.exists())

    def test_publish_and_due_time_boundaries(self):
        now = timezone.now()
        for publish_delta, due_delta, status in ((1, 10, 403), (-10, -1, 403), (0, 0, 200)):
            with self.subTest(publish_delta=publish_delta, due_delta=due_delta):
                self.d.quiz.publish_at = now + timedelta(seconds=publish_delta)
                self.d.quiz.due_date = now + timedelta(seconds=due_delta)
                self.d.quiz.save()
                with patch('exams.views.timezone.now', return_value=now):
                    res = self.client.post(f'/api/exams/{self.d.quiz.pk}/start/', {}, format='json')
                self.assertEqual(res.status_code, status, res.data)

    def test_submission_duration_grace_and_due_date_boundaries(self):
        now = timezone.now()
        for elapsed, deadline_delta, status in ((1860, 0, 200), (1861, 60, 400), (1800, -1, 400)):
            with self.subTest(elapsed=elapsed, deadline_delta=deadline_delta):
                QuizAttempt.objects.all().delete()
                attempt = QuizAttempt.objects.create(quiz=self.d.quiz, student=self.d.student)
                QuizAttempt.objects.filter(pk=attempt.pk).update(start_time=now - timedelta(seconds=elapsed))
                self.d.quiz.due_date = now + timedelta(seconds=deadline_delta)
                self.d.quiz.save()
                with patch('exams.views.timezone.now', return_value=now):
                    res = self.submit([self.answer()], attempt.pk)
                self.assertEqual(res.status_code, status, res.data)
                self.assertEqual(QuizAttempt.objects.get(pk=attempt.pk).is_completed, status == 200)

    def test_weighted_mixed_quiz_and_zero_total(self):
        short = Question.objects.create(subject=self.d.subject, question_type='short_answer',
                                        text='Một nửa', correct_answer_text='0.5')
        qq = QuizQuestion.objects.create(quiz=self.d.quiz, question=short, order=2, points=3)
        self.d.qq.points = 7
        self.d.qq.save()
        res = self.submit([self.answer(self.d.wrong), {'quiz_question_id': qq.pk, 'answer_text': ' 1/2 '}])
        self.assertEqual(res.data['score'], 3)
        self.assertEqual(StudentAnswer.objects.get(quiz_question=qq).answer_text, '1/2')
        QuizAttempt.objects.all().delete()
        QuizQuestion.objects.filter(quiz=self.d.quiz).update(points=0)
        self.assertEqual(self.submit([self.answer()]).data['score'], 0)

    def test_true_false_preserves_boolean_for_all_sixteen_answer_patterns(self):
        self.d.mc.question_type = 'true_false'
        self.d.mc.save()
        self.d.mc.options.all().delete()
        options = [Option.objects.create(question=self.d.mc, text=f'Nhận định {i}') for i in range(4)]
        for pattern in product((False, True), repeat=4):
            for option, expected in zip(options, pattern):
                option.is_correct = expected
                option.save()
            for invert, score in ((False, 10), (True, 0)):
                with self.subTest(pattern=pattern, invert=invert):
                    QuizAttempt.objects.all().delete()
                    res = self.submit([{
                        'quiz_question_id': self.d.qq.pk, 'selected_option_id': option.pk,
                        'answer_value': expected != invert,
                    } for option, expected in zip(options, pattern)])
                    self.assertEqual(res.status_code, 200)
                    self.assertEqual(res.data['score'], score)


class SubmissionRaceTests(TransactionTestCase):
    def setUp(self):
        self.d = seed_lms()

    def test_concurrent_submit_commits_only_one_result(self):
        attempt = QuizAttempt.objects.create(quiz=self.d.quiz, student=self.d.student)
        barrier = Barrier(2)

        def submit():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.d.student)
                barrier.wait(timeout=10)
                return client.post(f'/api/exams/attempt/{attempt.pk}/submit/', {'answers': [{
                    'quiz_question_id': self.d.qq.pk, 'selected_option_id': self.d.correct.pk,
                }]}, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(StudentAnswer.objects.filter(attempt=attempt).count(), 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 10)

    def test_concurrent_start_creates_only_one_attempt(self):
        barrier = Barrier(2)
        # Synchronize the initial misses so both requests exercise the create race.
        from django.db.models.query import QuerySet
        original_get = QuerySet.get

        def get(queryset, *args, **kwargs):
            try:
                return original_get(queryset, *args, **kwargs)
            except QuizAttempt.DoesNotExist:
                barrier.wait(timeout=10)
                raise

        def start():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.d.student)
                return client.post(f'/api/exams/{self.d.quiz.pk}/start/', {}, format='json').status_code
            finally:
                connections.close_all()

        with patch.object(QuerySet, 'get', get), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: start(), range(2)))
        self.assertEqual(results, [200, 200])
        self.assertEqual(QuizAttempt.objects.filter(quiz=self.d.quiz, student=self.d.student).count(), 1)
