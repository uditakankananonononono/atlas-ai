# Release rollback

Abort on elevated 5xx, auth-boundary failures, migration mismatch or data corruption. Stop traffic migration, route Cloud Run traffic to the last known-good immutable revision, and restore prior Secret Manager versions. Forward-only database repair is preferred; destructive down-migrations require owner review and a fresh backup. Validate `/health` and `/ready`, tenant-isolation tests, queue lag and four golden signals. Record revision IDs and observations. A manifest is not deployment evidence.
