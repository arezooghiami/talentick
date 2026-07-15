// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «سازمان» کارمند: معرفی سازمان + چارت سازمانی + کتابخانه اسناد
// ════════════════════════════════════════════════════════════════════

const OrganizationPage = (() => {
  const state = {
    chartLoaded: false,
    docCategories: [],
    docCategoryId: '',
    docSearch: '',
    docPage: 1,
    docSearchTimer: null,
  };

  async function load() {
    await loadIntro();
    await loadDocCategories();
    await loadDocs(1);
  }

  // ─── تب‌ها ───────────────────────────────────────────────────────
  function switchTab(name) {
    document.querySelectorAll('.org-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.orgTab === name));
    document.querySelectorAll('.org-tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('orgTab' + name.charAt(0).toUpperCase() + name.slice(1)).classList.add('active');
    if (name === 'chart' && !state.chartLoaded) loadChart();
  }

  // ─── درباره سازمان ──────────────────────────────────────────────
  async function loadIntro() {
    try {
      const org = await api.get('/me/org');
      document.getElementById('introName').textContent = org.name || '—';
      document.getElementById('introDesc').textContent = org.description || '';
      const logoEl = document.getElementById('introLogo');
      if (org.logo_url) logoEl.innerHTML = `<img src="${esc(org.logo_url)}" alt="${esc(org.name || '')}">`;

      const cards = [
        { key: 'history', icon: '📜', title: 'تاریخچه' },
        { key: 'mission', icon: '🎯', title: 'ماموریت' },
        { key: 'vision', icon: '🔭', title: 'چشم‌انداز' },
        { key: 'values', icon: '💎', title: 'ارزش‌ها' },
      ].filter(c => org[c.key]);

      const grid = document.getElementById('introGrid');
      grid.innerHTML = cards.length
        ? cards.map(c => `
            <div class="org-intro-card">
              <div class="org-intro-card-icon">${c.icon}</div>
              <div class="org-intro-card-title">${c.title}</div>
              <div class="org-intro-card-text">${esc(org[c.key])}</div>
            </div>`).join('')
        : `<div class="org-empty-hint">هنوز محتوایی برای معرفی سازمان ثبت نشده است.</div>`;

      const contactItems = [
        org.website ? { icon: '🌐', label: org.website } : null,
        org.phone ? { icon: '📞', label: org.phone } : null,
        org.address ? { icon: '📍', label: org.address } : null,
        org.employee_count ? { icon: '👥', label: `${numFa(org.employee_count)} نفر` } : null,
      ].filter(Boolean);
      document.getElementById('introContact').innerHTML = contactItems
        .map(i => `<div class="org-intro-contact-item"><span>${i.icon}</span><span>${esc(i.label)}</span></div>`).join('');
    } catch (e) {
      toastError(e.message);
    }
  }

  // ─── چارت سازمانی ───────────────────────────────────────────────
  async function loadChart() {
    const wrap = document.getElementById('orgChartWrap');
    wrap.innerHTML = `<div class="org-chart-loading">در حال بارگذاری...</div>`;
    try {
      const tree = await api.get('/me/org-chart');
      state.chartLoaded = true;
      wrap.innerHTML = tree && tree.length
        ? `<div class="org-chart-tree">${renderChartNodes(tree)}</div>`
        : `<div class="org-empty-hint">هنوز واحد سازمانی ثبت نشده است.</div>`;
    } catch (e) {
      wrap.innerHTML = `<div class="org-empty-hint" style="color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</div>`;
    }
  }

  function renderChartNodes(nodes) {
    return `<ul class="org-chart-level">` + nodes.map(n => `
      <li class="org-chart-node">
        <div class="org-chart-box${n.is_active ? '' : ' inactive'}">
          <div class="org-chart-box-name">${esc(n.name)}</div>
          ${n.manager_name ? `<div class="org-chart-box-manager">👤 ${esc(n.manager_name)}</div>` : ''}
          <div class="org-chart-box-count">${numFa(n.user_count)} نفر</div>
        </div>
        ${n.children && n.children.length ? renderChartNodes(n.children) : ''}
      </li>
    `).join('') + `</ul>`;
  }

  // ─── کتابخانه اسناد ─────────────────────────────────────────────
  async function loadDocCategories() {
    try {
      state.docCategories = await api.get('/me/documents/categories') || [];
      const wrap = document.getElementById('docLibCategoryPills');
      wrap.innerHTML = `<button class="emp-filter-pill active" onclick="OrganizationPage.setDocCategory('', this)">همه</button>` +
        state.docCategories.map(c =>
          `<button class="emp-filter-pill" onclick="OrganizationPage.setDocCategory('${c.id}', this)">${esc(c.name)}</button>`
        ).join('');
    } catch (e) { /* غیرحیاتی — فقط فیلتر دسته‌بندی نمایش داده نمی‌شود */ }
  }

  function setDocCategory(id, btn) {
    state.docCategoryId = id;
    document.querySelectorAll('#docLibCategoryPills .emp-filter-pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadDocs(1);
  }

  function docSearchDebounced() {
    clearTimeout(state.docSearchTimer);
    state.docSearchTimer = setTimeout(() => {
      state.docSearch = document.getElementById('docLibSearch').value.trim();
      loadDocs(1);
    }, 350);
  }

  const FILE_ICONS = { pdf: '📕', doc: '📘', docx: '📘', ppt: '📙', pptx: '📙', xls: '📗', xlsx: '📗' };

  function fmtSize(bytes) {
    if (!bytes) return '';
    const kb = bytes / 1024;
    if (kb < 1024) return `${Math.round(kb)} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  }

  async function loadDocs(page = 1) {
    state.docPage = page;
    const list = document.getElementById('docLibList');
    list.innerHTML = `<div class="org-chart-loading">در حال بارگذاری...</div>`;
    const p = new URLSearchParams({ page, page_size: 20 });
    if (state.docSearch) p.set('search', state.docSearch);
    if (state.docCategoryId) p.set('category_id', state.docCategoryId);
    try {
      const res = await api.get(`/me/documents?${p}`);
      if (!res.items.length) {
        list.innerHTML = `<div class="org-empty-hint">سندی یافت نشد.</div>`;
        document.getElementById('docLibPagination').innerHTML = '';
        return;
      }
      list.innerHTML = res.items.map(d => `
        <a class="doc-lib-item" href="${esc(d.file_url)}" target="_blank" rel="noopener">
          <div class="doc-lib-icon">${FILE_ICONS[(d.file_type || '').toLowerCase()] || '📄'}</div>
          <div class="doc-lib-body">
            <div class="doc-lib-title">${esc(d.title)}</div>
            ${d.description ? `<div class="doc-lib-desc">${esc(d.description)}</div>` : ''}
            <div class="doc-lib-meta">
              ${d.category_name ? `<span>${esc(d.category_name)}</span>` : ''}
              ${d.file_size ? `<span>${fmtSize(d.file_size)}</span>` : ''}
              <span>${fmtDate(d.created_at)}</span>
            </div>
          </div>
          <div class="doc-lib-download">⬇️</div>
        </a>`).join('');
      renderPagination('docLibPagination', res.page, res.total_pages, loadDocs);
    } catch (e) {
      list.innerHTML = `<div class="org-empty-hint" style="color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</div>`;
    }
  }

  return { load, switchTab, setDocCategory, docSearchDebounced };
})();
