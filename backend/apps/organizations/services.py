from django.db import transaction
from .models import Membership, Organization, Role

@transaction.atomic
def create_organization(*, owner, name, slug):
    organization = Organization.objects.create(name=name, slug=slug)
    Membership.objects.create(organization=organization, user=owner, role=Role.OWNER)
    return organization
