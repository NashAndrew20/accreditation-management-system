(function () {
  const checkbox = document.querySelector('[data-consent-checkbox]');
  const submit = document.querySelector('[data-consent-submit]');
  const valueInput = document.getElementById('consent-acknowledge-value');
  if (!checkbox || !submit || !valueInput) return;

  function sync() {
    const checked = checkbox.checked;
    submit.disabled = !checked;
    valueInput.value = checked ? '1' : '0';
  }

  checkbox.addEventListener('change', sync);
  sync();
})();