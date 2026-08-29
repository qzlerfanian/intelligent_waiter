from rest_framework import serializers
from apps.conversations.models import Conversation, Message

class MessageSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    class Meta:
        model = Message
        fields = ["id", "role", "content", "actions", "created_at"]
    def get_actions(self, obj):
        return obj.metadata.get("actions", []) if obj.role == Message.Role.ASSISTANT else []

class ConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()
    class Meta:
        model = Conversation
        fields = ["id", "status", "provider", "model", "messages", "created_at", "updated_at"]
    def get_messages(self, obj):
        return MessageSerializer(obj.messages.exclude(role=Message.Role.TOOL), many=True).data

class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(min_length=1, max_length=1000, trim_whitespace=True)
