# ADR 0001: Modular monolith first

Status: accepted

Use one Django deployment and PostgreSQL database with explicit domain modules. Cross-domain writes go through application services, not model imports from views. This preserves simple transactions and operations during product discovery. Split a module only when scaling, ownership, or release-cadence evidence requires it.
