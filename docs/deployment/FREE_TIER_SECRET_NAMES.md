# Free-tier deployment: required secret names (contract, names only)

`docker-compose.prod.yml` (`x-atlas-env`) requires these names with `:?` checks. A deployment descriptor for the same API image must declare each one so the owner is prompted to supply it. No values belong in this repository.

| Name | Declared as | Notes |
|---|---|---|
| `ATLAS_DATABASE_URL` | `sync: false` in `render.yaml` | Already declared. |
| `ATLAS_REDIS_URL` | `sync: false` in `render.yaml` | Already declared. |
| `ATLAS_TOKEN_KEY` | `sync: false` in `render.yaml`; empty `NAME=` in `.env.free-tier.example` | Read in `backend/app/core/token_crypto.py` line 28. Any non-empty string is accepted (lines 29-32 reject only an empty value); the code derives its own key as SHA-256 of `master::tenant` (lines 19-21). Use 32+ random bytes as a recommendation; `docs/REQUIRED_ENV.md` line 11 is advice, not enforced. Unset raises `TokenCryptoError` at use time (M10/M11), not at startup. |
| `ATLAS_API_KEY_ENCRYPTION_KEY` | `sync: false` in `render.yaml`; empty `NAME=` in `.env.free-tier.example` | A different contract: passed directly to `Fernet(key.encode())` (`backend/app/platform/encryption.py` lines 4-6), so it must be a real Fernet key. In the `cryptography` source (`src/cryptography/fernet.py`, main branch as fetched 2026-10-10, not a pinned release) `Fernet.__init__` base64-urlsafe-decodes the key and requires exactly 32 bytes, else "Fernet key must be 32 url-safe base64-encoded bytes"; `generate_key()` returns `base64.urlsafe_b64encode(os.urandom(32))`. No application reader of this variable has been proven absent repo-wide; the source audit is still open. |

With the companion deployment-descriptor change applied, `render.yaml` and `.env.free-tier.example` declare both `ATLAS_TOKEN_KEY` and `ATLAS_API_KEY_ENCRYPTION_KEY` by name only, and `tests/platform/test_free_tier_secret_names_contract.py` checks that. Names are declared so the owner is prompted; values are never stored in the repository.
