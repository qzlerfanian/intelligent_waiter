from apps.organizations.models import Role

def accessible_branch_ids(user, organization):
    membership = user.memberships.filter(organization=organization, is_active=True).first()
    if membership is None:
        return []
    if membership.role in (Role.OWNER, Role.ADMIN):
        return None
    return list(user.branch_assignments.filter(branch__organization=organization).values_list("branch_id", flat=True))
