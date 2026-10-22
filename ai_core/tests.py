import json
from itertools import product
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from ai_core.models import Document, DocumentChunk
from ai_core.services.ai_generator import AIGeneratorService, NoQuestionsGenerated
from ai_core.services import openai_client
from classes.models import Class, ClassStudent, Subject


class OpenAIClientTests(SimpleTestCase):
    def setUp(self):
        self.client_patch = patch('ai_core.services.openai_client._client')
        self.client = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.choice = SimpleNamespace(
            finish_reason='stop',
            message=SimpleNamespace(content='{"questions": []}', refusal=None),
        )
        self.client.chat.completions.create.return_value = SimpleNamespace(choices=[self.choice])

    def test_luna_uses_completion_tokens_without_retry_or_sampling(self):
        response = openai_client.generate_content('Trả về JSON.', model='gpt-6-luna', config={
            'response_mime_type': 'application/json', 'max_output_tokens': 8192,
            'temperature': 0.2, 'top_p': 0.9,
        })
        self.client.chat.completions.create.assert_called_once()
        payload = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(payload['model'], 'gpt-6-luna')
        self.assertEqual(payload['max_completion_tokens'], 8192)
        self.assertNotIn('max_tokens', payload)
        self.assertNotIn('temperature', payload)
        self.assertNotIn('top_p', payload)
        self.assertEqual(payload['response_format'], {'type': 'json_object'})
        self.assertEqual(AIGeneratorService._parse_model_json(response.text), [])

    def test_legacy_model_keeps_sampling_settings(self):
        openai_client.generate_content('Xin chào.', model='gpt-4o-mini', config={'temperature': 0.1})
        payload = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(payload['temperature'], 0.1)
        self.assertNotIn('response_format', payload)

    def test_incomplete_refused_or_empty_response_raises(self):
        for reason, content, refusal in (
            ('length', '{"questions": []}', None),
            ('content_filter', None, None),
            ('stop', None, 'Refused'),
            ('stop', None, None),
            ('stop', '  ', None),
        ):
            with self.subTest(reason=reason, content=content, refusal=refusal):
                self.choice.finish_reason = reason
                self.choice.message.content = content
                self.choice.message.refusal = refusal
                with self.assertRaises(ValueError):
                    openai_client.generate_content('Tạo câu hỏi.', model='gpt-6-luna')
        self.client.chat.completions.create.return_value.choices = []
        with self.assertRaises(ValueError):
            openai_client.generate_content('Tạo câu hỏi.', model='gpt-6-luna')


class AIQuestionJSONTests(SimpleTestCase):
    def test_accepts_wrapped_and_legacy_lists_including_empty(self):
        for questions in ([], [{'text': 'Câu hỏi mẫu'}]):
            for payload in (questions, {'questions': questions}, {'items': questions}):
                for text in (json.dumps(payload), f'```json\n{json.dumps(payload)}\n```'):
                    with self.subTest(text=text):
                        self.assertEqual(AIGeneratorService._parse_model_json(text), questions)

    def test_rejects_missing_question_list_and_invalid_json(self):
        for text in ('{}', '{"questions": null}', '{"options": []}', '{"error": "Failed"}', 'null', 'not JSON'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                AIGeneratorService._parse_model_json(text)

    def test_keeps_recovery_of_legacy_truncated_arrays(self):
        self.assertEqual(
            AIGeneratorService._parse_model_json('[{"text": "Câu 1"}, {"text": "Câu 2'),
            [{'text': 'Câu 1'}],
        )

    def test_true_false_without_text_uses_question_title_as_transition(self):
        generated = [{
            'question_type': 'true_false',
            'question_text': 'Ứng dụng IoT trong nhà kính',
            'context': 'Một nhà kính sử dụng cảm biến để theo dõi nhiệt độ.',
            'options': [
                {'text': f'Nhận định {label}', 'is_correct': label in ('a', 'c')}
                for label in 'abcd'
            ],
            'difficulty': 'medium',
            'topic': 'Internet vạn vật',
            'subject': 'Tin học',
            'explanation': 'Lời giải mẫu.',
        }]

        normalized = AIGeneratorService._normalize_questions(generated)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]['question_text'], 'Ứng dụng IoT trong nhà kính')
        self.assertEqual(
            normalized[0]['text'],
            'Có một số nhận định về Ứng dụng IoT trong nhà kính như sau:',
        )
        self.assertEqual(len(normalized[0]['options']), 4)


