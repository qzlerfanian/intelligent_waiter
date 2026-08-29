from celery import shared_task
from django.utils import timezone
from .models import Conversation

@shared_task
def purge_expired_conversations():
    deleted, _ = Conversation.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted
