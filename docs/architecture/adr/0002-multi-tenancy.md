# ADR 0002: Shared-schema multi-tenancy

Status: accepted

Use a shared database and schema. Every tenant-owned root and descendant carries a non-null organization foreign key, even when derivable through a branch. The duplication enables simple indexes, explicit constraints, and auditable scoping.

Tenant context is resolved at the boundary and passed explicitly. Tenant model access must reject unscoped queries; background jobs carry an organization ID; cache keys and object-storage paths are tenant-prefixed. Constraints enforce that related objects share an organization. PostgreSQL row-level security remains a defense-in-depth option after application isolation tests exist.

QR codes contain a high-entropy, revocable lookup token. They expose no organization, branch, or table IDs and do not themselves authorize an order. Resolution creates an expiring table session after availability checks.
