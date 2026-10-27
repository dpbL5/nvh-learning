"""Database-free tests for the exam-taking/scoring module.

All exam data is built from lightweight mock objects, so these tests run under
SimpleTestCase without creating or touching a real database.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from exams.models import Option, Question, QuizQuestion, StudentAnswer
from exams.scoring import (
    calculate_score,
    coerce_answer_value,
    is_answer_correct,
    score_submission,
)


class MockOptions(list):
    """Stand-in for the related manager exposed as ``question.options``."""

    def all(self):
        return list(self)

    def count(self):
        return len(self)


def make_option(pk, is_correct):
    return SimpleNamespace(pk=pk, id=pk, is_correct=is_correct)


def make_question(question_type='multiple_choice', options=(), correct_answer_text=None):
    return SimpleNamespace(
        question_type=question_type,
        options=MockOptions(options),
        correct_answer_text=correct_answer_text,
    )


def make_quiz_question(pk, question, points):
    return SimpleNamespace(pk=pk, id=pk, question=question, points=points)


def grade(quiz_questions, answers):
    answers_by_question = {}
    for answer in answers:
        answers_by_question.setdefault(answer['quiz_question_id'], []).append(answer)
    decisions, earned_points, total_points = score_submission(quiz_questions, answers_by_question)
    return calculate_score(earned_points, total_points), decisions


class MultipleChoiceScoringTests(SimpleTestCase):
    def test_perfect_submission_scores_ten(self):
        quiz_questions = [
            make_quiz_question(1, make_question(options=[
                make_option(11, True), make_option(12, False),
            ]), 5),
            make_quiz_question(2, make_question(options=[
                make_option(21, False), make_option(22, True),
            ]), 5),
        ]

        score, decisions = grade(quiz_questions, [
            {'quiz_question_id': 1, 'selected_option_id': 11},
            {'quiz_question_id': 2, 'selected_option_id': 22},
        ])

        self.assertEqual(score, 10.0)
        self.assertEqual(len(decisions), 2)
        self.assertTrue(all(decision['is_correct'] for decision in decisions))

    def test_unanswered_question_forfeits_its_points(self):
        quiz_questions = [
            make_quiz_question(1, make_question(options=[
                make_option(11, True), make_option(12, False),
            ]), 5),
            make_quiz_question(2, make_question(options=[
                make_option(21, True), make_option(22, False),
            ]), 5),
        ]

        score, _ = grade(quiz_questions, [
            {'quiz_question_id': 1, 'selected_option_id': 11},
        ])

        self.assertEqual(score, 5.0)

    def test_foreign_and_duplicate_options_are_ignored(self):
        quiz_question = make_quiz_question(1, make_question(options=[
            make_option(11, True), make_option(12, False),
        ]), 10)

        score, decisions = grade([quiz_question], [
            {'quiz_question_id': 1, 'selected_option_id': 999},
            {'quiz_question_id': 1, 'selected_option_id': 11},
            {'quiz_question_id': 1, 'selected_option_id': 11},
            {'quiz_question_id': 1, 'selected_option_id': 12},
        ])

        self.assertEqual(score, 10.0)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]['selected_option'].pk, 11)


class TrueFalseScoringTests(SimpleTestCase):
    def make_statements(self, points=10, correct_pattern=(True, False, True, False)):
        options = [make_option(index, is_correct) for index, is_correct in enumerate(correct_pattern, start=1)]
        return make_quiz_question(1, make_question('true_false', options), points)

    def test_perfect_answers_score_ten_when_key_contains_false_statements(self):
        quiz_question = self.make_statements()

        score, decisions = grade([quiz_question], [
            {'quiz_question_id': 1, 'selected_option_id': 1, 'answer_value': True},
            {'quiz_question_id': 1, 'selected_option_id': 2, 'answer_value': False},
            {'quiz_question_id': 1, 'selected_option_id': 3, 'answer_value': True},
            {'quiz_question_id': 1, 'selected_option_id': 4, 'answer_value': False},
        ])

        self.assertEqual(score, 10.0)
        self.assertEqual([decision['is_correct'] for decision in decisions], [True, True, True, True])
        self.assertEqual([decision['answer_value'] for decision in decisions], [True, False, True, False])

    def test_marking_every_statement_true_against_key_gets_partial_credit(self):
        quiz_question = self.make_statements(points=8)

        score, decisions = grade([quiz_question], [
            {'quiz_question_id': 1, 'selected_option_id': index, 'answer_value': True}
            for index in range(1, 5)
        ])

        self.assertEqual(score, 5.0)
        self.assertEqual([decision['is_correct'] for decision in decisions], [True, False, True, False])

    def test_partial_credit_uses_all_statements_as_denominator(self):
        quiz_question = self.make_statements(points=8)

        score, decisions = grade([quiz_question], [
            {'quiz_question_id': 1, 'selected_option_id': 1, 'answer_value': True},
        ])

        self.assertEqual(score, 2.5)
        self.assertEqual(len(decisions), 1)

    def test_legacy_payload_without_answer_value_implies_true(self):
        quiz_question = self.make_statements(points=10, correct_pattern=(True, False))

        score, decisions = grade([quiz_question], [
            {'quiz_question_id': 1, 'selected_option_id': 1},
            {'quiz_question_id': 1, 'selected_option_id': 2},
        ])

        self.assertEqual(score, 5.0)
        self.assertEqual([decision['answer_value'] for decision in decisions], [None, None])
        self.assertEqual([decision['is_correct'] for decision in decisions], [True, False])


class ShortAnswerScoringTests(SimpleTestCase):
    def test_numeric_and_text_equivalence(self):
        for expected, actual, correct in (
            ('0.5', ' 1 / 2 ', True),
            ('0,5', '0.50', True),
            ('ABC', ' aBc ', True),
            ('10', '10.0', True),
            ('2', '3', False),
            ('2', '', False),
            ('2', None, False),
        ):
            with self.subTest(expected=expected, actual=actual):
                question = make_question('short_answer', correct_answer_text=expected)
                self.assertEqual(
                    is_answer_correct(question, answer_text=actual), correct,
                )

    def test_correct_answer_scores_full_points(self):
        quiz_question = make_quiz_question(
            1, make_question('short_answer', correct_answer_text='0.5'), 10,
        )

        score, decisions = grade([quiz_question], [
            {'quiz_question_id': 1, 'answer_text': ' 1 / 2 '},
        ])

        self.assertEqual(score, 10.0)
        self.assertEqual(decisions[0]['answer_text'], '1 / 2')


class MixedExamScoringTests(SimpleTestCase):
    def test_perfect_mixed_exam_scores_ten(self):
        quiz_questions = [
            make_quiz_question(1, make_question(options=[
                make_option(11, True), make_option(12, False),
            ]), 6),
            make_quiz_question(2, make_question('true_false', [
                make_option(21, True), make_option(22, False),
                make_option(23, True), make_option(24, False),
            ]), 1),
            make_quiz_question(3, make_question('short_answer', correct_answer_text='12'), 3),
        ]

        score, decisions = grade(quiz_questions, [
            {'quiz_question_id': 1, 'selected_option_id': 11},
            {'quiz_question_id': 2, 'selected_option_id': 21, 'answer_value': True},
            {'quiz_question_id': 2, 'selected_option_id': 22, 'answer_value': False},
            {'quiz_question_id': 2, 'selected_option_id': 23, 'answer_value': True},
            {'quiz_question_id': 2, 'selected_option_id': 24, 'answer_value': False},
            {'quiz_question_id': 3, 'answer_text': '12'},
        ])

        self.assertEqual(score, 10.0)
        self.assertEqual(len(decisions), 6)
        self.assertTrue(all(decision['is_correct'] for decision in decisions))

    def test_points_are_normalised_to_a_ten_point_scale(self):
        quiz_question = make_quiz_question(1, make_question('true_false', [
            make_option(1, True), make_option(2, False),
        ]), 1)

        score, _ = grade([quiz_question], [
            {'quiz_question_id': 1, 'selected_option_id': 1, 'answer_value': True},
            {'quiz_question_id': 1, 'selected_option_id': 2, 'answer_value': False},
        ])

        self.assertEqual(score, 10.0)

    def test_no_points_available_scores_zero(self):
        self.assertEqual(calculate_score(0, 0), 0.0)

        quiz_question = make_quiz_question(1, make_question(options=[
            make_option(11, True), make_option(12, False),
        ]), 0)
        score, _ = grade([quiz_question], [
            {'quiz_question_id': 1, 'selected_option_id': 11},
        ])
        self.assertEqual(score, 0.0)


class AnswerValueCoercionTests(SimpleTestCase):
    def test_boolean_numeric_and_string_values(self):
        for raw, expected in (
            (True, True), (False, False), (1, True), (0, False),
            ('true', True), ('FALSE', False), ('1', True), ('0', False),
            ('sai', None), (None, None),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(coerce_answer_value(raw), expected)


class StudentAnswerModelTests(SimpleTestCase):
    def test_is_correct_honours_answer_value_for_true_false(self):
        question = Question(question_type='true_false')
        statement = Option(question=question, is_correct=False)
        quiz_question = QuizQuestion(question=question)

        answer = StudentAnswer(
            quiz_question=quiz_question,
            selected_option=statement,
            answer_value=False,
        )
        self.assertTrue(answer.is_correct())

        answer.answer_value = True
        self.assertFalse(answer.is_correct())
