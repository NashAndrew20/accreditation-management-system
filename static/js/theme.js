(function () {
  const storageKey = 'jmcfi-theme';

  function isTheme(value) {
    return value === 'light' || value === 'dark';
  }

  function readTheme() {
    try {
      const storedTheme = window.localStorage.getItem(storageKey);
      return isTheme(storedTheme) ? storedTheme : 'light';
    } catch (error) {
      return 'light';
    }
  }

  function updateToggle(toggle, theme) {
    const isDark = theme === 'dark';
    const label = toggle.querySelector('[data-theme-label]');
    const icon = toggle.querySelector('[data-theme-icon]');
    toggle.setAttribute('aria-pressed', String(isDark));
    toggle.setAttribute(
      'aria-label',
      isDark ? 'Switch to light mode' : 'Switch to dark mode',
    );
    if (label) label.textContent = isDark ? 'Light mode' : 'Dark mode';
    if (icon) icon.textContent = isDark ? '☀' : '☾';
  }

  function applyTheme(theme, persist) {
    const nextTheme = isTheme(theme) ? theme : 'light';
    document.documentElement.dataset.theme = nextTheme;
    document.documentElement.style.colorScheme = nextTheme;
    if (persist) {
      try {
        window.localStorage.setItem(storageKey, nextTheme);
      } catch (error) {
        // Theme still works for the current page when storage is unavailable.
      }
    }
    document.querySelectorAll('[data-theme-toggle]').forEach(function (toggle) {
      updateToggle(toggle, nextTheme);
    });
  }

  // Apply before the stylesheets paint to avoid a light-mode flash.
  applyTheme(readTheme(), false);

  function bindThemeToggles() {
    document.querySelectorAll('[data-theme-toggle]').forEach(function (toggle) {
      updateToggle(toggle, document.documentElement.dataset.theme || 'light');
      if (toggle.dataset.themeBound === 'true') return;
      toggle.dataset.themeBound = 'true';
      toggle.addEventListener('click', function () {
        const currentTheme = document.documentElement.dataset.theme || 'light';
        applyTheme(currentTheme === 'dark' ? 'light' : 'dark', true);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindThemeToggles);
  } else {
    bindThemeToggles();
  }
})();
