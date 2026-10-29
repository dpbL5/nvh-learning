from rest_framework import serializers
from .models import Question, Option, Quiz, QuizQuestion, QuizAttempt, StudentAnswer, ImageBank, QuestionImage
from classes.models import Subject, Class


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'content_json', 'is_correct', 'explanation']


class ImageBankSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ImageBank
        fields = [
            'sha256', 'image_url', 'original_filename', 'mime_type', 'file_size',
            'width_pt', 'height_pt', 'created_at',
        ]

    def get_image_url(self, obj):
        request = self.context.get('request')
        if not obj.image_file:
            return None
        
        # Nếu url đã lưu là direct URL (Cloudinary)
        if obj.image_file.name.startswith('http'):
            return obj.image_file.name

        url = obj.image_file.url
        if request:
            return request.build_absolute_uri(url)
        return url


class QuestionImageSerializer(serializers.ModelSerializer):
    image = ImageBankSerializer(read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = QuestionImage
        fields = [
            'id', 'image', 'image_url', 'position', 'placement', 'source_type',
            'uploaded_by', 'uploaded_by_username', 'note', 'created_at',
        ]


from django.db import transaction

class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)
    question_images = QuestionImageSerializer(many=True, read_only=True)
    options_data = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    images_data = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    grade_display = serializers.CharField(source='get_grade_display', read_only=True)
    question_type_display = serializers.CharField(
        source='get_question_type_display', read_only=True
    )
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'question_type_display',
            'subject', 'subject_name', 'difficulty', 'grade', 'grade_display',
            'text', 'question_text', 'topic', 'content_json', 'context', 'image', 'correct_answer_text',
            'created_at', 'options', 'question_images', 'options_data', 'images_data',
            'can_edit',
        ]

    def get_can_edit(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        role_name = getattr(user.role, 'name', None)
        return role_name == 'admin' or user.is_superuser or obj.created_by_id == user.id

    def _blocks_to_text(self, blocks):
        if not isinstance(blocks, list):
            return ''
        parts = []
        for b in blocks:
            if isinstance(b, dict) and b.get('type') == 'text' and isinstance(b.get('value'), str):
                parts.append(b.get('value'))
        return ' '.join(parts).strip()

    def _has_image_block(self, blocks):
        if not isinstance(blocks, list):
            return False
        return any(isinstance(b, dict) and b.get('type') == 'image' for b in blocks)

    def _heal_content_images(self, blocks):
        """
        Scan text blocks for [IMG:sha256] and split them into text and image blocks.
        """
        if not isinstance(blocks, list): return []
        import re
        new_blocks = []
        img_pattern = re.compile(r'\[IMG:([a-fA-F0-9]{32,64})\]')
        
        for b in blocks:
            if isinstance(b, dict) and b.get('type') == 'text' and b.get('value'):
                val = str(b.get('value'))
                last_end = 0
                for match in img_pattern.finditer(val):
                    start, end = match.span()
                    if start > last_end:
                        new_blocks.append({'type': 'text', 'value': val[last_end:start]})
                    new_blocks.append({'type': 'image', 'sha256': match.group(1)})
                    last_end = end
                if last_end < len(val):
                    new_blocks.append({'type': 'text', 'value': val[last_end:]})
            else:
                new_blocks.append(b)
        return new_blocks

    def validate(self, attrs):
        content_json = self.initial_data.get('content_json') or attrs.get('content_json')
        text = self.initial_data.get('text') or attrs.get('text', '')
        text = str(text).strip() if text else ''

        if content_json is not None and not text:
            text = self._blocks_to_text(content_json)

        if content_json is not None and not text and not self._has_image_block(content_json):
            raise serializers.ValidationError({"text": "Question content cannot be empty"})

        attrs['text'] = text
        if content_json is not None:
             # Heal images in blocks if they contain [IMG:sha] text
             content_json = self._heal_content_images(content_json)
             attrs['content_json'] = content_json
             
        # Add to options too
        opts = self.initial_data.get('options', [])
        for opt in opts:
            if 'content_json' in opt:
                opt['content_json'] = self._heal_content_images(opt['content_json'])
            elif 'text' in opt:
                 opt['content_json'] = self._build_content_json_from_text(opt['text'])
        
        attrs['options_data'] = opts
        
        # Only set images_data if it was explicitly provided to prevent accidental deletion
        images_data = self.initial_data.get('question_images', self.initial_data.get('images_data'))
        if images_data is not None:
             attrs['images_data'] = images_data

        return attrs

    def _build_content_json_from_text(self, text):
        return self._heal_content_images([{'type': 'text', 'value': text}])

    def create(self, validated_data):
        options_data = validated_data.pop('options_data', [])
        images_data = validated_data.pop('images_data', [])
        created_by = validated_data.pop('created_by', None)
        
        request = self.context.get('request')
        user = created_by or (request.user if request else None)

        with transaction.atomic():
            question = Question.objects.create(created_by=user, **validated_data)
            self._handle_options(question, options_data)
            self._handle_images(question, images_data, user)
            return question

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options_data', None)
        images_data = validated_data.pop('images_data', None)
        validated_data.pop('created_by', None) # Don't update creator
        
        request = self.context.get('request')
        user = request.user if request else getattr(instance, 'created_by', None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            if options_data is not None:
                instance.options.all().delete()
                self._handle_options(instance, options_data)
                
            if images_data is not None:
                instance.question_images.all().delete()
                self._handle_images(instance, images_data, user)
                
            return instance

    def _handle_options(self, question, options_data):
        if not isinstance(options_data, list):
            return
        for opt in options_data:
            opt_content = opt.get('content_json')
            opt_text = str(opt.get('text') or '').strip()
            if not opt_text and isinstance(opt_content, list):
                opt_text = self._blocks_to_text(opt_content)
                
            Option.objects.create(
                question=question,
                text=opt_text,
                content_json=opt_content or [],
                is_correct=opt.get('is_correct', False)
            )

    def _handle_images(self, question, images_data, user):
        if not isinstance(images_data, list):
            return
        from ai_core.services.cloudinary_service import (
            cloudinary_asset_from_url,
            is_allowed_remote_url,
        )
        for img in images_data:
            sha256 = img.get('sha256')
            url = img.get('url') or img.get('image_url')
            
            img_bank = None
            if sha256:
                img_bank, created = ImageBank.objects.get_or_create(
                    sha256=sha256,
                    defaults={
                        'original_filename': img.get('original_filename', ''),
                        'mime_type': 'image/jpeg',
                        'width_pt': img.get('width_pt'),
                        'height_pt': img.get('height_pt')
                    }
                )
                
                if url and (created or not img_bank.image_file or not img_bank.image_file.name.startswith('http')):
                    img_bank.image_file.name = url
                    if is_allowed_remote_url(url):
                        public_id, _ = cloudinary_asset_from_url(url)
                        if public_id:
                            img_bank.cloudinary_public_id = public_id
                    img_bank.save()

            if not img_bank and not url:
                continue

            QuestionImage.objects.create(
                question=question,
                image=img_bank,
                image_url=url if not img_bank else None,
                placement=img.get('placement', 'stem'),
                position=int(img.get('position', 0)),
                source_type=img.get('source_type', 'user_upload'),
                uploaded_by=user,
                note=img.get('note', '')
            )


class QuizQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer(read_only=True)
    question_id = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all(), source='question', write_only=True
    )
    quiz = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = QuizQuestion
        fields = ['id', 'quiz', 'question', 'question_id', 'order', 'points', 'is_points_overridden']
        read_only_fields = ['is_points_overridden']

    def validate_points(self, value):
        if value < 0 or value > 10:
            raise serializers.ValidationError('Điểm mỗi câu phải nằm trong khoảng 0 đến 10.')
        return value


class QuizSerializer(serializers.ModelSerializer):
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    subject_name = serializers.CharField(source='classroom.subject.name', read_only=True)
    subject_id = serializers.IntegerField(source='classroom.subject.id', read_only=True)
    question_count = serializers.SerializerMethodField()
    my_attempt = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField()
    duration_minutes = serializers.IntegerField(min_value=1, max_value=600, required=False)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'classroom', 'classroom_name',
            'subject_name', 'subject_id', 'duration_minutes', 'is_published', 'publish_at',
            'created_at', 'due_date', 'question_count', 'my_attempt', 'average_score'
        ]

    def get_question_count(self, obj):
        return obj.quiz_questions.count()

    def validate(self, attrs):
        if 'publish_at' in attrs or 'due_date' in attrs:
            publish_at = attrs.get('publish_at', getattr(self.instance, 'publish_at', None))
            due_date = attrs.get('due_date', getattr(self.instance, 'due_date', None))
            if publish_at and due_date and due_date <= publish_at:
                raise serializers.ValidationError({'due_date': 'Hạn nộp phải sau thời điểm công khai.'})
        return attrs

    def get_my_attempt(self, obj):
        user = self.context.get('request').user
        if not user or user.is_anonymous:
            return None
        if hasattr(obj, '_prefetched_objects_cache') and 'attempts' in obj._prefetched_objects_cache:
            attempt = next((a for a in obj.attempts.all() if a.student_id == user.id), None)
        else:
            attempt = QuizAttempt.objects.filter(quiz=obj, student=user).first()
        if attempt:
            return {
                'id': attempt.id,
                'score': attempt.score,
                'is_completed': attempt.is_completed,
                'start_time': attempt.start_time,
            }
        return None

    def get_average_score(self, obj):
        if not obj.is_published:
            return None
        if hasattr(obj, '_prefetched_objects_cache') and 'attempts' in obj._prefetched_objects_cache:
            scores = [a.score for a in obj.attempts.all() if a.is_completed and a.score is not None]
            return round(sum(scores) / len(scores), 2) if scores else 0
        from django.db.models import Avg
        stats = QuizAttempt.objects.filter(quiz=obj, is_completed=True).aggregate(avg_score=Avg('score'))
        return round(stats['avg_score'], 2) if stats['avg_score'] is not None else 0


class QuizAttemptSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_title', 'student', 'student_name',
            'start_time', 'end_time', 'score', 'is_completed',
        ]

    def get_student_name(self, obj):
        return f"{obj.student.last_name} {obj.student.first_name}".strip() or obj.student.username


# ─── Public (Student) Read-Only Serializers (Anti-Cheat) ─────────────────────

class OptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'content_json']  # Không phơi bày is_correct


class QuestionPublicSerializer(serializers.ModelSerializer):
    options = OptionPublicSerializer(many=True)
    question_images = QuestionImageSerializer(many=True)

    class Meta:
        model = Question
        fields = ['id', 'question_type', 'text', 'question_text', 'topic', 'content_json', 'context', 'image', 'options', 'question_images']
        # Lưu ý: KHÔNG trả correct_answer_text cho học sinh


class QuizQuestionPublicSerializer(serializers.ModelSerializer):
    question = QuestionPublicSerializer()

    class Meta:
        model = QuizQuestion
        fields = ['id', 'question', 'order', 'points']

# ─── Review (Student) Serializers (Post-Exam) ──────────────────────────────

class OptionReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'content_json', 'is_correct', 'explanation']


class QuestionReviewSerializer(serializers.ModelSerializer):
    options = OptionReviewSerializer(many=True, read_only=True)
    question_images = QuestionImageSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'text', 'question_text', 'topic', 'content_json', 'context',
            'image', 'options', 'question_images', 'correct_answer_text', 'explanation',
            'subject_name', 'difficulty', 'difficulty_display'
        ]


class StudentAnswerReviewSerializer(serializers.ModelSerializer):
    is_correct = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentAnswer
        fields = ['id', 'quiz_question', 'selected_option', 'answer_text', 'answer_value', 'is_correct']

    def get_is_correct(self, obj):
        return obj.is_correct()



class QuizQuestionReviewSerializer(serializers.ModelSerializer):
    question = QuestionReviewSerializer(read_only=True)
    
    class Meta:
        model = QuizQuestion
        fields = ['id', 'question', 'order', 'points']


class QuizAttemptReviewSerializer(serializers.ModelSerializer):
    answers = StudentAnswerReviewSerializer(many=True, read_only=True)
    questions = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'score', 'is_completed', 'answers', 'questions']

    def get_questions(self, obj):
        quiz_questions = QuizQuestion.objects.filter(quiz=obj.quiz).select_related('question').prefetch_related('question__options', 'question__question_images__image')
        return QuizQuestionReviewSerializer(quiz_questions, many=True, context=self.context).data
