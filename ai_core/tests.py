from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from ai_core.models import Document
from classes.models import Class, ClassStudent, Subject


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

	def test_generate_from_rag_forbidden_for_student(self):
		self._auth('student_ai', 'StudentPass123')
		payload = {'class_id': str(self.classroom.id), 'topic': 'Chu de A'}
		res = self.client.post('/api/ai/generate/from-rag/', payload, format='json')
		self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
