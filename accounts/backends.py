from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOrUsernameBackend(ModelBackend):
    """Allow login with either email or username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        login_value = username or kwargs.get(UserModel.USERNAME_FIELD)
        if not login_value or not password:
            return None
        try:
            if '@' in login_value:
                user = UserModel.objects.filter(email__iexact=login_value).order_by('id').first()
            else:
                user = UserModel.objects.filter(username__iexact=login_value).order_by('id').first()
        except UserModel.DoesNotExist:
            return None
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
