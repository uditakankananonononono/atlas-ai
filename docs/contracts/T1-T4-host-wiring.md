# T1-T4 host integration

The main app mounts the existing tenant-authenticated T1-T4 router with the shared
mount_training_routes helper. No tenant is provisioned automatically. Unconfigured
tenants receive 503. No network transport is installed.

Server deployment code can call configure_training_units(tenant_id, permits) with
explicit source permits. Candidate source registries are not grants. This binds a
per-tenant TrainingUnits engine to canonical c30.policy.classify using a validated
offline descriptor, module 20 and the configured tenant. Only canonical offline
actions can pass. Risk flags, unknown fields/actions and approval-shaped client
inputs refuse. No spend/outreach approval is created or consumed.

The original unconfigured TrainingUnits policy path remains deny-only. The hook
is not an HTTP parameter, and clients cannot provide source permits or replace it.
Reports remain process-local and tenant-keyed, not durable. Tests exercise the
same mount helper with production RS256 tenant verification and supplied fixtures;
full application boot and deployment provisioning are not verified by those tests.
