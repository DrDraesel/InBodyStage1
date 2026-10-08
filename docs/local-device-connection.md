# Local InBody 380 connection without a cloud API

The operator's sample identifies an InBody 380. Device Wi-Fi is reported as connected to Innovative Medical Wellness; no hardware pairing or data transfer has been verified from this development session. Vercel hosts the synthetic visual preview; it cannot pair the clinic's local Bluetooth device. The printer cable is not a PC data connection.

## Without LookinBody registration or credentials

The 380 manual documents local USB Excel export. Insert a flash drive in an available USB host port; choose **Setup → 4. Data Management → Export Data as an MS Excel File**; select a test or date range, then export. Move the drive to the clinic computer. This device-side operation uses the device Setup passcode, not a LookinBody username/password. It is a file transfer rather than a continuous Wi-Fi connection. Avoid a full-history export during active testing because it can occupy the device.

Copy exports to a local inbox and run the bridge below. `.xls` and `.xlsx` originals are retained alongside CSV and images; vendor Excel field mapping is not enabled until a sample export is validated. Do not upload an Excel export through the current PDF/image form. A printed-sheet photo or scan can be imported and transcribed immediately without vendor credentials. If the device Setup passcode is also missing, use the printed-sheet path while obtaining an authorized reset from InBody support (323-932-6503 ext. 2). This bridge does not bypass the device passcode or claim to implement an undocumented Wi-Fi protocol.

## On the clinic computer

1. Install the licensed LookinBody 120 software and activate it with its InBody USB hard-lock key. Use the [official installation guide](https://lbwebfaq.inbodyusa.com/support/solutions/articles/69000880625-lookinbody-120-installation-guide). Its screenshots use an InBody120 scale; use the InBody 380 manual for your device connection.
2. Pair the 380 in LookinBody's device connection setup. The [380 manual](https://inbodyusa.zendesk.com/hc/en-us/articles/26353282696084-InBody-380-User-s-Manual), sections 5.6–5.8, documents a serial PC connection and Bluetooth. Use the administrator passcode to enable the supported connection. A blocked passcode needs authorized reset through InBody support; the bridge does not bypass it. Do not disconnect the printer to repurpose its USB cable.
3. Confirm LookinBody actually receives a completed test. Wi-Fi association alone does not establish a measurement stream to this app.
4. In LookinBody, choose **Setup → 10. Export Data as CSV/Image Files**. Select a local folder, enable automatic export after every test, and retain both CSV and image where offered. See [official export instructions](https://inbodyusa.zendesk.com/hc/en-us/articles/360021198652-Export-your-InBody-data-into-csv-on-LookinBody-120).
5. With Python, requirements and Tesseract installed, run from this repository root:

```powershell
python -m scripts.local_export_bridge --inbox "C:\IMW\InBodyExports" --queue "C:\IMW\InBodyReview" --watch
```

The folders are examples: use your actual LookinBody export folder. This bridge runs on the clinic computer, not Vercel. No cloud API key or subscription is used by the bridge; LookinBody software licensing still applies.

## What the bridge does

After a file is stable for three seconds, it keeps an exact original in a SHA-256-addressed review package. PNG/JPEG/PDF exports receive OCR/text and QR/barcode extraction. CSV/Excel/BMP exports are retained in full without guessing proprietary field mappings. Repeated unchanged files are skipped. Source exports remain untouched. Packages contain no automatic patient/encounter assignment and do not create clinical records.

Open the original PNG/JPEG/PDF in the app's **Import result**, extract, associate with the correct patient and encounter, enter the actual test timestamp/timezone, and confirm source values. A normalized vendor CSV mapping and integrated review-queue UI remain future work. This remains a synthetic development workspace; the bridge's output is source evidence, not an approved clinical record. Keep review packages outside the Git repository. Windows folder access controls must be configured on the clinic computer.

## Current sample extraction limit

The supplied photograph was tested locally. Its QR decodes to an InBody results-interpretation URL, which is retained and not followed. Several labels are faint and graph/history values share rows. The conservative parser therefore leaves uncertain measurements unresolved; an original digital export or manual transcription is needed. The photograph and personal values are not included in this repository.
