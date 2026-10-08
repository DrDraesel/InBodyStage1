# Printed InBody results and connectivity — v0.1.2

## Capture and import

Run the local application, select the patient and encounter, and choose Import result.
Choose Printed sheet / screenshot / photo or PDF result sheet. Select up to five original
files, or use Photograph a printed result sheet on a supported phone browser.
Only PNG/JPEG and unencrypted PDFs (1–10 pages each) are accepted.

Use Extract text, measurements & codes before importing. The preview does not create a
clinical result. Check the full extracted text, code contents and suggested measurements
against the original. Explicit labels and units are required; charts and unsupported
layouts may require transcription in the measurement JSON. Segmental lean/fat mass,
body water, phase angle and ECW/TBW are supported when explicitly labeled with units.
Do not interpret a missing field as a normal result.

Enter the actual test date/time with timezone, source identifier and device model.
A USB/Bluetooth scanner configured as a keyboard can enter its decoded string into the
scanner field. The app does not pair the scanner. Codes are unverified source evidence;
no URL is fetched and no code automatically assigns a patient, encounter or measurement.
A printed QR may identify a report or provide an interpretation link; it is not guaranteed
to carry the complete measurements.

Import retains the original file hash, per-page text, decoded codes, operator scanner
entry, measurement candidates and extraction version. Transcribed file values remain
unverified until a clinician creates a confirmed/corrected linked version. Original
source evidence is preserved through that correction. Structured export includes this
source evidence for the future Coherence handoff. Patient identity and test timestamps
are explicitly confirmed; OCR does not silently set them.

## Automatic sync

Founder reported on October 8, 2026 that the InBody is connected to the Innovative
Medical Wellness Wi-Fi network. This is operator-reported, not remotely verified here.
Wi-Fi alone does not enable result synchronization with InBodyStage1.
The app's readiness panel reports automatic sync as not configured.

Required next evidence:

1. Exact InBody model and firmware.
2. Device registered and connected to the clinic's LookinBody Web account.
3. Approved, active API access and its official documentation.
4. Backend server IP whitelist and official webhook setup, where applicable.
5. A synthetic/deidentified response and printed sheet to validate every available field,
   units, timestamps, identity binding, duplicates and historical-data retrieval.

Official API onboarding: https://lbwebfaq.inbodyusa.com/support/solutions/articles/69000848771-lb-web-integration-api-key-setup
Device/cloud connection: https://inbodyusa.zendesk.com/hc/en-us/articles/360021086932-How-to-connect-your-InBody-unit-to-your-LookinBody-Web-account
Do not put vendor credentials in GitHub, the frontend or a chat message.
Vendor response mapping remains deliberately disabled pending the validated contract.
No local network discovery or proprietary protocol is guessed.

## Coherence continuity

InBodyStage1 passes its complete provenance-preserving result package to Coherence.
Hermes coordinates authorized access; the future central runtime associates the package
with intake/HPI and the encounter. The specialist app does not independently read/write
Google Vault or Notion Cortex. GHL/Toma remains the business/referral router. Module
analysis, source confirmation and clinician acceptance remain distinct states.

## Current verification limits

Real synthetic QR and Code128 images, mixed text/scanned PDFs, explicit unit/segment
parsing, transcription, retained original evidence and correction inheritance are tested.
A sheet from this exact device and actual LookinBody API response are still needed for
layout accuracy and complete-field sync validation. The local backend remains a
synthetic-only development application. The Vercel static preview does not run OCR,
store clinical files or connect to the InBody device.
