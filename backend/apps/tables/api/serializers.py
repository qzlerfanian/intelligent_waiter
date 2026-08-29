from rest_framework import serializers
from apps.tables.models import RestaurantTable
from apps.tables.services import issue_qr_token

class RestaurantTableSerializer(serializers.ModelSerializer):
    capacity = serializers.IntegerField(min_value=1, required=False)
    qr_token = serializers.CharField(read_only=True)
    class Meta:
        model = RestaurantTable
        fields = ["id", "branch", "number", "capacity", "status", "is_active", "qr_token", "qr_rotated_at", "created_at"]
        read_only_fields = ["id", "qr_token", "qr_rotated_at", "created_at"]

    def validate_branch(self, branch):
        if branch.organization_id != self.context["request"].organization.id:
            raise serializers.ValidationError("Branch does not belong to the selected organization.")
        return branch

    def validate_capacity(self, capacity):
        if capacity < 1:
            raise serializers.ValidationError("Capacity must be at least one.")
        return capacity

    def create(self, validated_data):
        token, token_hash = issue_qr_token()
        table = RestaurantTable.objects.create(organization=self.context["request"].organization, qr_token_hash=token_hash, **validated_data)
        table.qr_token = token
        return table

class QRResolutionSerializer(serializers.ModelSerializer):
    branch = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    class Meta:
        model = RestaurantTable
        fields = ["id", "number", "capacity", "status", "organization", "branch"]
    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name, "slug": obj.organization.slug}
    def get_branch(self, obj):
        return {"id": obj.branch_id, "name": obj.branch.name, "code": obj.branch.code}
