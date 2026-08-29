from django.urls import path
from .views import ConfirmCheckoutView, ConversationView, MessageView

urlpatterns = [path("", ConversationView.as_view(), name="conversation"), path("messages/", MessageView.as_view(), name="conversation-message"), path("confirmations/<uuid:confirmation_id>/confirm/", ConfirmCheckoutView.as_view(), name="conversation-confirm-order")]
