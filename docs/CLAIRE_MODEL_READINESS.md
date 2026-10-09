# Local model protocol readiness

Run with PYTHONPATH=backend python scripts/claire_model_readiness.py and explicit
ATLAS_CLAIRE_MODEL_PROVIDER / MODEL_URL / MODEL_NAME. Supported selected local
providers: hermes, ornith, inkling. The URL must pass the existing loopback validation.
No DB, queue, tools, private context, hosted fallback or inference retry is used.

It sends one fixed synthetic readiness prompt with a random probe ID, expects final
JSON, and emits unavailable, invalid_output or protocol_answered. Invalid/missing
configuration emits configuration_invalid. Exit0 means protocol answered, NOT learned
model proven. Response is the actual parsed final text, scrubbed/capped at1000 chars;
SHA256 covers full parsed decision JSON before scrubbing, not raw network bytes.

learned_model_verified and acceptance_a_met always remain false: a synthetic/echo
server can pass this probe. Learned provenance needs a separately inspected selected
model deployment/weights plus actual behavior evidence. No learned endpoint was
available during implementation. The script is a canary entrypoint, not certification.
Waiting is bounded5 seconds plus cancellation grace; a synchronous provider thread
may outlive cancellation, including asyncio.run's threadpool shutdown wait. It is not
an OS-isolated hard deadline or production health service.
