"""Pure scoring helpers for exam submissions.

Everything here works on in-memory objects (questions, options, payload dicts)
and never touches the database, so it can be unit-tested with mock data.
"""

import re
from fractions import Fraction

MAX_ANSWER_TEXT_LENGTH = 500

QUESTION_TYPE_MULTIPLE_CHOICE = 'multiple_choice'
QUESTION_TYPE_TRUE_FALSE = 'true_false'
QUESTION_TYPE_SHORT_ANSWER = 'short_answer'


def normalize_short_answer(value):
    text = re.sub(r'\s+', '', str(value or '').strip().lower().replace(',', '.'))
    if not text:
        return ''
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return text


def coerce_answer_value(value):
    """Normalise a true/false value coming from the client.

    Returns None when the client did not send a usable value (legacy payloads).
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ('true', '1'):
            return True
        if normalized in ('false', '0'):
            return False
    return None


def is_answer_correct(question, selected_option=None, answer_text=None, answer_value=None):
    question_type = getattr(question, 'question_type', QUESTION_TYPE_MULTIPLE_CHOICE)

    if question_type == QUESTION_TYPE_SHORT_ANSWER:
        correct = getattr(question, 'correct_answer_text', None)
        if not correct or answer_text is None:
            return False
        actual = str(answer_text).strip()
        if not actual:
            return False
        return normalize_short_answer(actual) == normalize_short_answer(correct)

    if selected_option is None:
        return False

    if question_type == QUESTION_TYPE_TRUE_FALSE:
        # The selected option only identifies the statement; the student's
        # Đúng/Sai decision is carried by answer_value. Older clients omitted
        # it and implied "Đúng" by selecting the statement.
        truth_value = coerce_answer_value(answer_value)
        if truth_value is None:
            truth_value = True
        return bool(selected_option.is_correct) == truth_value

    return bool(selected_option.is_correct)


def calculate_score(earned_points, total_points):
    if not total_points or total_points <= 0:
        return 0.0
    return min(10.0, round(earned_points / total_points * 10, 2))


def _option_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _lookup_option(options_by_id, raw_option_id):
    option_id = _option_id(raw_option_id)
    if option_id is None:
        return None
    return options_by_id.get(option_id)


def _decision(quiz_question, selected_option=None, answer_text=None,
              answer_value=None, is_correct=False):
    return {
        'quiz_question': quiz_question,
        'selected_option': selected_option,
        'answer_text': answer_text,
        'answer_value': answer_value,
        'is_correct': is_correct,
    }


def score_submission(quiz_questions, answers_by_question):
    """Grade a submission against in-memory quiz questions.

    ``answers_by_question`` maps a ``QuizQuestion.pk`` to the raw payload rows
    for that question. Returns ``(decisions, earned_points, total_points)``
    where each decision is a dict ready to be persisted as a StudentAnswer.
    """
    decisions = []
    earned_points = 0.0
    total_points = 0.0

    for quiz_question in quiz_questions:
        points = quiz_question.points or 0.0
        total_points += points

        raw_answers = answers_by_question.get(quiz_question.pk) or []
        if not raw_answers:
            continue

        question = quiz_question.question
        question_type = getattr(question, 'question_type', QUESTION_TYPE_MULTIPLE_CHOICE)

        if question_type == QUESTION_TYPE_SHORT_ANSWER:
            answer_text = next(
                (
                    str(raw.get('answer_text')).strip()
                    for raw in raw_answers
                    if raw.get('answer_text') is not None and str(raw.get('answer_text')).strip()
                ),
                None,
            )
            if answer_text is None:
                continue
            answer_text = answer_text[:MAX_ANSWER_TEXT_LENGTH]
            correct = is_answer_correct(question, answer_text=answer_text)
            decisions.append(_decision(
                quiz_question, answer_text=answer_text, is_correct=correct,
            ))
            if correct:
                earned_points += points
            continue

        options = list(question.options.all())
        options_by_id = {option.pk: option for option in options}

        if question_type == QUESTION_TYPE_TRUE_FALSE:
            answered = []
            seen_option_ids = set()
            for raw in raw_answers:
                option = _lookup_option(options_by_id, raw.get('selected_option_id'))
                if option is None or option.pk in seen_option_ids:
                    continue
                seen_option_ids.add(option.pk)
                answer_value = raw.get('answer_value')
                correct = is_answer_correct(
                    question, selected_option=option, answer_value=answer_value,
                )
                answered.append((option, answer_value, correct))

            if not answered:
                continue

            statement_count = len(options) or 1
            correct_count = sum(1 for _, _, correct in answered if correct)
            for option, answer_value, correct in answered:
                decisions.append(_decision(
                    quiz_question,
                    selected_option=option,
                    answer_value=coerce_answer_value(answer_value),
                    is_correct=correct,
                ))
            earned_points += points * correct_count / statement_count
            continue

        selected_option = None
        for raw in raw_answers:
            selected_option = _lookup_option(options_by_id, raw.get('selected_option_id'))
            if selected_option is not None:
                break

        if selected_option is None:
            continue

        correct = is_answer_correct(question, selected_option=selected_option)
        decisions.append(_decision(
            quiz_question, selected_option=selected_option, is_correct=correct,
        ))
        if correct:
            earned_points += points

    return decisions, earned_points, total_points
