document.addEventListener('DOMContentLoaded', function () {
  const passwordToggle = document.querySelector('[data-password-toggle]');
  const passwordInput = passwordToggle
    ? passwordToggle.closest('.login-password-wrap')?.querySelector('input')
    : null;

  if (passwordInput && passwordToggle) {
    passwordToggle.addEventListener('click', function () {
      const isVisible = passwordInput.type === 'text';
      passwordInput.type = isVisible ? 'password' : 'text';
      const label = isVisible ? 'Show' : 'Hide';
      passwordToggle.querySelector('.password-toggle-label').textContent = label;
      passwordToggle.setAttribute('aria-label', label + ' password');
      passwordToggle.setAttribute('title', label + ' password');
      passwordToggle.setAttribute('aria-pressed', String(!isVisible));
    });
  }

  const loginForm = document.querySelector('.login-form');
  const submitButton = loginForm?.querySelector('.login-submit');

  if (loginForm && submitButton) {
    loginForm.addEventListener('submit', function () {
      submitButton.disabled = true;
      submitButton.querySelector('.login-submit-label').textContent = 'Signing in...';
    });
  }

  document.querySelectorAll('[data-demo-login]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (!loginForm) return;
      const usernameInput = loginForm.querySelector('[name="username"]');
      const passwordInput = loginForm.querySelector('[name="password"]');
      if (!usernameInput || !passwordInput) return;

      usernameInput.value = button.dataset.demoUsername || '';
      passwordInput.value = button.dataset.demoPassword || '';
      if (typeof loginForm.requestSubmit === 'function') {
        loginForm.requestSubmit(submitButton);
      } else {
        loginForm.submit();
      }
    });
  });
});
