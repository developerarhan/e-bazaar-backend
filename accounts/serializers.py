from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "name", "email", "phone", "password"]
    
    def create(self, validated_data):
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
    

class ProfileSerializer(serializers.Serializer):
    class Meta:
        model = User
        fields = ["id", "name", "email", "phone"]
        read_only_fields = ["email"]