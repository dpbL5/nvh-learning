from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
import uuid
from .models import User, Role, StudentProfile, TeacherProfile

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']

class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'role', 'avatar_url', 'created_at']

class RegisterSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'first_name', 'last_name', 'role_name']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_role_name(self, value):
        role_name = (value or Role.STUDENT).strip().lower()
        if role_name not in (Role.STUDENT, Role.TEACHER):
            raise serializers.ValidationError('Chỉ có thể đăng ký với vai trò học sinh hoặc giáo viên.')
        return role_name

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email này đã được sử dụng.')
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Tên đăng nhập này đã được sử dụng.')
        return value

    def create(self, validated_data):
        role_name = validated_data.pop('role_name', Role.STUDENT)
        with transaction.atomic():
            user = User.objects.create_user(
                email=validated_data['email'],
                username=validated_data['username'],
                password=validated_data['password'],
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
            )
            target_role, _ = Role.objects.get_or_create(name=role_name)
            user.role = target_role
            user.save(update_fields=['role'])

            code_suffix = uuid.uuid4().hex[:8].upper()
            if role_name == Role.TEACHER:
                TeacherProfile.objects.create(user=user, teacher_code=f'GV-{code_suffix}')
            else:
                StudentProfile.objects.create(user=user, student_code=f'HS-{code_suffix}')

        return user
