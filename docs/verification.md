# Build verification

Verification performed October 7, 2026 for InBodyStage1 v0.1.0.

| Check | Result |
|---|---|
| Python synthetic suite | **45 tests passed** |
| Consecutive acceptance flows | **10 passed**, no code changes between flows |
| PDF import | Actual PDF text extraction passed |
| Screenshot import | Actual local Tesseract OCR passed |
| Multipart HTTP upload | Actual multipart PDF request passed |
| Paid-model HTTP contract | Mocked OpenAI-compatible JSON response passed |
| AI fallback / fabricated prose | Rejected or fell back safely in tests |
| Immutable records / linked corrections | Passed |
| SQLite restart/recovery | Passed |
| Patient/result/source binding | Passed; includes negative cross-patient tests |
| Source hash tampering | Detected |
| Operator/clinician/webhook token separation | Passed |
| Server startup and seeded data | Passed: 2 synthetic patients, 3 studies |
| Health and OpenAPI HTTP response | Passed |
| JavaScript syntax | Passed (`node --check`) |
| Frontend isolated view-model smoke checks | Passed: overview, trend SVG, summaries, provenance, history, empty state |
| Generated schema/OpenAPI reproducibility | Passed |
| Real browser visual / interactive QA | **Blocked**: cloud browser rejects local loopback URL; local browser executable unavailable |
| Live InBody vendor connection | **Not enabled**: account-specific mapping/credentials required |
| Live paid AI request | **Not run**: credentials/model required |
| PostgreSQL / Docker target | **Not run**: target services unavailable in build environment |
| Windows workstation install | **Not run** |
| GitHub source | Repository initialized at https://github.com/DrDraesel/InBodyStage1; source publication verification recorded in the task handoff |

The ten-run acceptance test is `test_ten_consecutive_acceptance_flows`. It imports normalized synthetic fixtures and uses `EvidenceAI`, a controlled test provider. Each run checks preserved timestamp, verified measurements, associated encounter, prior-study selection, structured findings, both summaries, explicit clinician acceptance, retained history, AI provenance and the local encounter outbox. This verifies offline workflow integrity and does not prove a live vendor or paid-model integration.

Run the checks from the repository root:

```bash
python -m unittest discover -s tests -v
node --check frontend/app.js
node tests/test_frontend.cjs
python -m compileall -q backend adapters scripts
python scripts/generate_contracts.py
git diff --exit-code docs/openapi.json schemas/normalized-v1.json
```

Browser and workstation checks remain necessary before calling the proof of concept fully accepted for the clinic's actual device/report layouts. No real patient data was used.

## Vercel preview follow-up

The static preview build, isolated preview adapter tests and frontend view-model checks passed; the 45 backend tests still pass after the preview addition. Fixed synthetic sample import, duplicate handling, simulated review, history/trends and patient isolation were checked. A standalone HTML preview is available. GitHub and Vercel browser sessions required sign-in; the secure GitHub sign-in request timed out and browser verification could not complete. Neither service is claimed as published.

The owner created `DrDraesel/InBodyStage1` and explicitly authorized public source publication. The GitHub connector has confirmed write access. Vercel remains a separate synthetic static preview target and is not yet claimed as deployed.
