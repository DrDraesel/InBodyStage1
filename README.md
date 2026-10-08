# InBodyStage1

A standalone, local-first **synthetic proof of concept** for Coherence / IMW. Import a completed body-composition test, bind it to a patient encounter, preserve its timestamp and source, apply deterministic rules, compare prior studies, and produce separate clinician and patient summaries. Review and corrections are recorded without overwriting history.

The interface uses a blue clinical dashboard palette. For local acquisition without a cloud API, see [InBody 380 connection and automatic export setup](docs/local-device-connection.md). The local export bridge preserves files in an unassigned review queue; hardware pairing must be completed in LookinBody 120 on the clinic computer.

**This is executable Stage 1 software, not a production clinical deployment.** Real patient use is not enabled. The live InBody connector, paid AI account validation, institutional identity integration and clinical rule approval remain outstanding.

## Quick start (local SQLite)

Prerequisites: Python 3.12+, Tesseract OCR 5+, Git, and the packages in `requirements.txt`. SQLite is bundled with Python. PDF text extraction uses PyMuPDF; OCR uses the local Tesseract executable. No frontend dependency installation is required.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m backend.server --seed
```

Open **http://127.0.0.1:8080**. The seeded records are labeled synthetic. One patient has three repeat studies; the second starts empty. Tesseract must be available on PATH; on Ubuntu install `tesseract-ocr` and `fonts-dejavu-core`. The tests use DejaVu Sans at its usual Ubuntu path.

The default development server accepts loopback connections without a token. It rejects other hostnames and cross-origin browser requests. Do not expose the development server on the internet. If using `.env`, copy `.env.example` and load it into your process environment; it is not implicitly loaded by Python. The Windows launcher `scripts/start.ps1` loads `.env` and starts the seeded server.

## PostgreSQL target

The DB-API repository supports SQLite and PostgreSQL with the same schema. Set:

```text
INBODY_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/inbody
```

The application applies the initial migration on startup. It creates append-only triggers on source results, analyses, reviews, audit events and the encounter outbox. Runtime schema migrations are a Stage 1 bootstrap convenience; later production migrations need their own deployment role and version controls.

For Docker Compose, add a strong `POSTGRES_PASSWORD`, `INBODY_CLINICIAN_TOKEN` and different `INBODY_OPERATOR_TOKEN` to `.env`. URL-encode special password characters in the database URL; using a long random hexadecimal password avoids URL parsing ambiguity. Run:

```bash
docker compose up --build
```

The application port is published only on host loopback. PostgreSQL has no public port. The reference Compose configuration has not been executed in this build environment; SQLite restart/recovery has been verified. PostgreSQL transaction/trigger behavior must be verified on the target workstation before relying on it.

## Interface

- Patient lookup and explicit encounter selection.
- Study overview, measurement table and reference findings with neutral visual styling.
- Verified longitudinal trends and a display comparison selector.
- Separate clinician and common-language patient summaries.
- Immutable study history including superseded versions.
- Source SHA-256 provenance, original file download, and structured-result export.
- Confirm/correct values in a new linked version, then clinician review.

The first import writes local history and queues an `inbody.analysis.complete` outbox event. This event includes `review_required=true`; completion is **not** clinical acceptance. No downstream GHL, Cortex, Drive or patient messaging is triggered.

## Ingestion methods

### Manual / normalized API fixture

Import uses the documented normalized contract (`schemas/normalized-v1.json`). Example:

```json
{
  "patient_id": "SYN-001",
  "encounter_id": "SYN-001-FOLLOW",
  "test_timestamp": "2026-10-07T09:30:00-04:00",
  "source_identifier": "synthetic-test-004",
  "device_model": "Synthetic fixture",
  "source_type": "mock_api",
  "measurements": [
    {"metric": "weight", "value": 81.6, "unit": "kg"},
    {"metric": "bmi", "value": 26.6, "unit": "kg/m2"}
  ]
}
```

Missing metrics are omitted. An unreadable reported measurement has `value:null`, `status:unverified`. Unknown model-specific metrics are supported with explicit metric keys and units (for example segmental lean/fat, impedance at a frequency, or target composition). Standard mass fields normalize lb/lbs to kg while preserving the original value and unit. Unsupported units are rejected rather than guessed.

### PDF / screenshot

Use the import dialog or multipart POST with a JSON-string `metadata` part and 1–5 `files` parts. Accepts PDF, PNG and JPEG, up to 10 MiB per file, 10 PDF pages and 20 million image pixels. File signatures are validated. Original bytes are content-addressed locally; filenames are never trusted as paths.

The conservative parser recognizes lines such as `Weight: 80 kg`, `BMI: 27 kg/m2` or `ECW/TBW: 0.385 ratio`. It does not claim universal support for proprietary report layouts. Scanned PDFs use OCR. Unreadable, missing-unit or conflicting values are unverified; all extracted fields require clinician confirmation regardless of OCR appearance. Test timestamp and encounter are entered explicitly and must be checked against the original source during review. Explicit source `Patient ID` mismatches are rejected. The parser does not infer identity from a person's name.

If a vendor report has labels and values in different columns or uses a layout that cannot be extracted safely, use manual entry and retain the original. Accuracy against the clinic's actual InBody models/reports has not been validated.

### Official InBody integration

`adapters/inbody/official.py` defines the adapter contract, an internal mock adapter and a deliberately disabled live adapter. The mock normalized data is **not** a claimed vendor response format.

Official guide: https://usa.developers.lookinbody.com/guide . Configure an approved LookinBody Web account, API key, IP whitelist, and obtain the official response and webhook documentation for the clinic's account and device. `INBODY_ACCOUNT` and `INBODY_API_KEY` are reserved environment variables; they are not used by the disabled adapter. Implement and verify the documented mapping before enabling live ingestion. No vendor endpoints are scraped or reverse-engineered.

### Internal webhook

`POST /inbody/webhook` supports the **synthetic-normalized-v1** internal fixture contract only. Include normalized fields plus `contract:synthetic-normalized-v1` and `patient_id`. Set `INBODY_WEBHOOK_TOKEN` and use it as a bearer token. This is not a live InBody webhook implementation or a guess about vendor signing requirements.

Patient/source-type/source-identifier uniqueness is enforced in the database. Identical content returns the same result; the same identifier with different content returns 409. The Stage 1 server serializes access within one process. Multi-process/race behavior requires additional deployment validation.

## Rules and longitudinal comparison

`rules/clinical-v1.json` is the versioned deterministic rule registry. Each configured threshold includes metric, unit, population restrictions, source date/version, evidence category, explanation, severity and review requirement. The complete rules snapshot is retained with every analysis. `docs/clinical-sources.md` explains the initial narrow evidence scope.

- Source-reported manufacturer reference intervals are applied separately after value confirmation.
- Adult BMI screening review rules use CDC thresholds and require age 20+ on the test date.
- AMA guidance supplies BMI context, not a fabricated numerical threshold.
- No CMS threshold is configured.
- No guessed phase-angle, water-ratio, muscle or visceral-fat thresholds.
- Out-of-range values do not automatically imply urgency, disease or a diagnosis.
- Absent reference findings do not mean every measurement is normal.

The previous study is chosen by **actual test time**, excluding superseded versions and future tests. Comparisons require matching metric/unit and verified values. Changes include the comparison dates, elapsed days, absolute delta and percentage delta where meaningful. Body-fat percent changes use percentage points. Units, estimates and testing conditions matter. Numerical direction is not labeled clinical improvement or worsening without an approved rule.

The interface can display a different study comparison without modifying the stored analysis. Reanalysis appends a new analysis version and returns it to pending review.

## AI provider configuration

Deterministic summaries always work without AI. Paid OpenAI-compatible endpoints are implemented through `ModelProvider`:

```text
AI_ENABLED=true
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=YOUR_SECRET
AI_MODEL=YOUR_AVAILABLE_MODEL
```

Select a model available in the configured account that supports JSON-object responses. A later local Qwen server can use an OpenAI-compatible loopback endpoint, or implement `LocalModelProvider.synthesize`. Google Drive export stays disabled behind its own storage adapter.

The Stage 1 AI interface is intentionally constrained: the model selects and organizes sentences from deterministic evidence. Arbitrary clinical prose, invented facts, diagnoses and treatment instructions are rejected. Provider identifiers, reported model and interface version are retained. No patient identifiers or source documents are sent to the model, but measurement statements could still be sensitive; the application accepts synthetic records only. Unavailable or malformed AI responses fall back to deterministic summaries and record the failure status. The paid HTTP contract is tested with a mocked response; no live paid account was used.

## Security and review

Set distinct server-side operator and clinician tokens (at least 32 characters each). Enter a token through the interface; it stays in page memory and is cleared on reload, not stored in browser storage. Operators may ingest/analyze. Clinicians may append corrections and accept/hold analyses. The separate webhook token cannot call patient endpoints. These static shared role tokens are an authentication abstraction for Stage 1, not institutional identity or multi-tenant authorization.

Only explicitly synthetic records are accepted. Every authorized user operates in a single-clinic workspace; result routes enforce patient/result binding. This is not per-provider patient-assignment authorization. Do not relabel real records as synthetic.

Review requires a current analysis ID, confirmed patient/encounter/test association and verified measurements. A stale analysis ID returns 409. Source results, analyses, reviews, audit events and outbox notifications are append-only. Corrections link a new result to the prior version; originals remain queryable.

Loopback HTTP is intended only for local development. For authenticated network operation, use a tested TLS reverse proxy and firewall, set `INBODY_ALLOWED_HOSTS` explicitly, keep database/storage private, and configure backups, disk encryption, institutional authentication and independently reviewed access policies. Encrypted network transport and at-rest encryption are deployment responsibilities, not claims about this prototype. Original source files are stored with restricted local permissions on POSIX systems. Windows permissions need workstation verification.

The built-in Python HTTP server is suitable for bounded workstation proof-of-concept use. Hardened application serving, upload/OCR resource isolation, rate limits, threat review, and operational monitoring are required before real data or network exposure. Unprocessed content-addressed files can remain after a failed database write; future retention tooling must reconcile orphan files safely.

## API documentation

`docs/openapi.json` documents the REST contract (OpenAPI 3.1), also served at `/openapi.json`. Health is available at `/health`.

Required endpoints:

- `POST /patients/{patient_id}/inbody/import`
- `POST /inbody/webhook`
- `GET /patients/{patient_id}/inbody`
- `GET /patients/{patient_id}/inbody/{result_id}`
- `GET /patients/{patient_id}/inbody/trends`
- `POST /patients/{patient_id}/inbody/{result_id}/analyze`
- `POST /patients/{patient_id}/inbody/{result_id}/review`
- `GET /health`

Additional patient/encounter creation, clinician-only corrections, source metadata and patient-scoped original source downloads are documented. Generate the contracts with `python scripts/generate_contracts.py`.

## Verification

```bash
python -m unittest discover -s tests -v
node --check frontend/app.js
node tests/test_frontend.cjs
```

The suite covers the requested scenarios including actual PDF parsing and screenshot OCR, unreadable/missing values, duplicates, wrong associations, repeat testing, interval changes, rules/conflicts, AI failure/malformed responses, reviews, provenance, timestamps, corrections, database restart and patient isolation. The acceptance test performs ten consecutive synthetic end-to-end flows without code changes, using a deterministic AI test provider. It checks source association, preserved timestamps, analysis, comparison, both summaries, review, history, provenance and encounter outbox notifications.

This is an offline proof. Live vendor data, paid account access, real report-layout accuracy, PostgreSQL target execution, Docker startup, Windows installation, and production security have not been certified by these tests. See `docs/verification.md` for the actual build verification.

## Repository and GitHub

The source is initialized as a clean standalone Git repository with incremental commits. Do not commit `.env`, runtime databases, screenshots, original patient reports or secrets. The `.gitignore` and `.dockerignore` exclude runtime data and local configuration.

To create and push a new private GitHub repository with an authenticated GitHub CLI:

```bash
bash scripts/publish.sh
```

For Windows without Bash, after `gh auth login`:

```powershell
gh repo create InBodyStage1 --private --source=. --remote=origin --push
```

An existing repository needs a normal remote/push instead of create. Source repository: https://github.com/DrDraesel/InBodyStage1 . The repository is public by explicit owner authorization; runtime data and secrets are excluded.

## Stage 2 integration boundaries

Preserve GHL/Toma as the business/referral router and Cortex as the governed reasoning layer. Future integration consumes the structured result and review status, not uncontrolled AI prose. The local encounter outbox is an integration seam, not an externally delivered notification. Add a durable dispatcher/acknowledgment mechanism before delivery. Google Drive may receive governed source exports behind `GoogleDriveStorage`; it is not the runtime database. Intake/HPI can later share patient/encounter bindings through a separate module; this Stage 1 attachment did not authorize building an intake engine.

The downloadable source package includes `source-history.bundle` with the incremental Git history. To recover it as a repository, run `git clone source-history.bundle InBodyStage1-checkout` from the extracted package directory. The bundle has no remote and contains source only.

## Vercel visual preview (v0.1.1 addition)

A separate synthetic preview is ready for Vercel. Run `node scripts/build-preview.mjs`; `vercel.json` publishes only `dist-preview`. See `docs/vercel-preview.md`. The preview reuses the clinical interface with precomputed synthetic studies and an in-memory demonstration adapter. It does not host the local database, imports, AI credentials or live patient API. The source repository is available at https://github.com/DrDraesel/InBodyStage1 . Vercel deployment remains pending account access; no hosted preview URL is claimed.

## Printed results and code capture

See [printed-result-import.md](docs/printed-result-import.md) for the photograph/PDF extraction preview, barcode/QR decoding, handheld scanner entry, retained full source text, manual transcription and LookinBody sync prerequisites. The device Wi-Fi connection is Founder-reported; automatic sync remains unconfigured.
