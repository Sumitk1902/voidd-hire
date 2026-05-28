/* Admin dashboard logic */
(function () {
  const api = window.VH.api;
  const token = localStorage.getItem('vh_token');
  if (!token) { window.location.href = '/login'; return; }

  // verify token
  api('/api/auth/me').catch(() => {
    localStorage.removeItem('vh_token');
    window.location.href = '/login';
  });

  const user = JSON.parse(localStorage.getItem('vh_user') || '{}');
  const userEl = document.querySelector('[data-testid="admin-user-label"]');
  if (userEl && user.email) userEl.textContent = user.email;

  document.getElementById('logout-btn').addEventListener('click', () => {
    localStorage.removeItem('vh_token');
    localStorage.removeItem('vh_user');
    window.location.href = '/login';
  });

  // ----- View switching -----
  const viewTitles = {
    overview: ['Overview', 'Live snapshot of the operations desk.'],
    candidates: ['Candidates', 'Manage the talent pipeline.'],
    companies: ['Companies', 'Open hiring briefs and inquiries.'],
    placements: ['Placements', 'Closed roles and matched candidates.'],
    invoices: ['Invoices', 'Generate and track placement billing.'],
    messages: ['Messages', 'Inbound contact form submissions.'],
  };
  function setView(name) {
    document.querySelectorAll('.admin-nav-btn').forEach((b) =>
      b.classList.toggle('is-active', b.dataset.view === name)
    );
    document.querySelectorAll('.admin-view').forEach((v) =>
      v.classList.toggle('is-active', v.dataset.view === name)
    );
    const [t, s] = viewTitles[name] || ['', ''];
    document.getElementById('view-title').textContent = t;
    document.getElementById('view-subtitle').textContent = s;
    if (name === 'overview') loadOverview();
    if (name === 'candidates') loadCandidates();
    if (name === 'companies') loadCompanies();
    if (name === 'placements') loadPlacements();
    if (name === 'invoices') loadInvoices();
    if (name === 'messages') loadMessages();
  }
  document.querySelectorAll('.admin-nav-btn').forEach((b) => {
    b.addEventListener('click', () => setView(b.dataset.view));
  });
  document.getElementById('refresh-btn').addEventListener('click', () => {
    const active = document.querySelector('.admin-nav-btn.is-active').dataset.view;
    setView(active);
  });

  // ----- Drawer / Modal helpers -----
  const drawer = document.getElementById('drawer');
  const drawerBody = document.getElementById('drawer-body');
  const drawerTitle = document.getElementById('drawer-title');
  const drawerEyebrow = document.getElementById('drawer-eyebrow');
  drawer.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', closeDrawer));
  function openDrawer(eyebrow, title, html) {
    drawerEyebrow.textContent = eyebrow;
    drawerTitle.textContent = title;
    drawerBody.innerHTML = html;
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
  }
  function closeDrawer() { drawer.classList.remove('is-open'); drawer.setAttribute('aria-hidden', 'true'); }

  const modal = document.getElementById('modal');
  const modalTitle = document.getElementById('modal-title');
  const modalBody = document.getElementById('modal-body');
  modal.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', closeModal));
  function openModal(title, html) {
    modalTitle.textContent = title;
    modalBody.innerHTML = html;
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
  }
  function closeModal() { modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeDrawer(); closeModal(); }
  });

  // ----- Utilities -----
  function fmtCurrency(n) {
    if (n === null || n === undefined) return '—';
    return '₹ ' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }
  function pill(text, kind) {
    const k = (text || 'new').toLowerCase().replace(/[^a-z]/g, '-');
    return `<span class="status-pill is-${k}">${text || '—'}</span>`;
  }
  function escape(s) { return (s == null ? '' : String(s)).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  // ----- Overview -----
  let overviewLoaded = false;
  async function loadOverview() {
    try {
      const d = await api('/api/admin/analytics');
      document.getElementById('kpi-candidates').textContent = d.totals.candidates;
      document.getElementById('kpi-companies').textContent = d.totals.companies;
      document.getElementById('kpi-shortlisted').textContent = d.totals.shortlisted;
      document.getElementById('kpi-placements').textContent = d.totals.placements;
      document.getElementById('kpi-revenue').textContent = fmtCurrency(d.totals.revenue_paid);
      document.getElementById('kpi-revenue-pending').textContent = fmtCurrency(d.totals.revenue_pending);

      // Trend bars
      const trend = d.trend || [];
      const chart = document.getElementById('trend-chart');
      if (!trend.length) {
        chart.innerHTML = '<div class="muted" style="font-size:13px;padding:20px;">No submissions yet — the chart will populate as candidates apply.</div>';
      } else {
        const max = Math.max(...trend.map((t) => t.count), 1);
        chart.innerHTML = trend.map((t) => {
          const h = Math.max(8, Math.round((t.count / max) * 200));
          return `<div class="bar" style="height:${h}px" data-count="${t.count}" title="${t.date}: ${t.count}"></div>`;
        }).join('');
      }

      // Status bars
      const sb = document.getElementById('status-bars');
      const byStatus = d.candidates_by_status || {};
      const total = Object.values(byStatus).reduce((a, b) => a + b, 0) || 1;
      const order = ['new', 'contacted', 'shortlisted', 'placed', 'rejected'];
      sb.innerHTML = order.map((s) => {
        const v = byStatus[s] || 0;
        const pct = Math.round((v / total) * 100);
        return `
          <div class="status-bar">
            <span class="status-bar-label">${s}</span>
            <span class="status-bar-track"><span class="status-bar-fill" style="width:${pct}%"></span></span>
            <span class="status-bar-count">${v}</span>
          </div>`;
      }).join('');
    } catch (e) {
      console.error('analytics', e);
    }
    overviewLoaded = true;
  }

  // ----- Candidates -----
  const candSearch = document.getElementById('cand-search');
  const candStatusFilter = document.getElementById('cand-status-filter');
  const candShortlistFilter = document.getElementById('cand-shortlist-filter');
  [candSearch, candStatusFilter, candShortlistFilter].forEach((el) =>
    el.addEventListener('input', debounce(loadCandidates, 250))
  );
  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  async function loadCandidates() {
    const params = new URLSearchParams();
    if (candSearch.value) params.set('q', candSearch.value);
    if (candStatusFilter.value) params.set('status', candStatusFilter.value);
    if (candShortlistFilter.checked) params.set('shortlisted', 'true');
    const rows = await api('/api/admin/candidates?' + params.toString());
    const tbody = document.getElementById('cand-tbody');
    const empty = document.getElementById('cand-empty');
    if (!rows.length) {
      tbody.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    tbody.innerHTML = rows.map((c) => `
      <tr data-id="${c.id}" data-testid="candidate-row-${c.id}">
        <td>
          <div class="cell-primary">${escape(c.full_name)}${c.is_shortlisted ? ' <span class="status-pill is-shortlisted">★</span>' : ''}</div>
          <div class="cell-muted">${escape(c.email)}</div>
        </td>
        <td>${escape(c.preferred_role || '—')}</td>
        <td>${escape(c.experience || '—')}</td>
        <td>${escape(c.location || '—')}</td>
        <td>${escape(c.salary_expectation || '—')}</td>
        <td>${pill(c.status)}</td>
        <td class="row-actions">
          <button class="btn btn-ghost btn-sm" data-action="view" data-id="${c.id}" data-testid="candidate-view-${c.id}">View</button>
        </td>
      </tr>
    `).join('');
    tbody.querySelectorAll('[data-action="view"]').forEach((b) =>
      b.addEventListener('click', () => openCandidate(b.dataset.id))
    );
  }

  async function openCandidate(id) {
    try {
      const c = await api('/api/admin/candidates/' + id);
      const notes = await api(`/api/admin/notes/candidate/${id}`);
      const html = `
        <div class="detail-block">
          <h4>Profile</h4>
          <div class="detail-grid">
            <div><label>Email</label><span>${escape(c.email)}</span></div>
            <div><label>Phone</label><span>${escape(c.phone)}</span></div>
            <div><label>Location</label><span>${escape(c.location || '—')}</span></div>
            <div><label>Experience</label><span>${escape(c.experience || '—')}</span></div>
            <div><label>Preferred role</label><span>${escape(c.preferred_role || '—')}</span></div>
            <div><label>Salary expectation</label><span>${escape(c.salary_expectation || '—')}</span></div>
            <div><label>LinkedIn</label><span>${c.linkedin ? `<a href="${escape(c.linkedin)}" target="_blank" rel="noopener">Open ↗</a>` : '—'}</span></div>
            <div><label>Portfolio</label><span>${c.portfolio ? `<a href="${escape(c.portfolio)}" target="_blank" rel="noopener">Open ↗</a>` : '—'}</span></div>
          </div>
        </div>
        <div class="detail-block">
          <h4>Skills</h4>
          <p>${escape(c.skills || '—')}</p>
        </div>
        <div class="detail-block">
          <h4>Status</h4>
          <div class="detail-grid">
            <div>
              <label>Pipeline</label>
              <select id="cand-status-select" class="search-select">
                ${['new','contacted','shortlisted','placed','rejected'].map(s => `<option value="${s}" ${s===c.status?'selected':''}>${s}</option>`).join('')}
              </select>
            </div>
            <div>
              <label>Shortlist</label>
              <label class="checkbox"><input type="checkbox" id="cand-shortlist-cb" ${c.is_shortlisted?'checked':''}/> <span>Mark as shortlisted</span></label>
            </div>
          </div>
        </div>
        <div class="detail-actions">
          ${c.resume_path ? `<button class="btn btn-ghost btn-sm" id="view-resume" data-testid="view-resume-btn">View resume</button>` : ''}
          <button class="btn btn-primary btn-sm" id="save-cand-btn" data-testid="save-candidate-btn">Save changes</button>
          <button class="btn btn-danger btn-sm" id="delete-cand-btn" data-testid="delete-candidate-btn">Delete</button>
        </div>
        <div class="detail-block" style="margin-top:28px;">
          <h4>CRM · Interaction log</h4>
          <div class="notes-list" id="notes-list">
            ${notes.length ? notes.map(n => `
              <div class="note-item">
                <header><span>${escape(n.author)} · ${escape(n.interaction_type)}</span><span>${fmtDate(n.created_at)}</span></header>
                <div>${escape(n.note)}</div>
              </div>`).join('') : '<div class="muted" style="font-size:13px;">No notes yet.</div>'}
          </div>
          <form class="note-form" id="note-form">
            <select id="note-type" class="search-select" style="max-width:200px;">
              <option value="note">Note</option>
              <option value="call">Call</option>
              <option value="email">Email</option>
              <option value="meeting">Meeting</option>
            </select>
            <textarea id="note-text" placeholder="Add an interaction log…" required></textarea>
            <div class="row"><button class="btn btn-primary btn-sm" type="submit" data-testid="add-note-btn">Add note</button></div>
          </form>
        </div>
      `;
      openDrawer('Candidate', c.full_name, html);

      document.getElementById('save-cand-btn').addEventListener('click', async () => {
        const status = document.getElementById('cand-status-select').value;
        const is_shortlisted = document.getElementById('cand-shortlist-cb').checked;
        await api('/api/admin/candidates/' + id, { method: 'PATCH', body: JSON.stringify({ status, is_shortlisted }) });
        closeDrawer();
        loadCandidates();
      });
      document.getElementById('delete-cand-btn').addEventListener('click', async () => {
        if (!confirm('Delete this candidate permanently?')) return;
        await api('/api/admin/candidates/' + id, { method: 'DELETE' });
        closeDrawer();
        loadCandidates();
      });
      const viewResume = document.getElementById('view-resume');
      if (viewResume) {
        viewResume.addEventListener('click', async () => {
          try {
            const res = await fetch('/api/admin/candidates/' + id + '/resume', { headers: { Authorization: 'Bearer ' + localStorage.getItem('vh_token') } });
            if (!res.ok) throw new Error('Failed to fetch resume');
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
          } catch (e) { alert(e.message); }
        });
      }
      document.getElementById('note-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const note = document.getElementById('note-text').value.trim();
        const interaction_type = document.getElementById('note-type').value;
        if (!note) return;
        await api('/api/admin/notes', { method: 'POST', body: JSON.stringify({ entity_type: 'candidate', entity_id: id, note, interaction_type }) });
        openCandidate(id);
      });
    } catch (e) { alert(e.message); }
  }

  // ----- Companies -----
  const compSearch = document.getElementById('comp-search');
  const compStatusFilter = document.getElementById('comp-status-filter');
  [compSearch, compStatusFilter].forEach((el) =>
    el.addEventListener('input', debounce(loadCompanies, 250))
  );

  async function loadCompanies() {
    const params = new URLSearchParams();
    if (compSearch.value) params.set('q', compSearch.value);
    if (compStatusFilter.value) params.set('status', compStatusFilter.value);
    const rows = await api('/api/admin/companies?' + params.toString());
    const tbody = document.getElementById('comp-tbody');
    const empty = document.getElementById('comp-empty');
    if (!rows.length) { tbody.innerHTML = ''; empty.classList.remove('hidden'); return; }
    empty.classList.add('hidden');
    tbody.innerHTML = rows.map((c) => `
      <tr data-id="${c.id}" data-testid="company-row-${c.id}">
        <td><div class="cell-primary">${escape(c.company_name)}</div><div class="cell-muted">${escape(c.email)}</div></td>
        <td>${escape(c.required_role)}</td>
        <td>${escape(c.hr_name)}</td>
        <td>${escape(c.budget || '—')}</td>
        <td>${escape(c.urgency || '—')}</td>
        <td>${pill(c.status)}</td>
        <td class="row-actions">
          <button class="btn btn-ghost btn-sm" data-action="matches" data-id="${c.id}" data-testid="company-matches-${c.id}">Matches</button>
          <button class="btn btn-ghost btn-sm" data-action="view" data-id="${c.id}" data-testid="company-view-${c.id}">View</button>
        </td>
      </tr>
    `).join('');
    tbody.querySelectorAll('[data-action="view"]').forEach((b) =>
      b.addEventListener('click', () => openCompany(b.dataset.id))
    );
    tbody.querySelectorAll('[data-action="matches"]').forEach((b) =>
      b.addEventListener('click', () => openMatches(b.dataset.id))
    );
  }

  async function openCompany(id) {
    const c = await api('/api/admin/companies/' + id);
    const notes = await api(`/api/admin/notes/company/${id}`);
    const html = `
      <div class="detail-block">
        <h4>Hiring brief</h4>
        <div class="detail-grid">
          <div><label>Company</label><span>${escape(c.company_name)}</span></div>
          <div><label>HR / contact</label><span>${escape(c.hr_name)}</span></div>
          <div><label>Email</label><span>${escape(c.email)}</span></div>
          <div><label>Phone</label><span>${escape(c.phone)}</span></div>
          <div><label>Required role</label><span>${escape(c.required_role)}</span></div>
          <div><label>Experience</label><span>${escape(c.experience_required || '—')}</span></div>
          <div><label>Budget</label><span>${escape(c.budget || '—')}</span></div>
          <div><label>Urgency</label><span>${escape(c.urgency || '—')}</span></div>
          <div><label>Timeline</label><span>${escape(c.hiring_timeline || '—')}</span></div>
          <div><label>Submitted</label><span>${fmtDate(c.created_at)}</span></div>
        </div>
      </div>
      <div class="detail-block">
        <h4>Skills required</h4>
        <p>${escape(c.skills_required || '—')}</p>
      </div>
      ${c.additional_notes ? `<div class="detail-block"><h4>Additional notes</h4><p>${escape(c.additional_notes)}</p></div>` : ''}
      <div class="detail-block">
        <h4>Status</h4>
        <div class="detail-grid">
          <div>
            <label>Pipeline</label>
            <select id="comp-status-select" class="search-select">
              ${['new','in_progress','closed','dropped'].map(s => `<option value="${s}" ${s===c.status?'selected':''}>${s.replace('_',' ')}</option>`).join('')}
            </select>
          </div>
        </div>
      </div>
      <div class="detail-actions">
        <button class="btn btn-primary btn-sm" id="save-comp-btn" data-testid="save-company-btn">Save changes</button>
        <a class="btn btn-ghost btn-sm" href="mailto:${escape(c.email)}">Email contact</a>
      </div>
      <div class="detail-block" style="margin-top:28px;">
        <h4>CRM · Interaction log</h4>
        <div class="notes-list">
          ${notes.length ? notes.map(n => `
            <div class="note-item">
              <header><span>${escape(n.author)} · ${escape(n.interaction_type)}</span><span>${fmtDate(n.created_at)}</span></header>
              <div>${escape(n.note)}</div>
            </div>`).join('') : '<div class="muted" style="font-size:13px;">No notes yet.</div>'}
        </div>
        <form class="note-form" id="comp-note-form">
          <select id="comp-note-type" class="search-select" style="max-width:200px;">
            <option value="note">Note</option><option value="call">Call</option><option value="email">Email</option><option value="meeting">Meeting</option>
          </select>
          <textarea id="comp-note-text" placeholder="Add an interaction log…" required></textarea>
          <div class="row"><button class="btn btn-primary btn-sm" type="submit">Add note</button></div>
        </form>
      </div>
    `;
    openDrawer('Company', c.company_name, html);
    document.getElementById('save-comp-btn').addEventListener('click', async () => {
      const status = document.getElementById('comp-status-select').value;
      await api('/api/admin/companies/' + id, { method: 'PATCH', body: JSON.stringify({ status }) });
      closeDrawer();
      loadCompanies();
    });
    document.getElementById('comp-note-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const note = document.getElementById('comp-note-text').value.trim();
      const interaction_type = document.getElementById('comp-note-type').value;
      if (!note) return;
      await api('/api/admin/notes', { method: 'POST', body: JSON.stringify({ entity_type: 'company', entity_id: id, note, interaction_type }) });
      openCompany(id);
    });
  }

  // ----- Matching -----
  async function openMatches(companyId) {
    try {
      const data = await api('/api/admin/companies/' + companyId + '/matches?limit=15');
      const { company, matches } = data;
      const matchesHtml = matches.length ? matches.map((m) => {
        const c = m.candidate;
        const tone = m.score >= 75 ? 'is-high' : m.score >= 50 ? 'is-mid' : 'is-low';
        const reasons = (m.reasons || []).slice(0, 3).map((r) => `<li>${escape(r)}</li>`).join('');
        return `
          <article class="match-card" data-testid="match-card-${c.id}">
            <header class="match-card-head">
              <div>
                <div class="match-name">${escape(c.full_name)}${c.is_shortlisted ? ' <span class="status-pill is-shortlisted">★</span>' : ''}</div>
                <div class="muted match-sub">${escape(c.preferred_role || '—')} · ${escape(c.experience || '—')} · ${escape(c.location || '—')}</div>
              </div>
              <div class="match-score ${tone}">
                <span class="match-score-value">${m.score}</span>
                <span class="match-score-label">match</span>
              </div>
            </header>
            <div class="match-bars">
              ${Object.entries(m.percentages).map(([k, v]) => `
                <div class="match-bar">
                  <span class="match-bar-label">${k}</span>
                  <span class="match-bar-track"><span class="match-bar-fill" style="width:${v}%"></span></span>
                  <span class="match-bar-pct">${v}%</span>
                </div>`).join('')}
            </div>
            ${reasons ? `<ul class="match-reasons">${reasons}</ul>` : ''}
            <footer class="match-actions">
              <button class="btn btn-ghost btn-sm" data-action="view-cand" data-id="${c.id}" data-testid="match-view-${c.id}">View profile</button>
              <button class="btn btn-primary btn-sm" data-action="shortlist" data-id="${c.id}" data-testid="match-shortlist-${c.id}">${c.is_shortlisted ? 'Already shortlisted' : 'Add to shortlist'}</button>
            </footer>
          </article>`;
      }).join('') : '<div class="empty">No candidates available to match yet.</div>';

      const html = `
        <div class="detail-block">
          <h4>Brief</h4>
          <div class="detail-grid">
            <div><label>Role</label><span>${escape(company.required_role)}</span></div>
            <div><label>Experience</label><span>${escape(company.experience_required || '—')}</span></div>
            <div><label>Budget</label><span>${escape(company.budget || '—')}</span></div>
            <div><label>Skills</label><span>${escape(company.skills_required || '—')}</span></div>
          </div>
        </div>
        <div class="detail-block">
          <h4>Top matches · ranked by match score</h4>
          <div class="match-list" id="match-list">${matchesHtml}</div>
        </div>
      `;
      openDrawer('Top matches', company.company_name, html);

      const list = document.getElementById('match-list');
      list.querySelectorAll('[data-action="view-cand"]').forEach((b) =>
        b.addEventListener('click', () => { closeDrawer(); setView('candidates'); setTimeout(() => openCandidate(b.dataset.id), 200); })
      );
      list.querySelectorAll('[data-action="shortlist"]').forEach((b) =>
        b.addEventListener('click', async () => {
          b.disabled = true;
          b.textContent = 'Shortlisting…';
          try {
            await api('/api/admin/candidates/' + b.dataset.id, { method: 'PATCH', body: JSON.stringify({ is_shortlisted: true, status: 'shortlisted' }) });
            b.textContent = 'Shortlisted ✓';
            b.classList.remove('btn-primary');
            b.classList.add('btn-ghost');
          } catch (e) { b.disabled = false; b.textContent = 'Add to shortlist'; alert(e.message); }
        })
      );
    } catch (e) {
      alert(e.message);
    }
  }

  // ----- Placements -----
  async function loadPlacements() {
    const rows = await api('/api/admin/placements');
    const tbody = document.getElementById('placements-tbody');
    const empty = document.getElementById('placements-empty');
    if (!rows.length) { tbody.innerHTML = ''; empty.classList.remove('hidden'); return; }
    empty.classList.add('hidden');
    tbody.innerHTML = rows.map((p) => `
      <tr>
        <td><div class="cell-primary">${escape(p.candidate_name)}</div></td>
        <td>${escape(p.company_name)}</td>
        <td>${escape(p.role || '—')}</td>
        <td>${fmtCurrency(p.fee)}</td>
        <td>${fmtDate(p.placed_at)}</td>
      </tr>
    `).join('');
  }

  document.getElementById('new-placement-btn').addEventListener('click', async () => {
    const cands = await api('/api/admin/candidates');
    const comps = await api('/api/admin/companies');
    openModal('Record placement', `
      <form class="modal-form" id="placement-form">
        <div class="field">
          <label>Candidate</label>
          <select id="p-cand" class="search-select" required>${cands.map(c => `<option value="${c.id}">${escape(c.full_name)} · ${escape(c.preferred_role||'')}</option>`).join('')}</select>
        </div>
        <div class="field">
          <label>Company</label>
          <select id="p-comp" class="search-select" required>${comps.map(c => `<option value="${c.id}">${escape(c.company_name)} · ${escape(c.required_role)}</option>`).join('')}</select>
        </div>
        <div class="field">
          <label>Role title</label>
          <input id="p-role" type="text" placeholder="Final role title" />
        </div>
        <div class="field">
          <label>Placement fee (₹)</label>
          <input id="p-fee" type="number" min="0" step="1000" placeholder="0" />
        </div>
        <div class="form-actions">
          <button type="button" class="btn btn-ghost btn-sm" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" data-testid="save-placement-btn">Record placement</button>
        </div>
      </form>
    `);
    modalBody.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', closeModal));
    document.getElementById('placement-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        candidate_id: document.getElementById('p-cand').value,
        company_id: document.getElementById('p-comp').value,
        role: document.getElementById('p-role').value.trim(),
        fee: parseFloat(document.getElementById('p-fee').value || 0),
      };
      await api('/api/admin/placements', { method: 'POST', body: JSON.stringify(payload) });
      closeModal();
      loadPlacements();
    });
  });

  // ----- Invoices -----
  async function loadInvoices() {
    const rows = await api('/api/admin/invoices');
    const tbody = document.getElementById('invoices-tbody');
    const empty = document.getElementById('invoices-empty');
    if (!rows.length) { tbody.innerHTML = ''; empty.classList.remove('hidden'); return; }
    empty.classList.add('hidden');
    tbody.innerHTML = rows.map((i) => `
      <tr data-testid="invoice-row-${i.id}">
        <td><span class="cell-primary">${escape(i.invoice_number)}</span></td>
        <td>${escape(i.company_name)}</td>
        <td>${escape(i.candidate_name || '—')}</td>
        <td>${fmtCurrency(i.total_amount)}</td>
        <td>${pill(i.status)}</td>
        <td>${fmtDate(i.created_at)}</td>
        <td class="row-actions">
          <button class="btn btn-ghost btn-sm" data-action="download" data-id="${i.id}" data-testid="invoice-download-${i.id}">PDF</button>
          ${i.status === 'pending' ? `<button class="btn btn-ghost btn-sm" data-action="mark-paid" data-id="${i.id}">Mark paid</button>` : ''}
        </td>
      </tr>
    `).join('');
    tbody.querySelectorAll('[data-action="download"]').forEach((b) =>
      b.addEventListener('click', () => downloadInvoice(b.dataset.id))
    );
    tbody.querySelectorAll('[data-action="mark-paid"]').forEach((b) =>
      b.addEventListener('click', async () => {
        await api('/api/admin/invoices/' + b.dataset.id, { method: 'PATCH', body: JSON.stringify({ status: 'paid' }) });
        loadInvoices();
      })
    );
  }

  async function downloadInvoice(id) {
    try {
      const res = await fetch('/api/admin/invoices/' + id + '/pdf', { headers: { Authorization: 'Bearer ' + localStorage.getItem('vh_token') } });
      if (!res.ok) throw new Error('Failed to download');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `invoice-${id}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { alert(e.message); }
  }

  document.getElementById('new-invoice-btn').addEventListener('click', async () => {
    const comps = await api('/api/admin/companies');
    openModal('Generate invoice', `
      <form class="modal-form" id="invoice-form">
        <div class="field field-wide">
          <label>Company</label>
          <select id="i-company" class="search-select" required>
            <option value="">— Select company —</option>
            ${comps.map(c => `<option value="${c.id}" data-name="${escape(c.company_name)}" data-email="${escape(c.email)}" data-role="${escape(c.required_role)}">${escape(c.company_name)} · ${escape(c.required_role)}</option>`).join('')}
          </select>
        </div>
        <div class="field">
          <label>Company name (override)</label>
          <input id="i-company-name" required />
        </div>
        <div class="field">
          <label>Company email</label>
          <input id="i-company-email" type="email" />
        </div>
        <div class="field field-wide">
          <label>Billing address</label>
          <textarea id="i-company-address" rows="2"></textarea>
        </div>
        <div class="field">
          <label>GSTIN (optional)</label>
          <input id="i-gstin" />
        </div>
        <div class="field">
          <label>Candidate name</label>
          <input id="i-candidate" />
        </div>
        <div class="field">
          <label>Role</label>
          <input id="i-role" />
        </div>
        <div class="field">
          <label>Placement date</label>
          <input id="i-pdate" type="date" />
        </div>
        <div class="field">
          <label>Placement fee (₹)</label>
          <input id="i-fee" type="number" min="0" step="1000" required />
        </div>
        <div class="field">
          <label>GST rate (%)</label>
          <input id="i-gst" type="number" min="0" max="100" step="0.5" value="18" />
        </div>
        <div class="field field-wide">
          <label>Notes</label>
          <textarea id="i-notes" rows="2"></textarea>
        </div>
        <div class="form-actions">
          <button type="button" class="btn btn-ghost btn-sm" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" data-testid="save-invoice-btn">Create invoice</button>
        </div>
      </form>
    `);
    modalBody.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', closeModal));

    const compSel = document.getElementById('i-company');
    compSel.addEventListener('change', () => {
      const opt = compSel.options[compSel.selectedIndex];
      if (!opt || !opt.value) return;
      document.getElementById('i-company-name').value = opt.dataset.name || '';
      document.getElementById('i-company-email').value = opt.dataset.email || '';
      document.getElementById('i-role').value = opt.dataset.role || '';
    });

    document.getElementById('invoice-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        company_id: compSel.value || null,
        company_name: document.getElementById('i-company-name').value.trim(),
        company_email: document.getElementById('i-company-email').value.trim(),
        company_address: document.getElementById('i-company-address').value.trim(),
        company_gstin: document.getElementById('i-gstin').value.trim(),
        candidate_name: document.getElementById('i-candidate').value.trim(),
        role: document.getElementById('i-role').value.trim(),
        placement_date: document.getElementById('i-pdate').value,
        placement_fee: parseFloat(document.getElementById('i-fee').value || 0),
        gst_rate: parseFloat(document.getElementById('i-gst').value || 18),
        notes: document.getElementById('i-notes').value.trim(),
      };
      await api('/api/admin/invoices', { method: 'POST', body: JSON.stringify(payload) });
      closeModal();
      loadInvoices();
    });
  });

  // ----- Messages -----
  async function loadMessages() {
    const rows = await api('/api/admin/contact_messages');
    const tbody = document.getElementById('messages-tbody');
    const empty = document.getElementById('messages-empty');
    if (!rows.length) { tbody.innerHTML = ''; empty.classList.remove('hidden'); return; }
    empty.classList.add('hidden');
    tbody.innerHTML = rows.map((m) => `
      <tr>
        <td><div class="cell-primary">${escape(m.name)}</div></td>
        <td><a href="mailto:${escape(m.email)}">${escape(m.email)}</a></td>
        <td>${escape(m.subject || '—')}</td>
        <td class="cell-muted" style="max-width:380px;">${escape(m.message)}</td>
        <td>${fmtDate(m.created_at)}</td>
      </tr>
    `).join('');
  }

  // initial load
  setView('overview');
})();
