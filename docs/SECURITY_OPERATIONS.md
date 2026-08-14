# Security operations for local deployments

SOFI.IA PREVI is a single-office, local-first deployment. It is not a
multi-tenant SaaS and must not be exposed directly to the public internet.

## Operator baseline

- Use a separate, password-protected Windows account for each operator.
- Enable full-disk encryption and keep the operating system and OCR libraries
  updated.
- Back up the data directory using encrypted storage. Test restoration on a
  separate machine before relying on a backup.
- Never place the data directory in a public sync folder or shared network
  drive without access controls and encryption.
- Treat OCR output as sensitive legal and personal data. Automatic extraction
  never replaces review of the original document.

## Application controls

- Credential and settings files are written atomically with restrictive file
  modes where the operating system supports them.
- SQLite uses WAL mode, foreign keys, and a busy timeout to reduce local
  contention. Schema migrations are recorded in `schema_migrations`.
- Uploads use an allowlist, signature checks, size limits, sanitized names and
  content-derived names. OCR additionally limits pages and image pixels.

## Known boundaries

Encryption at rest, backup automation, user management, RBAC and tenant
isolation require a hosted identity/key-management design and are deliberately
not claimed by this local application.
