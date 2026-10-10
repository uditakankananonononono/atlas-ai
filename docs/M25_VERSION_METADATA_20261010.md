# Original version metadata through restart

Base02a75fbd4eac6735437be4ba00fb575b295baa6f. New ingests persist explicit
metadata_version1, canonical UTC created_at and exact supported mime_type in
the SAME manifest row as sequential version number/content hash. Existing atomic
manifest write/rollback ordering retained. New-format recovery uses recorded MIME,
not guessing, validates schema/timezone/canonical representation and rederives
segments exactly before all-or-nothing state load. Original timestamp propagated
to chunks; contradiction freshness uses it. No extra file or partial metadata
write window. Manifest cap unchanged, so more metadata lowers version capacity.

Legacy two-key number/hash rows remain readable, timestamp restamped but marked
metadata_known=False. Later manifest writes never promote that unknown timestamp
to historical truth. RecoveryReport.created_at_restamped reflects any such rows;
contradiction fresher=unknown if either version historical time unknown. New
format survives restore/append, preserved MIME plain/markdown distinction.

No authenticity, trusted-clock or hostile manifest edit guarantee. An operator
can edit timestamp/MIME/hash consistently; record association is not cryptographic
authority. No adapter identity/consent authority change, default routes unchanged,
no HTTP/training or downloads. Existing TOCTOU/private primitive dependency remains.
Malformed metadata refuses, never silently falls back to legacy. New format is
not readable by old code; deploy compatible code before writing, old-binary
rollback requires separate migration/export decision, not silent data downgrade.
