# Offline ASR adapter

## Scope

Local PCM16 WAV transcription through faster-whisper 1.2.0 / CTranslate2,
CPU int8. No accounts, API calls, paid services or download execution. Model
assets are supplied by the operator, never committed. The adapter emits text,
segment-relative start/end seconds, detected language, input SHA256 and a model
profile hash. It does not identify speakers, assess accuracy, extract advice,
validate source identity, or grant source consent. Audio/text are untrusted data.

## Install and configuration

Install the optional dependency with `pip install '.[asr]'`. On a separately
network-enabled machine, manually obtain a complete converted Whisper small
model directory. Transfer it into an absolute local directory outside the repo.
Required nonempty regular files: model.bin, config.json, tokenizer.json and
preprocessor_config.json. Extra regular files contribute to the identity hash.
No symlinked files/directories/ancestors, no nested model directories. Supplying
a model name or Hub ID is not supported. Missing assets fail closed before model
loading. In particular, tokenizer.json is required so upstream cannot use its
missing-tokenizer remote fallback. Model construction explicitly sets
local_files_only=True and use_auth_token=False. Runtime has no download flag.

`ASRConfig(Path('/absolute/models/whisper-small'))` is the default small profile.
The operator must ensure that the directory really contains the selected model;
the size label is a declaration, not independently verified architecture. Model
identity hashes every local file plus size label and fixed decoding profile.
Assets are checked again before each inference. Each call re-hashes up to 32 files of up to 4GB each, a throughput cost accepted instead of an mtime cache; this
retains the identity check strength but does not eliminate TOCTOU.
Protect model directories from concurrent modification: check-to-load TOCTOU is not eliminated. Runtime assumes
trusted installed dependencies and a read-only model deployment. Use network
isolation as defense in depth. All credentials/account routes are absent.

Small is a size/quality compromise: less memory/work than medium/large, but lower
accuracy is possible, especially with noise, accents and domain terms. Tiny/base
are lighter; medium/large-v3 cost more local resources. No local speed, memory,
language accuracy or word-error-rate benchmark is claimed. Decoder uses beam1,
temperature0, no previous-text conditioning or VAD. These choices reduce variable
work and preserve speech timestamps; numerical determinism across platforms is
not promised. Whisper can hallucinate. Human review is required before relying
on text or timing. MIT-licensed implementation, no service fee; hardware and
operator setup still have costs. Verify model distribution/license yourself.

## Interfaces and ingestion wiring

- `OfflineWhisper(config).transcribe(bytes)` returns a Transcript. Loading is lazy;
  invalid audio is refused before loading. A lock serializes calls per instance.
- `TextTranscriber` implements M20's text protocol and a richer
  transcribe_with_provenance method. `SensoryLayer(asr_config=config)` and
  `CognitiveWorkerService(asr_config=config)` wire it explicitly. A custom
  transcriber and config together refuse; absent config preserves existing
  unbound behavior. Allowlist/dedupe occurs before inference. Event source and
  external_id remain caller-supplied; raw-byte SHA256 is content_hash. Event
  metadata.asr overrides caller metadata.asr with actual result provenance.
  observed_at remains ingestion time, not recording time.
- `AdviceTranscriber` implements M17's positional MIME text protocol for explicit
  host binding. It performs no collection or advice aggregation. M17's text-only
  protocol does not carry timing; use the backend Transcript for timestamped
  evidence rather than claiming that the text bridge itself preserves it.
- `KnowledgeTranscriber` implements M25's Segment protocol. Each segment has a
  timestamp anchor, start/end seconds and speaker='unknown', confidence=None.
  M25 associates source_id/version/input hash and consent through its existing
  ingestion/persistence code; adapter never invents source ownership.
- `provision(..., asr_config=config)` and
  `KnowledgeServiceFactory(..., asr_config=config)` select a new explicit
  deterministic-embedder-v1+offline-whisper-v1:<model-hash> profile. Old unavailable
  registries keep their old profile, not auto-upgraded. Different model/profile
  refuses instead of silently restoring with another transcriber. Existing
  ownership/root/consent/recovery checks remain. CLI/HTTP configuration and old
  registry migration are not supplied; integrator must explicitly construct the
  factory. Existing M25 20,000-byte ingress bound is unchanged.

## Boundaries and refusals

Only WAV containers with uncompressed 16-bit PCM, one/two channels, rate8k..48k
are supported. No path/URL, remote decoder, compressed/MP3/OGG support. Exact
bytes type, nonempty, <=20MB, <=600 seconds, complete declared frames. Limits
are design choices, not a general hostile-media sandbox. Decoder native code
and model inference can still consume resources; no process timeout or hard
memory sandbox. Large-model startup/hash work is costly; hash reads are streamed.
Model tree <=32 regular files, each nonempty <=4GB. Segment result <=1000 rows,
nonblank clean text <=20k per row, total text <=100k characters, finite numeric
non-bool times with 0 <= start < end <= declared duration and no overlap.
Time bounds are strict: rounding past duration is refused, not clamped. No speech
is a refusal, not fabricated text. Partial result never returned. ASRError carries
bounded generic messages, not audio/path/model exception details. Core policy
text refusal is converted to generic inference unavailable at the ASR boundary.

## Verification limits

CI uses a fake model boundary; no weights/audio accuracy claim. Tests exercise
local-only loader flags, model identity, invalid media before inference, result
validation, protocol bridges, source-time provenance, factory restart/profile
mismatch, and legacy integration behavior with repository conftests. Real-model
inference and rendered output are not tested by this contract. No deployment or
permission for external effects is implied.

## Upstream interface references

- https://github.com/SYSTRAN/faster-whisper
- https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.0/faster_whisper/transcribe.py
- https://github.com/openai/whisper
