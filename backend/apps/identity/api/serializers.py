from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10)
    class Meta:
        model = User
        fields = ["id", "email", "display_name", "password"]
        read_only_fields = ["id"]
    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class MeSerializer(serializers.ModelSerializer):
    organizations = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ["id", "email", "display_name", "organizations"]
    def get_organizations(self, obj):
        return [{"id": membership.organization_id, "name": membership.organization.name, "role": membership.role} for membership in obj.memberships.filter(is_active=True).select_related("organization")]
