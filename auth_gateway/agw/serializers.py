from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_registration.utils.users import build_initial_user
from django.contrib.auth.password_validation import validate_password


class CustomUserSerializer(serializers.ModelSerializer):
	class Meta:
		model = get_user_model()
		fields = (
		    'username',
		    'email',
		    'password',
		)

	def validate_password(self, password):
		user = build_initial_user(self.initial_data)
		validate_password(password, user=user)
		return password

	def create(self, validated_data):
		if not self.is_valid():
			print(self.errors)
		return self.Meta.model.objects.create_user(**validated_data)
