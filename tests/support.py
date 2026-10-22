from types import SimpleNamespace

from accounts.models import Role, User
from classes.models import Class, ClassStudent, Subject
from exams.models import Option, Question, Quiz, QuizQuestion


PASSWORD = 'RegressionPass987!'


def seed_lms():
    data = SimpleNamespace()
    for name, role_name in (('teacher', 'teacher'), ('other_teacher', 'teacher'),
                            ('student', 'student'), ('outsider', 'student'), ('admin', 'admin')):
        role, _ = Role.objects.get_or_create(name=role_name)
        setattr(data, name, User.objects.create_user(
            username=name, email=f'{name}@example.com', password=PASSWORD, role=role,
        ))
    data.subject = Subject.objects.create(name='Tin học regression')
    data.classroom = Class.objects.create(name='Lớp regression', subject=data.subject, teacher=data.teacher)
    data.other_class = Class.objects.create(name='Lớp khác', subject=data.subject, teacher=data.other_teacher)
    ClassStudent.objects.create(classroom=data.classroom, student=data.student)
    data.quiz = Quiz.objects.create(
        title='Đề regression', classroom=data.classroom, created_by=data.teacher,
        is_published=True, duration_minutes=30,
    )
    data.mc = Question.objects.create(
        subject=data.subject, created_by=data.teacher, question_type='multiple_choice',
        text='1 + 1 bằng bao nhiêu?', explanation='Một cộng một bằng hai.',
    )
    data.correct = Option.objects.create(question=data.mc, text='2', is_correct=True)
    data.wrong = Option.objects.create(question=data.mc, text='3', is_correct=False)
    data.qq = QuizQuestion.objects.create(quiz=data.quiz, question=data.mc, order=1, points=10)
    return data
