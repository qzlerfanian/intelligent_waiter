# ADR 0003: AI is an untrusted orchestration adapter

Status: accepted

The model never reads the database directly and never invents operational facts. It invokes allow-listed, tenant-scoped application tools for menu search, availability, deterministic price calculation, and cart mutation. Inputs are validated and authorization is repeated server-side. Order confirmation is an idempotent command requiring explicit customer consent.

Prompts and conversations follow configurable retention policies. Sensitive payment data is never sent to the model. Provider-specific code remains behind a port so the platform is not coupled to one model vendor.