class RAGServiceTests(SimpleTestCase):
    def setUp(self):
        self.ai_patch = patch('ai_core.services.ai_generator.ai_client')
        self.ai = self.ai_patch.start()
        self.addCleanup(self.ai_patch.stop)
        self.ai.embed_content.return_value = [0.0] * 768
        self.chunks_patch = patch('ai_core.models.DocumentChunk.objects')
        self.chunks = self.chunks_patch.start()
        self.addCleanup(self.chunks_patch.stop)
        self.query = self.chunks.filter.return_value
        self.query.filter.return_value = self.query
        self.retrieved = self.query.annotate.return_value.order_by.return_value.__getitem__

    @patch('classes.models.Class.objects')
    def test_generation_without_rag_preserves_question_types_and_explanation(self, classrooms):
        classrooms.select_related.return_value.get.return_value.subject.name = 'Tin học'
        self.retrieved.return_value = []
        learning_outcomes = 'Nêu được chức năng của switch.\nLựa chọn thiết bị phù hợp để kết nối mạng.'
        for question_type in ('multiple_choice', 'true_false', 'short_answer'):
            with self.subTest(question_type=question_type):
                draft = {
                    'question_type': question_type,
                    'text': 'Câu hỏi mẫu',
                    'context': 'Bối cảnh mẫu' if question_type == 'true_false' else '',
                    'explanation': 'Lời giải. Kiến thức nền bổ sung ngoài tài liệu lớp học.',
                    'correct_answer_text': '42' if question_type == 'short_answer' else '',
                    'options': [] if question_type == 'short_answer' else [
                        {'text': f'Phương án {i}', 'is_correct': i == 0} for i in range(4)
                    ],
                }
                self.ai.generate_content.return_value.text = json.dumps({'questions': [draft]})
                result = AIGeneratorService.generate_from_rag(
                    learning_outcomes, 1, 'class-1', question_type, document_id=7,
                )
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['question_type'], question_type)
                self.assertEqual(result[0]['explanation'], draft['explanation'])
                self.assertEqual(result[0]['correct_answer_text'], draft['correct_answer_text'])
                self.assertEqual(len(result[0]['options']), len(draft['options']))
                prompt = self.ai.generate_content.call_args.args[0]
                self.assertIn('Không tìm thấy nội dung trong tài liệu lớp học', prompt)
                self.assertIn(f'"question_type\": "{question_type}"', prompt)
                self.assertIn('Tin học', prompt)
                self.assertIn(f'<learning_outcomes>\n{learning_outcomes}\n</learning_outcomes>', prompt)
        self.chunks.filter.assert_called_with(document__classroom_id='class-1')
        self.query.filter.assert_called_with(document_id=7)

    @patch('classes.models.Class.objects')
    def test_blank_outcome_uses_selected_source_without_default_outcomes(self, classrooms):
        classrooms.select_related.return_value.get.return_value.subject.name = 'Tin học'
        self.query.order_by.return_value.__getitem__.return_value = [SimpleNamespace(
            content='Switch kết nối các thiết bị trong mạng LAN.',
            document=SimpleNamespace(title='Mạng máy tính'),
        )]
        self.ai.generate_content.return_value.text = json.dumps({'questions': [{
            'question_type': 'multiple_choice',
            'text': 'Thiết bị nào phù hợp để kết nối các máy tính trong mạng LAN?',
            'options': [
                {'text': 'Switch.', 'is_correct': True},
                {'text': 'Máy in.', 'is_correct': False},
                {'text': 'Máy quét.', 'is_correct': False},
                {'text': 'Loa.', 'is_correct': False},
            ],
            'explanation': 'Biết: nhận biết chức năng của switch.',
        }]})

        result = AIGeneratorService.generate_from_rag('', 1, 'class-1')

        self.assertEqual(len(result), 1)
        prompt = self.ai.generate_content.call_args.args[0]
        self.assertIn('<learning_outcomes>\n\n</learning_outcomes>', prompt)
        self.assertIn('Switch kết nối các thiết bị trong mạng LAN.', prompt)
        self.assertNotIn('KHUNG CẤP ĐỘ TƯ DUY', prompt)

    @patch('classes.models.Class.objects')
    def test_true_false_generation_preserves_every_answer_pattern(self, classrooms):
        classrooms.select_related.return_value.get.return_value.subject.name = 'Tin học'
        self.retrieved.return_value = []
        for answers in product((False, True), repeat=4):
            with self.subTest(answers=answers):
                explanation = '\n'.join(
                    f'{label}) {"Đúng" if answer else "Sai"}: Lời giải cho ý {label}.'
                    for label, answer in zip('abcd', answers)
                )
                draft = {
                    'question_type': 'true_false',
                    'text': 'Có các nhận định về hệ thống mạng như sau:',
                    'context': 'Một đơn vị đang triển khai hệ thống mạng.',
                    'options': [
                        {'text': f'Nhận định {label}', 'is_correct': answer}
                        for label, answer in zip('abcd', answers)
                    ],
                    'correct_option': 'A',
                    'explanation': explanation,
                }
                self.ai.generate_content.return_value.text = json.dumps([draft])
                result = AIGeneratorService.generate_from_rag(
                    'Mạng máy tính', 1, 'class-1', 'true_false',
                )
                self.assertEqual(len(result), 1)
                self.assertEqual(tuple(o['is_correct'] for o in result[0]['options']), answers)
                self.assertEqual(result[0]['explanation'], explanation)

    def test_multiple_choice_still_uses_answer_key(self):
        result = AIGeneratorService._normalize_questions([{
            'question_type': 'multiple_choice',
            'text': 'Chọn phương án đúng.',
            'options': [{'text': f'Phương án {label}'} for label in 'ABCD'],
            'correct_option': 'C',
        }])
        self.assertEqual([o['is_correct'] for o in result[0]['options']], [False, False, True, False])

    @patch('classes.models.Class.objects')
    def test_generation_keeps_retrieved_source_and_requires_relevance_check(self, classrooms):
        classrooms.select_related.return_value.get.return_value.subject.name = 'Tin học'
        self.retrieved.return_value = [SimpleNamespace(
            content='Nội dung không liên quan đến mạng máy tính.',
            document=SimpleNamespace(title='Bài học khác'),
        )]
        self.ai.generate_content.return_value.text = '[]'
        with self.assertRaisesMessage(NoQuestionsGenerated, 'AI không nêu lý do'):
            AIGeneratorService.generate_from_rag('Mạng máy tính', 2, 'class-1')
        prompt = self.ai.generate_content.call_args.args[0]
        self.assertIn('[Bài học khác]: Nội dung không liên quan', prompt)
        self.assertIn('Kết quả truy xuất có thể không liên quan', prompt)
        self.assertIn('được dùng kiến thức nền đáng tin cậy', prompt)

    @patch('classes.models.Class.objects')
    def test_empty_generation_reports_reason_or_actionable_fallback(self, classrooms):
        classrooms.select_related.return_value.get.return_value.subject.name = 'Tin học'
        self.retrieved.return_value = []
        reason = 'Cần bổ sung nội dung chức năng của thiết bị được yêu cầu trong bài.'
        for payload, expected in (
            ({'questions': [], 'reason': reason}, reason),
            ({'questions': [], 'reason': '  '}, 'AI không nêu lý do'),
            ({'questions': [], 'reason': []}, 'AI không nêu lý do'),
            ([], 'AI không nêu lý do'),
        ):
            with self.subTest(payload=payload):
                self.ai.generate_content.return_value.text = json.dumps(payload)
                with self.assertRaisesMessage(NoQuestionsGenerated, expected):
                    AIGeneratorService.generate_from_rag('Nêu được chức năng của switch.', 1, 'class-1')

    @patch('classes.models.Class.objects')
    def test_generation_rejects_questions_removed_by_normalization(self, classrooms):
        classrooms.select_related.return_value.get.return_value.subject.name = 'Tin học'
        self.retrieved.return_value = []
        self.ai.generate_content.return_value.text = '{"questions": [{"text": ""}]}'
        with self.assertRaisesMessage(ValueError, 'thiếu nội dung hợp lệ'):
            AIGeneratorService.generate_from_rag('Nêu được chức năng của switch.', 1, 'class-1')

    @patch('classes.models.Class.objects')
    def test_no_outcomes_and_no_document_content_does_not_call_ai(self, classrooms):
        classrooms.select_related.return_value.get.return_value.subject.name = 'Tin học'
        self.query.order_by.return_value.__getitem__.return_value = []
        with self.assertRaisesMessage(NoQuestionsGenerated, 'Chưa có nội dung tài liệu'):
            AIGeneratorService.generate_from_rag('  ', 1, 'class-1')
        self.ai.embed_content.assert_not_called()
        self.ai.generate_content.assert_not_called()

    def test_tutor_answers_with_and_without_retrieved_context(self):
        chunk = SimpleNamespace(content='Máy tính kết nối qua switch.', document=SimpleNamespace(title='Bài LAN'))
        for chunks in ([], [chunk]):
            with self.subTest(has_context=bool(chunks)):
                self.retrieved.return_value = chunks
                self.ai.generate_content.return_value.text = 'Câu trả lời mẫu'
                self.assertEqual(AIGeneratorService.chat_with_tutor('class-1', 'LAN là gì?'), 'Câu trả lời mẫu')
                prompt = self.ai.generate_content.call_args.args[0]
                self.assertIn('LAN là gì?', prompt)
                self.assertIn('[Bài LAN]' if chunks else 'Không tìm thấy nội dung trong tài liệu lớp học', prompt)
                self.assertIn('Kiến thức nền bổ sung ngoài tài liệu lớp học', prompt)
                self.assertIn('Đọc SOURCE trước', prompt)
        self.chunks.filter.assert_called_with(document__classroom_id='class-1')
        self.ai.embed_content.assert_called_with(
            content='LAN là gì?', task_type='RETRIEVAL_QUERY', output_dimensionality=768,
        )


