/* Candidate, Company, Contact forms */
(function () {
  const api = window.VH.api;

  function showNote(form, msg, ok) {
    const n = form.querySelector('.form-note');
    if (!n) return;
    n.textContent = msg;
    n.classList.remove('is-success', 'is-error');
    n.classList.add(ok ? 'is-success' : 'is-error');
  }

  function collect(form) {
    const data = {};
    Array.from(form.querySelectorAll('input, select, textarea')).forEach((el) => {
      if (!el.name) return;
      if (el.type === 'checkbox') return; // ignore terms in payload
      if (el.type === 'file') return;
      data[el.name] = el.value.trim();
    });
    return data;
  }

  // ---------- Candidate form ----------
  const candForm = document.getElementById('candidate-form');
  if (candForm) {
    const fileInput = candForm.querySelector('#resume');
    const dropZone = candForm.querySelector('.file-drop');
    const fileMeta = candForm.querySelector('[data-testid="resume-file-meta"]');

    function updateFileMeta() {
      if (fileInput.files && fileInput.files[0]) {
        const f = fileInput.files[0];
        fileMeta.textContent = `${f.name} · ${(f.size / 1024).toFixed(0)} KB`;
      } else {
        fileMeta.textContent = '';
      }
    }
    fileInput.addEventListener('change', updateFileMeta);
    ['dragenter','dragover'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add('is-drag'); }));
    ['dragleave','drop'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove('is-drag'); }));
    dropZone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        fileInput.files = e.dataTransfer.files;
        updateFileMeta();
      }
    });

    candForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!candForm.checkValidity()) {
        showNote(candForm, 'Please complete the required fields.', false);
        candForm.reportValidity();
        return;
      }
      if (!candForm.querySelector('#terms').checked) {
        showNote(candForm, 'Please accept the terms to continue.', false);
        return;
      }
      const submitBtn = candForm.querySelector('[type="submit"]');
      const original = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = 'Submitting…';
      try {
        const payload = collect(candForm);
        // Upload resume first (if present)
        if (fileInput.files && fileInput.files[0]) {
          showNote(candForm, 'Uploading resume…', true);
          const fd = new FormData();
          fd.append('file', fileInput.files[0]);
          const res = await fetch('/api/upload/resume', { method: 'POST', body: fd });
          const j = await res.json();
          if (!res.ok) throw new Error(j.error || 'Resume upload failed');
          payload.resume_path = j.path;
          payload.resume_filename = j.filename;
        }
        await api('/api/candidates', { method: 'POST', body: JSON.stringify(payload) });
        showNote(candForm, 'Profile received. We\'ll be in touch when there\'s a fit.', true);
        candForm.reset();
        fileMeta.textContent = '';
      } catch (err) {
        showNote(candForm, err.message || 'Submission failed.', false);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = original;
      }
    });
  }

  // ---------- Company form ----------
  const compForm = document.getElementById('company-form');
  if (compForm) {
    compForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!compForm.checkValidity()) {
        showNote(compForm, 'Please complete the required fields.', false);
        compForm.reportValidity();
        return;
      }
      if (!compForm.querySelector('#terms').checked) {
        showNote(compForm, 'Please accept the terms to continue.', false);
        return;
      }
      const submitBtn = compForm.querySelector('[type="submit"]');
      const original = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = 'Sending…';
      try {
        await api('/api/companies', { method: 'POST', body: JSON.stringify(collect(compForm)) });
        showNote(compForm, 'Brief received. A consultant will reach out within one working day.', true);
        compForm.reset();
      } catch (err) {
        showNote(compForm, err.message || 'Submission failed.', false);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = original;
      }
    });
  }

  // ---------- Contact form ----------
  const contactForm = document.getElementById('contact-form');
  if (contactForm) {
    contactForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!contactForm.checkValidity()) {
        showNote(contactForm, 'Please complete the required fields.', false);
        contactForm.reportValidity();
        return;
      }
      const submitBtn = contactForm.querySelector('[type="submit"]');
      const original = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = 'Sending…';
      try {
        await api('/api/contact', { method: 'POST', body: JSON.stringify(collect(contactForm)) });
        showNote(contactForm, 'Message received. We\'ll respond shortly.', true);
        contactForm.reset();
      } catch (err) {
        showNote(contactForm, err.message || 'Submission failed.', false);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = original;
      }
    });
  }
})();
