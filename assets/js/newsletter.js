(function () {
  var forms = document.querySelectorAll('form[data-newsletter-form]');
  if (!forms.length) return;

  forms.forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      if (form.dataset.enhanced === '1') return;
      ev.preventDefault();
      form.dataset.enhanced = '1';
      var status = form.querySelector('[data-newsletter-status]');
      var btn = form.querySelector('[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.dataset.label = btn.textContent;
        btn.textContent = btn.getAttribute('data-loading') || '…';
      }
      var fd = new FormData(form);
      fd.append('ajax', '1');
      fetch(form.action, {
        method: 'POST',
        body: fd,
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, body: j };
          });
        })
        .then(function (res) {
          if (status) {
            status.hidden = false;
            status.setAttribute('role', 'alert');
            if (res.ok && res.body.ok) {
              status.style.color = '#5ec9ff';
              status.textContent =
                form.getAttribute('data-msg-success') || 'Merci !';
              form.reset();
            } else {
              status.style.color = '#ff8a80';
              status.textContent =
                form.getAttribute('data-msg-error') || 'Une erreur est survenue.';
            }
          }
        })
        .catch(function () {
          if (status) {
            status.hidden = false;
            status.style.color = '#ff8a80';
            status.textContent =
              form.getAttribute('data-msg-error') || 'Une erreur est survenue.';
          }
        })
        .finally(function () {
          if (btn) {
            btn.disabled = false;
            btn.textContent = btn.dataset.label || btn.textContent;
          }
          delete form.dataset.enhanced;
        });
    });
  });
})();
