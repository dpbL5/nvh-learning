import random

from rest_framework import status
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Role, User
from classes.models import Class, ClassStudent, Subject
from exams.models import Option, Question, Quiz, QuizQuestion, QuizAttempt, ImageBank, QuestionImage


class ExamsApiTests(APITestCase):
	def setUp(self):
		self.student_role, _ = Role.objects.get_or_create(name=Role.STUDENT)
		self.teacher_role, _ = Role.objects.get_or_create(name=Role.TEACHER)

		self.teacher = User.objects.create_user(
			username='teacher_exam',
			email='teacher_exam@example.com',
			password='TeacherPass123',
			role=self.teacher_role,
		)
		self.student = User.objects.create_user(
			username='student_exam',
			email='student_exam@example.com',
			password='StudentPass123',
			role=self.student_role,
		)
		self.student2 = User.objects.create_user(
			username='student_exam_2',
			email='student_exam_2@example.com',
			password='StudentPass123',
			role=self.student_role,
		)

		self.subject = Subject.objects.create(name='Sinh')
		self.classroom = Class.objects.create(
			name='12B1',
			subject=self.subject,
			teacher=self.teacher,
		)
		ClassStudent.objects.create(classroom=self.classroom, student=self.student)

		self.question = Question.objects.create(
			question_type='multiple_choice',
			text='1 + 1 = ?',
			subject=self.subject,
			difficulty='easy',
			created_by=self.teacher,
		)
		self.correct_option = Option.objects.create(question=self.question, text='2', is_correct=True)
		self.wrong_option = Option.objects.create(question=self.question, text='3', is_correct=False)

		self.quiz = Quiz.objects.create(
			title='Quiz test',
			classroom=self.classroom,
			duration_minutes=30,
			is_published=True,
			created_by=self.teacher,
		)
		self.quiz_question = QuizQuestion.objects.create(
			quiz=self.quiz,
			question=self.question,
			order=1,
			points=1.0,
		)

	def _auth(self, username, password):
		login_res = self.client.post(
			'/api/accounts/login/',
			{'username': username, 'password': password},
			format='json',
		)
		token = login_res.data['access']
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

	def test_student_cannot_create_question(self):
		self._auth('student_exam', 'StudentPass123')
		payload = {
			'question_type': 'multiple_choice',
			'text': 'Cau hoi moi',
			'subject': self.subject.id,
			'difficulty': 'easy',
		}
		res = self.client.post('/api/exams/questions/', payload, format='json')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

	def test_teacher_can_create_question(self):
		self._auth('teacher_exam', 'TeacherPass123')
		payload = {
			'question_type': 'multiple_choice',
			'text': 'Cau hoi GV tao',
			'subject': self.subject.id,
			'difficulty': 'medium',
		}
		res = self.client.post('/api/exams/questions/', payload, format='json')
		self.assertEqual(res.status_code, status.HTTP_201_CREATED)

	def test_student_start_quiz_forbidden_if_not_in_class(self):
		self._auth('student_exam_2', 'StudentPass123')
		res = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

	def test_review_filter_accepts_true_false_with_all_false_statements(self):
		questions = {}
		for question_type in ('true_false', 'multiple_choice'):
			question = Question.objects.create(
				question_type=question_type, text='Câu hỏi cần xét',
				subject=self.subject, created_by=self.teacher,
			)
			Option.objects.bulk_create([
				Option(question=question, text=f'Ý {label}', is_correct=False)
				for label in 'abcd'
			])
			questions[question_type] = question
		empty_question = Question.objects.create(
			question_type='true_false', text='Câu hỏi chưa có nhận định',
			subject=self.subject, created_by=self.teacher,
		)
		self.client.force_authenticate(user=self.teacher)
		res = self.client.get('/api/exams/questions/', {'status': 'needs_review'})
		self.assertEqual(res.status_code, status.HTTP_200_OK)
		rows = res.data['results'] if isinstance(res.data, dict) else res.data
		question_ids = {row['id'] for row in rows}
		self.assertNotIn(questions['true_false'].id, question_ids)
		self.assertIn(questions['multiple_choice'].id, question_ids)
		self.assertIn(empty_question.id, question_ids)

	def test_student_submit_quiz_calculates_score(self):
		self._auth('student_exam', 'StudentPass123')

		start_res = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		self.assertEqual(start_res.status_code, status.HTTP_200_OK)
		attempt_id = start_res.data['attempt_id']

		submit_payload = {
			'answers': [
				{
					'quiz_question_id': self.quiz_question.id,
					'selected_option_id': self.correct_option.id,
				}
			]
		}
		submit_res = self.client.post(f'/api/exams/attempt/{attempt_id}/submit/', submit_payload, format='json')
		self.assertEqual(submit_res.status_code, status.HTTP_200_OK)
		self.assertEqual(submit_res.data['score'], 10.0)

		attempt = QuizAttempt.objects.get(id=attempt_id)
		self.assertTrue(attempt.is_completed)
		self.assertEqual(attempt.score, 10.0)

	def test_quiz_start_returns_question_images_payload(self):
		# 1x1 transparent PNG
		png_bytes = (
			b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
			b'\x00\x00\x00\x0cIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe5\'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82'
		)
		img = ImageBank.objects.create(
			sha256='a' * 64,
			image_file=SimpleUploadedFile('tiny.png', png_bytes, content_type='image/png'),
		)
		QuestionImage.objects.create(
			question=self.question,
			image=img,
			placement='stem',
			position=0,
			source_type='system',
		)
		self.question.content_json = [{'type': 'image', 'sha256': img.sha256}]
		self.question.save(update_fields=['content_json'])

		self._auth('student_exam', 'StudentPass123')
		res = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		self.assertEqual(res.status_code, status.HTTP_200_OK)
		self.assertTrue(res.data['questions'])
		q_payload = res.data['questions'][0]['question']
		self.assertIn('question_images', q_payload)
		self.assertEqual(len(q_payload['question_images']), 1)
		self.assertEqual(q_payload['question_images'][0]['image']['sha256'], img.sha256)

	def test_update_full_accepts_content_json_for_question_and_options(self):
		self._auth('teacher_exam', 'TeacherPass123')
		payload = {
			'subject': self.subject.id,
			'text': '',
			'content_json': [{'type': 'text', 'value': 'Noi dung tu block'}],
			'question_type': 'multiple_choice',
			'difficulty': 'medium',
			'options': [
				{'text': '', 'content_json': [{'type': 'text', 'value': 'PA A'}], 'is_correct': True},
				{'text': '', 'content_json': [{'type': 'text', 'value': 'PA B'}], 'is_correct': False},
			],
		}
		res = self.client.put(f'/api/exams/questions/{self.question.id}/update-full/', payload, format='json')
		self.assertEqual(res.status_code, status.HTTP_200_OK)
		self.assertEqual(res.data['text'], 'Noi dung tu block')
		self.assertEqual(len(res.data['options']), 2)
		self.assertEqual(res.data['options'][0]['text'], 'PA A')

	def test_quiz_start_shuffles_questions_stably_per_attempt(self):
		for index in range(5):
			question = Question.objects.create(
				question_type='multiple_choice',
				text=f'Câu phụ {index}',
				subject=self.subject,
				created_by=self.teacher,
			)
			Option.objects.create(question=question, text='Đúng', is_correct=True)
			Option.objects.create(question=question, text='Sai', is_correct=False)
			QuizQuestion.objects.create(quiz=self.quiz, question=question, order=index + 2, points=1.0)

		self._auth('student_exam', 'StudentPass123')
		first = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		self.assertEqual(first.status_code, status.HTTP_200_OK)
		first_ids = [row['id'] for row in first.data['questions']]

		second = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		second_ids = [row['id'] for row in second.data['questions']]

		# Cùng một lượt thi: tải lại không đổi thứ tự.
		self.assertEqual(first_ids, second_ids)
		# Vẫn đủ câu, chỉ đổi thứ tự.
		canonical_ids = list(
			QuizQuestion.objects.filter(quiz=self.quiz).order_by('order').values_list('id', flat=True)
		)
		self.assertEqual(sorted(first_ids), sorted(canonical_ids))

		# Nộp bài theo ID vẫn chấm đúng dù thứ tự hiển thị đã xáo.
		answers = []
		for row in first.data['questions']:
			question = Question.objects.get(pk=row['question']['id'])
			correct = question.options.get(is_correct=True)
			answers.append({'quiz_question_id': row['id'], 'selected_option_id': correct.pk})
		res = self.client.post(
			f"/api/exams/attempt/{first.data['attempt_id']}/submit/",
			{'answers': answers}, format='json',
		)
		self.assertEqual(res.status_code, status.HTTP_200_OK)
		self.assertEqual(res.data['score'], 10.0)

	def test_quiz_start_orders_mcq_first_and_true_false_last(self):
		for question_type, order in (
			('true_false', 2),
			('multiple_choice', 3),
			('true_false', 4),
			('short_answer', 5),
		):
			question = Question.objects.create(
				question_type=question_type,
				text=f'Câu {question_type} {order}',
				subject=self.subject,
				created_by=self.teacher,
			)
			QuizQuestion.objects.create(quiz=self.quiz, question=question, order=order, points=1.0)

		self._auth('student_exam', 'StudentPass123')
		res = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		self.assertEqual(res.status_code, status.HTTP_200_OK)

		types = [row['question']['question_type'] for row in res.data['questions']]
		self.assertEqual(len(types), 5)
		# Trắc nghiệm (kể cả câu có sẵn trong setUp) đứng đầu.
		self.assertEqual(types[:2], ['multiple_choice', 'multiple_choice'])
		# Đúng/sai đứng cuối.
		self.assertEqual(types[-2:], ['true_false', 'true_false'])
		self.assertEqual(types[2], 'short_answer')

	def test_quiz_start_shuffles_options_and_strips_embedded_labels(self):
		question = Question.objects.create(
			question_type='multiple_choice',
			text='Chọn phương án đúng',
			subject=self.subject,
			created_by=self.teacher,
		)
		options = [
			Option.objects.create(
				question=question,
				text=f'{label}. Nội dung {index}',
				is_correct=(index == 0),
			)
			for index, label in enumerate('ABCD')
		]
		QuizQuestion.objects.create(quiz=self.quiz, question=question, order=2, points=1.0)

		self._auth('student_exam', 'StudentPass123')
		first = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		row = next(r for r in first.data['questions'] if r['question']['id'] == question.id)

		# Nhãn A./B./... bị bỏ khỏi nội dung phương án.
		self.assertEqual(
			sorted(option['text'] for option in row['question']['options']),
			['Nội dung 0', 'Nội dung 1', 'Nội dung 2', 'Nội dung 3'],
		)

		# Thứ tự phương án được xáo theo seed của lượt thi.
		returned_ids = [option['id'] for option in row['question']['options']]
		expected_ids = [option.id for option in options]
		random.Random(f"{first.data['attempt_id']}:{row['id']}:options").shuffle(expected_ids)
		self.assertEqual(returned_ids, expected_ids)

		# Tải lại trong cùng lượt không đổi thứ tự.
		second = self.client.post(f'/api/exams/{self.quiz.id}/start/', {}, format='json')
		row2 = next(r for r in second.data['questions'] if r['question']['id'] == question.id)
		self.assertEqual(returned_ids, [option['id'] for option in row2['question']['options']])

		# Trang xem lại dùng cùng thứ tự phương án với lúc làm bài.
		submit = self.client.post(
			f"/api/exams/attempt/{first.data['attempt_id']}/submit/",
			{'answers': [
				{'quiz_question_id': row['id'], 'selected_option_id': options[0].id},
			]},
			format='json',
		)
		self.assertEqual(submit.status_code, status.HTTP_200_OK)
		review_row = next(
			r for r in submit.data['questions'] if r['question']['id'] == question.id
		)
		self.assertEqual(
			[option['id'] for option in review_row['question']['options']],
			returned_ids,
		)

	def test_teacher_progress_endpoint_for_teacher_and_admin(self):
		# create completed attempts for current quiz
		QuizAttempt.objects.create(quiz=self.quiz, student=self.student, score=8.0, is_completed=True)
		QuizAttempt.objects.create(quiz=self.quiz, student=self.student2, score=9.5, is_completed=True)

		# teacher should see data
		self._auth('teacher_exam', 'TeacherPass123')
		res = self.client.get('/api/exams/teacher-progress/')
		self.assertEqual(res.status_code, status.HTTP_200_OK)
		self.assertIn('quizzes', res.data)
		self.assertEqual(len(res.data['quizzes']), 1)
		quiz_data = res.data['quizzes'][0]
		self.assertEqual(quiz_data['quiz_title'], self.quiz.title)
		self.assertAlmostEqual(quiz_data['average_score'], 8.75, places=2)
		self.assertEqual(quiz_data['total_attempts'], 2)

		# create admin user and check visibility for admin too
		admin_role, _ = Role.objects.get_or_create(name=Role.ADMIN)
		admin = User.objects.create_user(username='admin_exam', email='admin_exam@example.com', password='AdminPass123', role=admin_role, is_superuser=True)
		self._auth('admin_exam', 'AdminPass123')
		res_admin = self.client.get('/api/exams/teacher-progress/')
		self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
		self.assertEqual(len(res_admin.data['quizzes']), 1)

	def test_teacher_progress_endpoint_forbidden_for_student(self):
		self._auth('student_exam', 'StudentPass123')
		res = self.client.get('/api/exams/teacher-progress/')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

