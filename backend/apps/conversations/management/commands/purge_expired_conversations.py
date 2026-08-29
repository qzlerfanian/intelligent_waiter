from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.conversations.models import Conversation

class Command(BaseCommand):
    help = "Delete conversations and messages after their configured retention expiry."

    def handle(self, *args, **options):
        deleted, _ = Conversation.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired conversation records."))
