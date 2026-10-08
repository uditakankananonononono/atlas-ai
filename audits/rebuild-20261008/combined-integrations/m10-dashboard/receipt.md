# M10/dashboard integration

Source replays: reviewed M10 7f4449cc and dashboard e90f3fa4. Distinct integration ordering commit 7d8456f211dc69195d2ea55dc1647d254011d961 puts view_version after m10_account_scope.

111 affected Python tests passed against new isolated SQLite. Prior scratch atlas.db lacked the new version column; four global-engine tests failed there, retained in stale-scratch-failure.log. create_all is not a schema upgrade. No product correction was made for stale scratch state.

Two actual SQLite upgrade head -> downgrade 20261008_m16_identity_forward -> upgrade head cycles succeeded. Final version 20261008_m16_view_version; view version column, draft account_id and tenant/account/gmail uniqueness restored. PostgreSQL and production migration not tested. Frontend tests remain pending.
