type UploadPageOptions = {
  date?: string;
  receiptId?: string;
  items: string[];
  targetUrl: string;
};

export function renderUploadPage(options: UploadPageOptions): string {
  const itemsList = options.items.length ? options.items : ["Breakfast", "Lunch", "Dinner", "Meds AM", "Meds PM"];
  const encodedItems = JSON.stringify(itemsList);
  const today = new Date().toISOString().slice(0, 10);
  const dateValue = options.date || today;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Upload Receipt Checklist</title>
  <style>
    :root { color-scheme: light; }
    body { font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif; margin: 0; padding: 1.25rem; background: #f7f8fb; color: #0f172a; }
    main { max-width: 720px; margin: 0 auto; background: #fff; border-radius: 14px; padding: 1.25rem; box-shadow: 0 18px 36px -20px rgba(15, 23, 42, 0.25); }
    h1 { margin: 0 0 0.5rem; font-size: 1.4rem; }
    p { margin: 0 0 0.75rem; color: #475569; }
    form { display: grid; gap: 0.75rem; }
    label { display: grid; gap: 0.35rem; font-weight: 600; color: #0f172a; }
    input[type=\"file\"], input[type=\"date\"], input[type=\"text\"] { padding: 0.6rem; font-size: 1rem; border: 1px solid #cbd5e1; border-radius: 10px; }
    button { padding: 0.75rem 1rem; border: none; background: #2563eb; color: #fff; font-size: 1rem; border-radius: 10px; cursor: pointer; box-shadow: 0 10px 28px -16px rgba(37, 99, 235, 0.7); }
    button:disabled { opacity: 0.6; cursor: not-allowed; box-shadow: none; }
    .card { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 12px; padding: 0.75rem; }
    .items { display: grid; gap: 0.3rem; padding-left: 1rem; color: #0f172a; }
    .result { margin-top: 1rem; background: #0f172a; color: #e2e8f0; border-radius: 12px; padding: 0.75rem; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 0.95rem; }
  </style>
</head>
<body>
  <main>
    <h1>Upload your receipt photo</h1>
    <p>Take a clear photo of the printed checklist. Keep the receipt flat and the QR/corner marks visible for best results.</p>
    <div class=\"card\">
      <strong>Items on this receipt:</strong>
      <div class=\"items\">
        ${itemsList.map((item) => `<span>• ${escapeHtml(item)}</span>`).join("")}
      </div>
    </div>
    <form id=\"uploadForm\" enctype=\"multipart/form-data\" method=\"post\" action=\"${options.targetUrl}\">
      <input type=\"hidden\" name=\"items\" value='${encodeURIComponent(encodedItems)}'>
      <label>Receipt photo<input type=\"file\" name=\"receipt\" accept=\"image/*\" capture=\"environment\" required></label>
      <label>Date<input type=\"date\" name=\"date\" value=\"${dateValue}\"></label>
      <label>Receipt ID<input type=\"text\" name=\"receipt_id\" value=\"${options.receiptId ?? ""}\" placeholder=\"Optional tracking ID\"></label>
      <button type=\"submit\">Upload & analyze</button>
    </form>
    <pre id=\"result\" class=\"result\" style=\"display:none\"></pre>
  </main>
  <script>
    const form = document.getElementById('uploadForm');
    const result = document.getElementById('result');
    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
      result.style.display = 'block';
      result.textContent = 'Processing...';
      try {
        const response = await fetch(form.action, { method: 'POST', body: fd });
        const json = await response.json();
        result.textContent = JSON.stringify(json, null, 2);
      } catch (err) {
        result.textContent = 'Upload failed: ' + err;
      }
    });
  </script>
</body>
</html>`;
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;");
}
