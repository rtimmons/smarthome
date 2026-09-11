// OliveTin 3000.19.0 refreshes Init on configuration events, but Dashboard.vue
// does not reload its dashboard data. Use the supported custom-JS extension
// until that upstream component handles EventConfigChanged itself.
(() => {
  let changed = false;
  let lastActivity = Date.now();
  for (const event of ['pointerdown', 'keydown']) {
    window.addEventListener(event, () => { lastActivity = Date.now(); }, { passive: true });
  }
  for (const event of ['EventConfigChanged', 'EventEntityChanged']) {
    window.addEventListener(event, () => { changed = true; });
  }
  window.setInterval(() => {
    if (!changed || document.visibilityState !== 'visible') return;
    if (document.body.getAttribute('loaded-dashboard') !== 'Catalog') return;
    if (document.querySelector('dialog[open], [role="dialog"], input:focus, textarea:focus, select:focus, [contenteditable="true"]:focus')) return;
    if (Date.now() - lastActivity < 15000) return;
    window.location.reload();
  }, 5000);
})();
