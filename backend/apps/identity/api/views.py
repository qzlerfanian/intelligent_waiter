from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from .serializers import MeSerializer, RegistrationSerializer

class RegistrationView(CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]

class MeView(RetrieveAPIView):
    serializer_class = MeSerializer
    def get_object(self):
        return self.request.user
