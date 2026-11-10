(() => {
  const key = 'qurilish-crm-theme';
  const root = document.documentElement;
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference;
  try { preference = localStorage.getItem(key); } catch (_) { /* Storage may be unavailable. */ }
  function apply(theme) {
    const dark = theme === 'dark';
    root.dataset.theme = dark ? 'dark' : 'light';
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-pressed', String(dark));
      button.setAttribute('aria-label', dark ? 'Yorug‘ rejimni yoqish' : 'Qorong‘u rejimni yoqish');
      button.querySelector('[data-theme-icon]').textContent = dark ? '☀' : '☾';
      button.querySelector('[data-theme-label]').textContent = dark ? 'Yorug‘ rejim' : 'Qorong‘u rejim';
    });
  }
  const preferred = () => preference === 'dark' || preference === 'light' ? preference : (system.matches ? 'dark' : 'light');
  apply(preferred());
  document.addEventListener('DOMContentLoaded', () => {
    apply(preferred());
    document.querySelectorAll('[data-theme-toggle]').forEach(button => button.addEventListener('click', () => {
      preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, preference); } catch (_) { /* Keep the current page usable. */ }
      apply(preference);
    }));
  });
  system.addEventListener('change', () => apply(preferred()));
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) {
      preference = event.newValue;
      apply(preferred());
    }
  });
})();
