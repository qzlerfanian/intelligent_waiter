import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import NotificationOutbox

logger = logging.getLogger(__name__)

def deliver_event(event):
    logger.info("outbox_event_delivered", extra={"topic": event.topic, "event_id": str(event.id)})

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=7)
def dispatch_outbox(self, batch_size=100):
    processed = 0
    while processed < batch_size:
        failure = None
        with transaction.atomic():
            event = NotificationOutbox.objects.select_for_update(skip_locked=True).filter(status=NotificationOutbox.Status.PENDING, available_at__lte=timezone.now()).order_by("created_at").first()
            if event is None: break
            try:
                deliver_event(event)
                event.status = NotificationOutbox.Status.PROCESSED; event.processed_at = timezone.now(); event.attempts += 1
                event.save(update_fields=["status", "processed_at", "attempts"])
            except Exception as exc:
                event.attempts += 1
                if event.attempts >= 7: event.status = NotificationOutbox.Status.FAILED
                event.save(update_fields=["status", "attempts"])
                failure = exc
        if failure is not None:
            raise failure
        processed += 1
    return processed
