// OliveTin 3000.19.0 refreshes Init on configuration events, but Dashboard.vue
// does not reload its dashboard data. Use the supported custom-JS extension
// until that upstream component handles EventConfigChanged itself.
(() => {
  const style = document.createElement('style');
  style.textContent = `
    fieldset:has(.transfer-status) { display: block; width: auto; max-width: 960px; margin-inline: auto; }
    .dashboard-row:has(.transfer-status) .display { width: 100%; padding: 24px; box-sizing: border-box; }
    .dashboard-row:has(.transfer-status) .display > div { width: 100%; min-width: 0; }
    .transfer-status { overflow-wrap: anywhere; }
    .transfer-status h2, .transfer-status h3 { margin: 0.5em 0; }
  `;
  document.head.append(style);
  let changed = false;
  let lastActivity = Date.now();
  for (const event of ['pointerdown', 'keydown']) {
    window.addEventListener(event, () => { lastActivity = Date.now(); }, { passive: true });
  }
  for (const event of ['EventConfigChanged', 'EventEntityChanged']) {
    window.addEventListener(event, () => { changed = true; });
  }
  window.setInterval(() => {
    for (const rate of document.querySelectorAll('[data-speed-at]')) {
      if (Date.now() / 1000 - Number(rate.dataset.speedAt) > 45) {
        rate.textContent = 'Waiting for fresh speed data';
        rate.removeAttribute('data-speed-at');
      }
    }
    if (!changed || document.visibilityState !== 'visible') return;
    if (document.body.getAttribute('loaded-dashboard') !== 'Catalog') return;
    if (document.querySelector('dialog[open], [role="dialog"], input:focus, textarea:focus, select:focus, [contenteditable="true"]:focus')) return;
    if (Date.now() - lastActivity < 15000) return;
    window.location.reload();
  }, 5000);
})();
