from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from apps.branches.models import Branch, BranchAssignment
from apps.organizations.models import Membership, Organization, Role
from apps.organizations.services import create_organization

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]
    def create(self, validated_data):
        return create_organization(owner=self.context["request"].user, **validated_data)

class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    display_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, min_length=10)
    branches = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), many=True, required=False)
    class Meta:
        model = Membership
        fields = ["id", "user", "email", "display_name", "password", "branches", "role", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"user": {"required": False}}
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["email"] = instance.user.email
        data["display_name"] = instance.user.display_name
        data["branches"] = list(instance.user.branch_assignments.filter(branch__organization=instance.organization).values_list("branch_id", flat=True))
        return data
    def validate_role(self, value):
        request = self.context["request"]
        actor = request.user.memberships.filter(organization=request.organization, is_active=True).first()
        if value == Role.OWNER and (actor is None or actor.role != Role.OWNER):
            raise serializers.ValidationError("Only an owner can grant the owner role.")
        return value
    def validate(self, attrs):
        organization = self.context["request"].organization
        if any(branch.organization_id != organization.id for branch in attrs.get("branches", [])):
            raise serializers.ValidationError({"branches": "Every branch must belong to this organization."})
        actor = self.context["request"].user.memberships.get(organization=organization, is_active=True)
        if self.instance:
            if self.instance.role == Role.OWNER and actor.role != Role.OWNER:
                raise serializers.ValidationError("Only an owner can modify another owner.")
            if any(key in attrs for key in ("user", "email", "password", "display_name")):
                raise serializers.ValidationError("Account identity cannot be changed through a membership.")
            is_self = self.instance.user_id == self.context["request"].user.id
            if is_self and ("role" in attrs or attrs.get("is_active") is False):
                raise serializers.ValidationError("You cannot demote or deactivate yourself.")
            removes_owner = self.instance.role == Role.OWNER and (attrs.get("role", Role.OWNER) != Role.OWNER or attrs.get("is_active") is False)
            other_owner_exists = Membership.objects.filter(organization=self.instance.organization, role=Role.OWNER, is_active=True).exclude(pk=self.instance.pk).exists()
            if removes_owner and not other_owner_exists:
                raise serializers.ValidationError("An organization must retain at least one active owner.")
        else:
            user = attrs.get("user")
            if user:
                if any(key in attrs for key in ("email", "password", "display_name")):
                    raise serializers.ValidationError("Choose an existing user OR create a new account.")
                if Membership.objects.filter(organization=organization, user=user).exists():
                    raise serializers.ValidationError({"user": "This account is already a member."})
            else:
                if not attrs.get("email") or not attrs.get("password"):
                    raise serializers.ValidationError("Email and password are required for a new employee.")
                if get_user_model().objects.filter(email__iexact=attrs["email"]).exists():
                    raise serializers.ValidationError({"email": "Account already exists. Use its user ID to add membership; its credentials will not be changed."})
                try:
                    validate_password(attrs["password"], get_user_model()(email=attrs["email"], display_name=attrs.get("display_name", "")))
                except DjangoValidationError as exc:
                    raise serializers.ValidationError({"password": exc.messages})
        return attrs
    def save_branches(self, instance, branches):
        BranchAssignment.objects.filter(user=instance.user, branch__organization=instance.organization).delete()
        BranchAssignment.objects.bulk_create([BranchAssignment(user=instance.user, branch=branch) for branch in set(branches)])
    @transaction.atomic
    def create(self, validated_data):
        branches = validated_data.pop("branches", [])
        if "user" not in validated_data:
            validated_data["user"] = get_user_model().objects.create_user(email=validated_data.pop("email"), password=validated_data.pop("password"), display_name=validated_data.pop("display_name", ""))
        instance = super().create(validated_data)
        self.save_branches(instance, branches)
        return instance
    @transaction.atomic
    def update(self, instance, validated_data):
        branches = validated_data.pop("branches", None)
        instance = super().update(instance, validated_data)
        if branches is not None:
            self.save_branches(instance, branches)
        return instance

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code", "address", "timezone", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
