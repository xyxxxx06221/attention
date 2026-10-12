/* Appearance: light, dark, or following the system. Loaded in <head> without defer so the
   chosen theme is set before first paint. Presentation only; kept in this browser. */
(function () {
  const KEY = 'zhuyi-theme';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  function preference() {
    try {
      const saved = localStorage.getItem(KEY);
      return saved === 'light' || saved === 'dark' ? saved : 'system';
    } catch { return 'system'; }
  }
  function apply() {
    const choice = preference();
    const theme = choice === 'system' ? (system.matches ? 'dark' : 'light') : choice;
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#13191c' : '#faf9f6');
    for (const button of document.querySelectorAll('[data-theme-choice]')) {
      button.setAttribute('aria-checked', String(button.dataset.themeChoice === choice));
    }
  }
  function choose(choice) {
    try {
      if (choice === 'system') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, choice);
    } catch {}
    apply();
  }
  apply();
  system.addEventListener('change', apply);
  document.addEventListener('DOMContentLoaded', apply);
  document.addEventListener('click', event => {
    const button = event.target.closest?.('[data-theme-choice]');
    if (button) choose(button.dataset.themeChoice);
  });
  window.ZhuyiTheme = { preference, apply };
})();