class AICoreApiTests(APITestCase):
	def setUp(self):
		self.student_role, _ = Role.objects.get_or_create(name=Role.STUDENT)
		self.teacher_role, _ = Role.objects.get_or_create(name=Role.TEACHER)
		self.admin_role, _ = Role.objects.get_or_create(name=Role.ADMIN)

		self.teacher = User.objects.create_user(
			username='teacher_ai',
			email='teacher_ai@example.com',
			password='TeacherPass123',
			role=self.teacher_role,
		)
		self.student = User.objects.create_user(
			username='student_ai',
			email='student_ai@example.com',
			password='StudentPass123',
			role=self.student_role,
		)
		self.student2 = User.objects.create_user(
			username='student_ai_2',
			email='student_ai_2@example.com',
			password='StudentPass123',
			role=self.student_role,
		)
		self.admin = User.objects.create_user(
			username='admin_ai',
			email='admin_ai@example.com',
			password='AdminPass123',
			role=self.admin_role,
			is_staff=True,
		)

		self.subject = Subject.objects.create(name='Tin hoc')
		self.classroom = Class.objects.create(
			name='12C1',
			subject=self.subject,
			teacher=self.teacher,
		)
		ClassStudent.objects.create(classroom=self.classroom, student=self.student)
		self.document = Document.objects.create(
			classroom=self.classroom,
			title='Bai giang 1',
			file_url='https://res.cloudinary.com/demo/raw/upload/bai_giang_1.docx',
		)

	def _auth(self, username, password):
		login_res = self.client.post(
			'/api/accounts/login/',
			{'username': username, 'password': password},
			format='json',
		)
		token = login_res.data['access']
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

	def test_rag_chat_requires_auth(self):
		res = self.client.post('/api/ai/chat/', {'class_id': str(self.classroom.id), 'question': 'test'}, format='json')
		self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('ai_core.views.ai_client.is_configured', return_value=False)
	def test_rag_chat_returns_500_when_api_key_missing(self, _):
		self._auth('student_ai', 'StudentPass123')
		res = self.client.post(
			'/api/ai/chat/',
			{'class_id': str(self.classroom.id), 'question': 'Noi dung bai hoc la gi?'},
			format='json',
		)
		self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

	def test_list_documents_forbidden_for_student_not_in_class(self):
		self._auth('student_ai_2', 'StudentPass123')
		res = self.client.get(f'/api/ai/classes/{self.classroom.id}/documents/')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

	def test_list_documents_allowed_for_enrolled_student(self):
		self._auth('student_ai', 'StudentPass123')
		res = self.client.get(f'/api/ai/classes/{self.classroom.id}/documents/')
		self.assertEqual(res.status_code, status.HTTP_200_OK)
		self.assertEqual(len(res.data), 1)

	def test_ai_insight_forbidden_for_student(self):
		self._auth('student_ai', 'StudentPass123')
		res = self.client.post('/api/ai/insight/', {'analytics_data': {'avg': 7.5}}, format='json')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

	def test_ai_insight_requires_analytics_data(self):
		self._auth('teacher_ai', 'TeacherPass123')
		res = self.client.post('/api/ai/insight/', {'class_name': '12C1'}, format='json')
		self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

	def test_upload_document_forbidden_for_student(self):
		self._auth('student_ai', 'StudentPass123')
		res = self.client.post(f'/api/ai/classes/{self.classroom.id}/documents/upload/', {}, format='multipart')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

	def test_delete_document_allowed_for_admin(self):
		self._auth('admin_ai', 'AdminPass123')
		res = self.client.delete(f'/api/ai/documents/{self.document.id}/')
		self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

	def test_generate_from_rag_requires_class_id(self):
		self._auth('teacher_ai', 'TeacherPass123')
		payload = {'topic': 'On tap hoc ky', 'count': 3, 'difficulty': 'medium'}
		res = self.client.post('/api/ai/generate/from-rag/', payload, format='json')
		self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

	@patch('ai_core.services.ai_generator.ai_client')
	def test_generate_from_rag_with_optional_outcomes_uses_selected_document(self, ai):
		self.client.force_authenticate(user=self.teacher)
		content = 'Switch kết nối các thiết bị trong mạng cục bộ; Access Point kết nối thiết bị Wi-Fi vào mạng có dây.'
		DocumentChunk.objects.create(document=self.document, chunk_index=0, content=content)
		ai.generate_content.return_value.text = json.dumps({'questions': [{
			'question_type': 'short_answer', 'text': 'Câu hỏi mẫu', 'correct_answer_text': '42',
		}]})
		for extra in ({}, {'topic': None}, {'topic': ''}, {'topic': '  '}):
			with self.subTest(extra=extra):
				res = self.client.post('/api/ai/generate/from-rag/', {
					'class_id': str(self.classroom.id), 'document_id': self.document.id,
					'count': 1, 'question_types': 'short_answer', **extra,
				}, format='json')
				self.assertEqual(res.status_code, status.HTTP_200_OK)
				self.assertEqual(len(res.data['questions']), 1)
				self.assertIn(content, ai.generate_content.call_args.args[0])
		ai.embed_content.assert_not_called()

	@patch('ai_core.views.AIGeneratorService.generate_from_rag', return_value=[{'text': 'Câu hỏi mẫu'}])
	def test_generate_from_rag_ignores_legacy_difficulty(self, generate):
		self.client.force_authenticate(user=self.teacher)
		for extra in ({}, {'difficulty': 'hard'}):
			with self.subTest(extra=extra):
				generate.reset_mock()
				payload = {
					'class_id': str(self.classroom.id),
					'topic': 'Nêu được chức năng của switch.\nLựa chọn thiết bị kết nối mạng phù hợp.',
					'count': 3, 'question_types': 'true_false', **extra,
				}
				res = self.client.post('/api/ai/generate/from-rag/', payload, format='json')
				self.assertEqual(res.status_code, status.HTTP_200_OK)
				self.assertEqual(res.data['questions'], generate.return_value)
				generate.assert_called_once_with(
					topic=payload['topic'], count=3, class_id=str(self.classroom.id),
					question_types='true_false', document_id=None,
				)

	def test_generate_from_rag_forbidden_for_student(self):
		self._auth('student_ai', 'StudentPass123')
		payload = {'class_id': str(self.classroom.id), 'topic': 'Chu de A'}
		res = self.client.post('/api/ai/generate/from-rag/', payload, format='json')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

	@patch('ai_core.views.AIGeneratorService.generate_from_rag', return_value=[])
	def test_generate_from_rag_never_returns_200_for_empty_questions(self, generate):
		self.client.force_authenticate(user=self.teacher)
		for reason in (None, 'Cần bổ sung kiến thức được yêu cầu trong bài.'):
			with self.subTest(reason=reason):
				generate.side_effect = NoQuestionsGenerated(reason) if reason else None
				res = self.client.post('/api/ai/generate/from-rag/', {
					'class_id': str(self.classroom.id), 'topic': 'Nêu được chức năng của switch.',
				}, format='json')
				self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
				self.assertNotIn('questions', res.data)
				self.assertIn(reason or 'kiểm tra yêu cầu cần đạt', res.data['error'])

	@patch('ai_core.views.AIGeneratorService.generate_from_rag', side_effect=ValueError('Invalid AI JSON'))
	def test_generate_from_rag_returns_error_for_invalid_ai_response(self, generate):
		self.client.force_authenticate(user=self.teacher)
		res = self.client.post('/api/ai/generate/from-rag/', {
			'class_id': str(self.classroom.id), 'topic': 'Nêu được chức năng của switch.',
		}, format='json')
		self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
		self.assertIn('Phản hồi AI không hợp lệ', res.data['error'])
		self.assertNotIn('questions', res.data)

	@patch('ai_core.views.AIGeneratorService.ingest_document', side_effect=Exception('boom'))
	@patch('ai_core.views.delete_from_cloudinary')
	@patch('requests.get')
	@patch('ai_core.views.is_allowed_remote_url', return_value=True)
	def test_upload_document_deletes_cloudinary_asset_when_ingestion_fails(
		self, _allowed, mock_get, mock_delete, _ingest
	):
		mock_get.return_value.iter_content.return_value = [b'test file content']
		self._auth('teacher_ai', 'TeacherPass123')
		res = self.client.post(
			f'/api/ai/classes/{self.classroom.id}/documents/upload/',
			{
				'file_url': 'https://res.cloudinary.com/demo/raw/upload/v1234/bai_giang_2.docx',
				'file_name': 'bai_giang_2.docx',
			},
			format='json',
		)
		self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
		mock_delete.assert_called_once_with('bai_giang_2.docx', resource_type='raw')
		self.assertEqual(Document.objects.filter(classroom=self.classroom).count(), 1)

	@patch('ai_core.views.AIGeneratorService.extract_from_file', side_effect=Exception('boom'))
	@patch('ai_core.views.delete_from_cloudinary')
	@patch('requests.Session.get')
	@patch('ai_core.views.is_allowed_remote_url', return_value=True)
	def test_extract_file_deletes_uploaded_assets_on_failure(
		self, _allowed, mock_get, mock_delete, _extract
	):
		mock_get.return_value.iter_content.return_value = [b'test file content']
		self._auth('teacher_ai', 'TeacherPass123')
		res = self.client.post(
			'/api/ai/generate/extract-file/',
			{
				'files': [{
					'file_url': 'https://res.cloudinary.com/demo/raw/upload/v1234/bai_giang_2.docx',
					'file_name': 'bai_giang_2.docx',
					'public_id': 'bai_giang_2.docx',
					'resource_type': 'raw',
				}],
			},
			format='json',
		)
		self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
		mock_delete.assert_called_once_with('bai_giang_2.docx', resource_type='raw')
