# Storage

How PulseIQ stores uploaded datasets, and exactly what's needed to move
from local disk to Cloudflare R2 later.

## Current Mode

**Production (Render): Cloudflare R2** (bucket `pulse-iq`, set in
`render.yaml`), verified against the real bucket on 2026-10-15; see "R2:
verified" below. **Local development: local filesystem** by default. No
Cloudflare account, R2 bucket, or credentials are required to run
PulseIQ today. Every dataset upload, profiling run, query, AI analysis,
and dashboard chart works fully against files stored on the backend's own
disk; uploaded CSV/XLSX datasets are stored through `LocalStorageProvider`
and processed by the exact same analytics pipeline that would run against
R2 — the provider is invisible above the storage layer.

## Configuration

```bash
STORAGE_PROVIDER=local
LOCAL_STORAGE_ROOT=./data/uploads
MAX_UPLOAD_SIZE_MB=200
ALLOWED_UPLOAD_EXTENSIONS=[".csv", ".xlsx", ".xls"]

# Reserved for a future scheduled cleanup job — not implemented yet (see
# "Not yet built" below). Safe to leave as the defaults shown.
ENABLE_STORAGE_CLEANUP=false
DATASET_RETENTION_DAYS=7
```

All of the above live in `.env` (see `.env.example`) and are read through
`app/core/config.py` — nothing storage-related is hardcoded elsewhere in
the codebase. The app **starts and runs with zero Cloudflare credentials**
as long as `STORAGE_PROVIDER=local` (the default).

## Architecture

```
                    StorageProvider (app/storage/base.py)
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
     LocalStorageProvider      R2StorageProvider
     (app/storage/local.py)    (app/storage/r2.py)
              │                       │
              ▼                       ▼
       Local filesystem         Cloudflare R2
```

Every other layer of the app — the dataset service, the Polars-based
analytics engine, the AI analyst, dashboards — depends only on the
`StorageProvider` interface, never on a concrete provider or a raw
filesystem path. `app/storage/__init__.py`'s `get_storage_provider()` is
the single place `STORAGE_PROVIDER` gets read; it's injected as a FastAPI
dependency (`get_storage` in `app/api/deps.py`) into every route that
needs one. Swapping providers is a config change, not a code change.

**The interface** (`StorageProvider`, abstract):

| Method | Purpose |
|---|---|
| `save(key, data)` | Persist bytes under an opaque key. Atomic — a provider never leaves a partially-written object visible at that key. |
| `open(key)` | A readable binary stream for a previously-saved key. |
| `exists(key)` | Whether an object is currently stored under key. |
| `delete(key)` | Remove the object at key. No-op if missing. |
| `local_path(key)` | A context manager yielding a *real filesystem path* to the object, for tools that need one rather than a stream. Local: the real path, no copy. R2: downloads to a temp file for the `with` block, then removes it. Not used by anything today (the analytics layer reads via `open()` into memory) — it exists so a future tool that specifically needs a path (e.g. a library that only accepts `read_csv(path)`) doesn't force a rewrite of the interface. |

**Storage keys** are opaque and never derived from client input: a key is
`{owner_id}/{a fresh uuid4}{extension}` — the original filename is kept
only as metadata (`Dataset.original_filename` in Postgres), never used to
build a path. `LocalStorageProvider` additionally resolves every path and
verifies it stays under the configured root before touching disk, so a
key can never escape `LOCAL_STORAGE_ROOT` via `../` or similar.

**Dataset lifecycle**: upload → `save()` (file first) → create the DB row
referencing that key (if this fails, the file is deleted again — no
orphan is left behind) → profile (reads via `open()`, never mutates the
stored file) → query/AI/charts all re-read the same file on demand,
nothing is cached to a second location. Delete removes the DB row first,
then the storage object — see BUG-007/BUG-006 in `BUGS.md` for exactly
why that order, and what happens if either half fails.

## Local Storage Limitations

**Persistence depends entirely on the hosting platform — this is not
disk-backed durability you can rely on everywhere:**

- Running natively or via `docker-compose` on a machine with a real,
  persistent disk (or the `pulseiq_uploads` Docker volume): files survive
  restarts.
- Deployed to a platform with **ephemeral** container storage (many
  serverless/PaaS platforms wipe the filesystem on every redeploy, and
  some on every restart): uploaded datasets **will be lost** whenever that
  happens. The database rows would still reference files that no longer
  exist — the app doesn't currently detect or warn about this mismatch at
  runtime (see "Not yet built" below).
