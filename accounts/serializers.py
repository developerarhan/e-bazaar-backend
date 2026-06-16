from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(
        write_only=True,
    )

    class Meta:
        model = User
        fields = ["id", "name", "email", "phone", "password", "confirm_password"]

    def validate_password(self, value):
        """
        Run all AUTH_PASSWORD_VALIDATORS against the password.
        This is what actually enforces our validators.
        """
        try:
            validate_password(value)
        except DjangoValidationError as e:
            # Convert Django's ValidationError to DRF's ValidationError
            # so it appears in the response properly
            raise serializers.ValidationError(list(e.messages))
        
        return value

    def validate(self, data):
        """Check that passwords match."""
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({
                'confirm_password': "Passwords do not match."
            })
        return data
    
    def create(self, validated_data):
        validated_data.pop('confirm_password') 
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        user.set_password(password)
        user.save()
        return user
    

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password")
        
        data["user"] = user

        return data
    

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email", "phone"]
        read_only_fields = ["email"]