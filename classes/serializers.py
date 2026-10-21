from rest_framework import serializers
from .models import Class, ClassStudent, Subject
from accounts.serializers import UserSerializer


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']


class ClassSerializer(serializers.ModelSerializer):
    teacher = UserSerializer(read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    student_count = serializers.SerializerMethodField()
    total_quizzes = serializers.SerializerMethodField()
    total_attempts = serializers.SerializerMethodField()
    avg_score = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = ['id', 'name', 'subject', 'subject_name', 'teacher', 'invite_code', 'description', 'created_at', 'student_count', 'total_quizzes', 'total_attempts', 'avg_score']
        read_only_fields = ['invite_code', 'teacher', 'subject_name', 'student_count', 'total_quizzes', 'total_attempts', 'avg_score']

    def get_student_count(self, obj):
        return obj.class_students.count()

    def get_total_quizzes(self, obj):
        return obj.quizzes.count()

    @staticmethod
    def _attempts_prefetched(obj):
        cache = getattr(obj, '_prefetched_objects_cache', {})
        if 'quizzes' not in cache:
            return False
        return all(
            'attempts' in getattr(quiz, '_prefetched_objects_cache', {})
            for quiz in cache['quizzes']
        )

    def get_total_attempts(self, obj):
        if self._attempts_prefetched(obj):
            return sum(
                1
                for quiz in obj.quizzes.all()
                for attempt in quiz.attempts.all()
                if attempt.is_completed
            )
        from exams.models import QuizAttempt
        return QuizAttempt.objects.filter(quiz__classroom=obj, is_completed=True).count()

    def get_avg_score(self, obj):
        if self._attempts_prefetched(obj):
            scores = [
                attempt.score
                for quiz in obj.quizzes.all()
                for attempt in quiz.attempts.all()
                if attempt.is_completed and attempt.score is not None
            ]
            return round(sum(scores) / len(scores), 2) if scores else 0.0
        from exams.models import QuizAttempt
        from django.db.models import Avg
        avg = QuizAttempt.objects.filter(quiz__classroom=obj, is_completed=True).aggregate(Avg('score'))['score__avg']
        return round(avg, 2) if avg else 0.0