- The frontend shows a small note on the Datasets page — *"Datasets are
  stored on the server's local disk in this environment — they may not
  persist across a restart or redeploy"* — driven by the actual
  `storage_provider` value the backend reports (via `GET /api/v1/health`),
  not a hardcoded assumption. It only appears when `STORAGE_PROVIDER=local`
  and disappears automatically once R2 is enabled.

**Not yet built** (called out here rather than silently absent):

- No scheduled cleanup job. `ENABLE_STORAGE_CLEANUP`/`DATASET_RETENTION_DAYS`
  are defined and read into `Settings`, but nothing acts on them yet — that
  needs the background-worker infrastructure deferred in `PHASES.md` Phase
  6. Until then, uploaded files simply persist for as long as the disk
  does; nothing deletes them automatically.
- No startup check that flags "the DB has N datasets but their files are
  missing" (which ephemeral storage can cause). Would be a reasonable
  addition alongside a real cleanup job.

## R2: verified (2026-10-15)

`R2StorageProvider` (`app/storage/r2.py`) implements the same interface
over the S3 API (`boto3`). Against the real `pulse-iq` bucket:

- **Provider round trip:** `save` → `exists` → `open` → `local_path` →
  `delete`, all with matching bytes, and the object gone afterwards.
- **Through the app:** the production image ran with `STORAGE_PROVIDER=r2`
  (512 MiB limit). The demo seeder uploaded and profiled its dataset to
  R2, a CSV uploaded through `POST /datasets` showed up in the bucket under
  `<user_id>/<uuid>.csv`, and NL-to-SQL ran against it.
- **Survives a redeploy:** the container was destroyed and recreated
  (fresh filesystem, same database). The same dataset still queried
  correctly, and the seeder found the demo data healthy and didn't
  re-upload it. This is exactly what failed on local disk.
- **Delete:** `DELETE /datasets/{id}` removed the object from the bucket.
- Test objects were removed afterwards; the bucket was left empty.

**Gotcha found while setting it up:** `R2_ENDPOINT_URL` set to the
bucket's *public* URL (`https://pub-….r2.dev`) gets a bare `401
Unauthorized` on every API call, which looks like a credentials problem.
The S3 API endpoint is `https://<account_id>.r2.cloudflarestorage.com`
(or leave it unset; it's derived from `R2_ACCOUNT_ID`).
`get_storage_provider()` now rejects an `r2.dev` endpoint with a message
saying so (`tests/test_storage_selection.py`). Also: R2 returns the same
`AccessDenied` for a wrong secret as for a missing permission, so
`AccessDenied` doesn't prove the key pair is valid.

**To turn it on elsewhere (e.g. local dev):**

1. Create an R2 bucket and an **Account API token** (Cloudflare dashboard →
   R2 → Manage API tokens) with **Object Read & Write** on that bucket.
   Copy the Access Key ID and Secret Access Key from the creation page;
   the secret isn't shown again.
2. Set in `.env`:
   ```bash
   STORAGE_PROVIDER=r2
   R2_ACCOUNT_ID=<your account id>
   R2_ACCESS_KEY_ID=<from the API token>
   R2_SECRET_ACCESS_KEY=<from the API token>
   R2_BUCKET_NAME=<your bucket name>
   R2_ENDPOINT_URL=            # leave blank; defaults to https://<account_id>.r2.cloudflarestorage.com
   ```
3. Restart the backend. Nothing else changes — no code, no migration, no
   different upload/query/AI/dashboard behavior. Existing datasets already
   on local disk are **not** automatically migrated to R2; only new
   uploads after the switch go to R2. (A one-off script to copy existing
   `LOCAL_STORAGE_ROOT` files to R2 and update `storage_key`s would be
   straightforward to add if a real migration is ever needed, but wasn't
   built speculatively.)

**If `STORAGE_PROVIDER=r2` but any of the four `R2_*` values above are
missing**, the app fails immediately and loudly with a clear error naming
exactly which variables are missing — it does **not** silently fall back
to local storage, and does not expose any credential values in the error.
Verified live (see `BUGS.md`'s QA section): a misconfigured-R2 upload
attempt returns a clean `500` to the client, logs the real cause
server-side, and the rest of the server keeps working normally — it
doesn't crash the process.
