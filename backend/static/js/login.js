/* Admin login */
(function () {
  const form = document.getElementById('login-form');
  if (!form) return;
  const note = form.querySelector('.form-note');

  function setNote(msg, ok) {
    note.textContent = msg;
    note.classList.remove('is-success', 'is-error');
    note.classList.add(ok ? 'is-success' : 'is-error');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = form.querySelector('#email').value.trim();
    const password = form.querySelector('#password').value;
    if (!email || !password) { setNote('Enter email and password.', false); return; }
    const btn = form.querySelector('[type="submit"]');
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = 'Signing in…';
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Login failed');
      localStorage.setItem('vh_token', data.token);
      localStorage.setItem('vh_user', JSON.stringify(data.user));
      setNote('Signed in. Redirecting…', true);
      setTimeout(() => { window.location.href = '/admin'; }, 250);
    } catch (err) {
      setNote(err.message || 'Login failed.', false);
    } finally {
      btn.disabled = false;
      btn.innerHTML = original;
    }
  });
})();
