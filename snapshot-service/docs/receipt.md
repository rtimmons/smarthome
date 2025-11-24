# Receipt checklist flow

This service exposes a local-only flow for processing printed checklists:

- **Print**: The `printer` add-on uses the `receipt_checklist` template to render checkboxes, fiducial bars, corner marks, and a QR code that points at this service.
- **Upload**: Scanning the QR (or visiting the printed URL) opens `/receipt/upload`, a simple page that captures a photo of the receipt.
- **Analyze**: The photo is posted to `/receipt/analyze` (multipart `receipt` field). The service runs local image processing (no cloud) to find the receipt, map the checkbox grid, and return JSON indicating which boxes are checked.

## Endpoints

- `GET /receipt/upload` — renders the upload page. Query params: `date`, `receipt_id`, `items` (URL-encoded JSON array), `layout` (optional).
- `POST /receipt/analyze` — multipart upload with `receipt` (image), optional `items`, `date`, `receipt_id`. Response matches `src/schema/receipt.ts`.

## Developer notes

- The checklist layout constants live in `src/receipt/layout.ts` and match the printed template (29x90 label by default).
- Image processing in `src/receipt/processor.ts`:
  - Rotates to portrait, converts to grayscale.
  - Finds the receipt bounding box using dark pixels (outline/fiducials).
  - Scales known checkbox positions, samples the center of each box, and marks checked when the mean pixel value is below a threshold.
- Tests:
  - `tests/receipt.test.ts` generates synthetic receipts to verify detection and failure cases.
  - `tests/receipt-routes.test.ts` exercises the upload page and multipart analyzer endpoint with a synthetic image.

## Quick demo

1. Start services: `cd snapshot-service && just dev` and `cd printer && just dev`.
2. Generate/print a checklist: `cd snapshot-service && ./check.sh --print` (defaults to checklist mode; add `--snapshot` for the daily snapshot preview).
3. Check some boxes, scan the QR, upload the photo. You’ll get JSON showing which boxes were checked.
