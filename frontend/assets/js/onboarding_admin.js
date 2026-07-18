// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «آنبوردینگ» (برنامه‌های آشنایی سازمانی) — Admin
// ════════════════════════════════════════════════════════════════════
// org_admin/super_admin: CRUD برنامه + مراحل + پیگیری/ثبت‌نام دستی کارکنان.
// همیشه محدود به سازمان خودشان (بک‌اند enforce می‌کند).
//
// فرم برنامه یک ویزارد ۲ تبی است (مشابه content.js):
//   تب ۱ «مشخصات و هدف‌گذاری» → نام/توضیح/نقش‌ها/واحد/پیش‌فرض/مهلت (سازنده‌ی رکورد برنامه)
//   تب ۲ «مراحل»              → چک‌لیست واقعی (محتوا/آزمون/آپلود مدرک/آزاد)
// در «ساخت جدید» تب‌ها به‌ترتیب باز می‌شوند چون افزودن مرحله به program_id
// واقعی نیاز دارد که فقط بعد از تب ۱ ساخته می‌شود.

const STEP_TYPE_LABELS = { content: 'محتوا', quiz: 'آزمون', document_upload: 'آپلود مدرک', custom: 'آزاد (بدون اکشن)' };
const ROLE_LABELS_FA = { employee: 'کارمند', manager: 'مدیر', org_admin: 'ادمین سازمان', super_admin: 'سوپر ادمین' };
const OB_TAB_ORDER = ['basic', 'steps'];

const OnboardingPage = (() => {
  const state = {
    page: 1, search: '', items: [], total: 0, totalPages: 1,
    mode: null, programId: null, activeTab: 'basic', maxUnlockedTab: 'basic',
    activeSteps: [],
    orgs: [], orgsLoaded: false, targetOrgId: null, depts: [],
    contentsForSelect: [], quizzesForSelect: [],
    // ثبت‌نام دستی
    enrollProgramId: null, enrollSearchTimer: null, enrollResults: [], enrollSelected: new Map(),
  };
  let searchTimer = null;

  function typeBadge(t) {
    return `<span class="badge badge-type-${t === 'custom' ? 'article' : t === 'quiz' ? 'course' : 'book'}">${STEP_TYPE_LABELS[t] || t}</span>`;
  }

  // ─── List ───────────────────────────────────────────────────────
  async function load(page = state.page) {
    state.page = page;
    if (App.isSuperAdmin) await loadOrgFilterOptions();
    const tbody = document.getElementById('obTableBody');
    tbody.innerHTML = `<tr><td colspan="7" class="loading-row">در حال بارگذاری...</td></tr>`;
    const orgFilter = document.getElementById('obOrgFilter')?.value || '';
    const p = new URLSearchParams({ page, page_size: 20 });
    if (state.search) p.set('search', state.search);
    if (App.isSuperAdmin && orgFilter) p.set('org_id', orgFilter);
    try {
      const res = await api.get(`/onboarding/programs?${p}`);
      state.items = res.items || [];
      setText('obTotalLabel', `${numFa(res.total)} برنامه`);
      if (!state.items.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--gray-400);">هنوز برنامه‌ی آشنایی‌ای ثبت نشده</td></tr>`;
        document.getElementById('obPagination').innerHTML = '';
        return;
      }
      tbody.innerHTML = state.items.map(p => `
        <tr>
          <td style="font-weight:600;">${esc(p.name)}${p.is_default ? ' <span class="badge badge-admin">پیش‌فرض</span>' : ''}</td>
          ${App.isSuperAdmin ? `<td class="th-org">${esc(p.org_name || '—')}</td>` : ''}
          <td>${targetSummary(p)}</td>
          <td>${numFa(p.step_count)} مرحله</td>
          <td>${numFa(p.enrollment_count)} نفر</td>
          <td>${statusBadge(p.is_active)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="edit-program" data-id="${p.id}">ویرایش</button>
              <button class="btn-action" style="background:#EFF6FF;color:#2563EB;" data-role="open-enrollments" data-id="${p.id}">پیگیری</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-program" data-id="${p.id}" data-title="${esc(p.name)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
      renderPagination('obPagination', res.page, res.total_pages, load);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function targetSummary(p) {
    const parts = [];
    if (p.target_roles && p.target_roles.length) parts.push(p.target_roles.map(r => ROLE_LABELS_FA[r] || r).join('، '));
    if (p.target_dept_name) parts.push(esc(p.target_dept_name));
    return parts.length ? parts.join(' · ') : '<span style="color:var(--gray-400);">کل سازمان</span>';
  }

  function searchDebounced() {
    state.search = document.getElementById('obSearch').value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load(1), 400);
  }

  async function loadOrgFilterOptions() {
    const sel = document.getElementById('obOrgFilter');
    if (!sel || sel.dataset.loaded) return;
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">همه سازمان‌ها</option>' +
        orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
      sel.dataset.loaded = '1';
    } catch { /* غیرحیاتی — فقط فیلتر است */ }
  }

  // ─── Wizard: تب‌ها ───────────────────────────────────────────────
  function switchTab(tab) {
    if (state.mode === 'create') {
      const targetIdx = OB_TAB_ORDER.indexOf(tab);
      const maxIdx = OB_TAB_ORDER.indexOf(state.maxUnlockedTab);
      if (targetIdx > maxIdx) return;
    }
    state.activeTab = tab;
    document.querySelectorAll('#obModalTabs .tab-btn').forEach(b => b.classList.toggle('active', b.dataset.obtab === tab));
    document.querySelectorAll('.obtab-content').forEach(el => el.classList.toggle('active', el.id === 'obtab-' + tab));
    updateFooterButtons();
  }

  function setTabsUnlocked(maxTab) {
    state.maxUnlockedTab = maxTab;
    const maxIdx = OB_TAB_ORDER.indexOf(maxTab);
    document.querySelectorAll('#obModalTabs .tab-btn').forEach(b => {
      b.disabled = state.mode === 'create' && OB_TAB_ORDER.indexOf(b.dataset.obtab) > maxIdx;
    });
  }

  function updateFooterButtons() {
    const next = document.getElementById('btn-ob-next');
    const save = document.getElementById('btn-ob-save');
    const finish = document.getElementById('btn-ob-finish');
    if (state.mode === 'edit') {
      next.classList.add('hidden'); finish.classList.add('hidden'); save.classList.remove('hidden');
      return;
    }
    save.classList.add('hidden');
    const idx = OB_TAB_ORDER.indexOf(state.activeTab);
    next.classList.toggle('hidden', idx === OB_TAB_ORDER.length - 1);
    finish.classList.toggle('hidden', idx !== OB_TAB_ORDER.length - 1);
  }

  async function nextTab() {
    if (state.activeTab !== 'basic') return;
    const name = document.getElementById('ob-name').value.trim();
    if (!name) { toastError('نام برنامه اجباری است'); return; }
    let orgId = null;
    if (App.isSuperAdmin) {
      orgId = document.getElementById('ob-org-id').value;
      if (!orgId) { toastError('لطفاً سازمان را انتخاب کنید'); return; }
    }
    const btn = document.getElementById('btn-ob-next');
    setLoading(btn, true);
    try {
      const payload = basicPayload();
      if (orgId) payload.org_id = orgId;
      const created = await api.post('/onboarding/programs', payload);
      state.programId = created.id;
      document.getElementById('ob-id').value = created.id;
      if (App.isSuperAdmin) document.getElementById('ob-org-id').disabled = true;
      toastSuccess('مشخصات ذخیره شد — حالا مراحل را اضافه کنید');
      await loadContentsAndQuizzesForSelect(created.org_id);
      state.activeSteps = created.steps || [];
      renderSteps();
      setTabsUnlocked('steps');
      switchTab('steps');
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  async function finishWizard() { closeModal('modal-onboarding'); await load(1); }

  function closeOnboardingModal() {
    const wasCreatingDraft = state.mode === 'create' && state.programId;
    closeModal('modal-onboarding');
    if (wasCreatingDraft) load(1); // برنامه از تب ۱ به بعد از قبل روی سرور ساخته شده
  }

  function parseRolesInput() {
    return Array.from(document.querySelectorAll('#ob-role-checks input:checked')).map(cb => cb.value);
  }

  function basicPayload() {
    return {
      name: document.getElementById('ob-name').value.trim(),
      description: document.getElementById('ob-desc').value.trim() || null,
      target_roles: parseRolesInput(),
      target_dept_id: document.getElementById('ob-dept-id').value || null,
      is_default: document.getElementById('ob-is-default').checked,
      deadline_days: document.getElementById('ob-deadline').value ? parseInt(document.getElementById('ob-deadline').value, 10) : null,
      is_active: true,
    };
  }

  function collectEditablePayload() {
    const p = basicPayload();
    p.is_active = document.getElementById('ob-is-active').checked;
    return p;
  }

  // ─── Create / Edit ──────────────────────────────────────────────
  async function openCreate() {
    state.mode = 'create'; state.programId = null; state.activeSteps = [];
    document.getElementById('obModalTitle').textContent = 'برنامه‌ی آشنایی جدید';
    document.getElementById('ob-id').value = '';
    ['ob-name', 'ob-desc'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('ob-deadline').value = '';
    document.getElementById('ob-is-default').checked = false;
    document.getElementById('ob-is-active-wrap').classList.add('hidden');
    document.querySelectorAll('#ob-role-checks input').forEach(cb => cb.checked = false);
    document.getElementById('ob-dept-id').innerHTML = '<option value="">— همه واحدها —</option>';
    state.activeSteps = [];
    renderSteps();
    setTabsUnlocked('basic');
    switchTab('basic');

    if (App.isSuperAdmin) {
      document.getElementById('ob-org-id').disabled = false;
      await loadOrgsForSelect('');
    } else {
      await loadDeptsForSelect(App.currentUser.org_id);
    }
    openModal('modal-onboarding');
  }

  async function openEdit(id) {
    let detail;
    try { detail = await api.get(`/onboarding/programs/${id}`); } catch (e) { toastError(e.message); return; }
    state.mode = 'edit'; state.programId = detail.id; state.activeSteps = detail.steps || [];

    document.getElementById('obModalTitle').textContent = 'ویرایش برنامه';
    document.getElementById('ob-id').value = detail.id;
    document.getElementById('ob-name').value = detail.name || '';
    document.getElementById('ob-desc').value = detail.description || '';
    document.getElementById('ob-deadline').value = detail.deadline_days ?? '';
    document.getElementById('ob-is-default').checked = !!detail.is_default;
    document.getElementById('ob-is-active').checked = !!detail.is_active;
    document.getElementById('ob-is-active-wrap').classList.remove('hidden');
    document.querySelectorAll('#ob-role-checks input').forEach(cb => {
      cb.checked = (detail.target_roles || []).includes(cb.value);
    });

    if (App.isSuperAdmin) {
      document.getElementById('ob-org-id').disabled = true;
      await loadOrgsForSelect(detail.org_id);
    }
    await loadDeptsForSelect(detail.org_id, detail.target_dept_id);
    await loadContentsAndQuizzesForSelect(detail.org_id);

    setTabsUnlocked('steps');
    renderSteps();
    switchTab('basic');
    openModal('modal-onboarding');
  }

  async function save() {
    const btn = document.getElementById('btn-ob-save');
    setLoading(btn, true);
    try {
      await api.patch(`/onboarding/programs/${state.programId}`, collectEditablePayload());
      toastSuccess('برنامه با موفقیت ویرایش شد');
      closeModal('modal-onboarding');
      await load(state.page);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function remove(id, name) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید برنامه‌ی "${name}" را حذف کنید؟ همه‌ی ثبت‌نام‌ها و پیشرفت کارکنان روی آن نیز حذف می‌شود.`, async () => {
      await api.delete(`/onboarding/programs/${id}`);
      toastSuccess('برنامه با موفقیت حذف شد');
      await load(1);
    });
  }

  async function loadOrgsForSelect(selectedId) {
    const sel = document.getElementById('ob-org-id');
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">— انتخاب سازمان —</option>' +
        orgs.map(o => `<option value="${o.id}" ${o.id === selectedId ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
    } catch { /* ignore */ }
  }

  async function loadDeptsForSelect(orgId, selectedId) {
    const sel = document.getElementById('ob-dept-id');
    if (!orgId) { sel.innerHTML = '<option value="">— همه واحدها —</option>'; return; }
    try {
      state.depts = await api.get(`/departments/?org_id=${orgId}`) || [];
      sel.innerHTML = '<option value="">— همه واحدها —</option>' +
        state.depts.map(d => `<option value="${d.id}" ${d.id === selectedId ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
    } catch { sel.innerHTML = '<option value="">— همه واحدها —</option>'; }
  }

  async function onOrgChange() {
    const orgId = document.getElementById('ob-org-id').value;
    await loadDeptsForSelect(orgId);
  }

  // ─── تب ۲: مراحل ────────────────────────────────────────────────
  async function loadContentsAndQuizzesForSelect(orgId) {
    try {
      const [contentsRes, quizzesRes] = await Promise.all([
        api.get(`/contents/?org_id=${orgId}&status=published&page_size=100`),
        api.get(`/quizzes/?org_id=${orgId}&page_size=100`),
      ]);
      state.contentsForSelect = contentsRes.items || [];
      state.quizzesForSelect = quizzesRes.items || [];
    } catch { state.contentsForSelect = []; state.quizzesForSelect = []; }
  }

  function renderSteps() {
    const wrap = document.getElementById('obStepsList');
    if (!state.activeSteps.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📭</div>هنوز مرحله‌ای اضافه نشده</div>`;
      return;
    }
    const sorted = [...state.activeSteps].sort((a, b) => a.order_index - b.order_index);
    wrap.innerHTML = sorted.map((s, idx) => `
      <div class="item-row">
        <div class="item-row-order">${numFa(idx + 1)}</div>
        <div class="item-row-icon">${s.type === 'content' ? '📚' : s.type === 'quiz' ? '📝' : s.type === 'document_upload' ? '📎' : '✅'}</div>
        <div class="item-row-info">
          <div class="item-row-title">${esc(s.title)}${s.is_required ? '' : ' <span class="badge badge-manager">اختیاری</span>'}</div>
          <div class="item-row-meta">${STEP_TYPE_LABELS[s.type] || s.type}${s.content_title ? ' — ' + esc(s.content_title) : ''}${s.quiz_title ? ' — ' + esc(s.quiz_title) : ''}</div>
        </div>
        <div class="item-row-actions">
          <button class="btn-icon" title="ویرایش" data-role="edit-step" data-id="${s.id}">✎</button>
          <button class="btn-icon" title="حذف" data-role="delete-step" data-id="${s.id}" data-title="${esc(s.title)}">🗑</button>
        </div>
      </div>`).join('');
  }

  function stepTypeSelectOptions(selected) {
    return Object.entries(STEP_TYPE_LABELS).map(([v, l]) =>
      `<option value="${v}" ${v === selected ? 'selected' : ''}>${l}</option>`).join('');
  }

  function refreshStepConditionalFields() {
    const type = document.getElementById('obs-type').value;
    document.getElementById('obs-content-wrap').classList.toggle('hidden', type !== 'content');
    document.getElementById('obs-quiz-wrap').classList.toggle('hidden', type !== 'quiz');
    if (type === 'content' && !document.getElementById('obs-content-id').dataset.loaded) {
      document.getElementById('obs-content-id').innerHTML = '<option value="">— انتخاب محتوا —</option>' +
        state.contentsForSelect.map(c => `<option value="${c.id}">${esc(c.title)}</option>`).join('');
      document.getElementById('obs-content-id').dataset.loaded = '1';
    }
    if (type === 'quiz' && !document.getElementById('obs-quiz-id').dataset.loaded) {
      document.getElementById('obs-quiz-id').innerHTML = '<option value="">— انتخاب آزمون —</option>' +
        state.quizzesForSelect.map(q => `<option value="${q.id}">${esc(q.title)}</option>`).join('');
      document.getElementById('obs-quiz-id').dataset.loaded = '1';
    }
  }

  function openCreateStep() {
    document.getElementById('obStepModalTitle').textContent = 'مرحله‌ی جدید';
    document.getElementById('obs-id').value = '';
    document.getElementById('obs-title').value = '';
    document.getElementById('obs-desc').value = '';
    document.getElementById('obs-type').value = 'custom';
    document.getElementById('obs-required').checked = true;
    document.getElementById('obs-content-id').dataset.loaded = '';
    document.getElementById('obs-quiz-id').dataset.loaded = '';
    refreshStepConditionalFields();
    openModal('modal-onboarding-step');
  }

  function openEditStep(id) {
    const s = state.activeSteps.find(x => x.id === id);
    if (!s) return;
    document.getElementById('obStepModalTitle').textContent = 'ویرایش مرحله';
    document.getElementById('obs-id').value = s.id;
    document.getElementById('obs-title').value = s.title || '';
    document.getElementById('obs-desc').value = s.description || '';
    document.getElementById('obs-type').value = s.type;
    document.getElementById('obs-required').checked = !!s.is_required;
    document.getElementById('obs-content-id').dataset.loaded = '';
    document.getElementById('obs-quiz-id').dataset.loaded = '';
    refreshStepConditionalFields();
    if (s.content_id) document.getElementById('obs-content-id').value = s.content_id;
    if (s.quiz_id) document.getElementById('obs-quiz-id').value = s.quiz_id;
    openModal('modal-onboarding-step');
  }

  async function saveStep() {
    const id = document.getElementById('obs-id').value;
    const title = document.getElementById('obs-title').value.trim();
    const type = document.getElementById('obs-type').value;
    if (!title) { toastError('عنوان مرحله اجباری است'); return; }
    const payload = {
      title,
      description: document.getElementById('obs-desc').value.trim() || null,
      type,
      content_id: type === 'content' ? (document.getElementById('obs-content-id').value || null) : null,
      quiz_id: type === 'quiz' ? (document.getElementById('obs-quiz-id').value || null) : null,
      is_required: document.getElementById('obs-required').checked,
    };
    const btn = document.getElementById('btn-obs-save');
    setLoading(btn, true);
    try {
      if (id) await api.patch(`/onboarding/steps/${id}`, payload);
      else await api.post(`/onboarding/programs/${state.programId}/steps`, payload);
      toastSuccess('مرحله با موفقیت ذخیره شد');
      closeModal('modal-onboarding-step');
      const detail = await api.get(`/onboarding/programs/${state.programId}`);
      state.activeSteps = detail.steps || [];
      renderSteps();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeStep(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید مرحله‌ی "${title}" را حذف کنید؟`, async () => {
      await api.delete(`/onboarding/steps/${id}`);
      toastSuccess('مرحله حذف شد');
      const detail = await api.get(`/onboarding/programs/${state.programId}`);
      state.activeSteps = detail.steps || [];
      renderSteps();
    });
  }

  // ─── پیگیری + ثبت‌نام دستی ──────────────────────────────────────
  async function openEnrollments(programId) {
    state.enrollProgramId = programId;
    state.enrollSelected = new Map();
    document.getElementById('obEnrollUserSearch').value = '';
    document.getElementById('obEnrollUserResults').innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>';
    renderEnrollChips();
    await loadEnrollments();
    openModal('modal-onboarding-enrollments');
  }

  async function loadEnrollments() {
    const tbody = document.getElementById('obEnrollTableBody');
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const res = await api.get(`/onboarding/programs/${state.enrollProgramId}/enrollments?page_size=100`);
      const items = res.items || [];
      setText('obEnrollTotalLabel', `${numFa(res.total)} نفر ثبت‌نام‌شده`);
      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--gray-400);">هنوز کسی ثبت‌نام نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = items.map(e => `
        <tr>
          <td style="font-weight:500;">${esc(e.user_name || '—')}</td>
          <td style="direction:ltr;text-align:right;color:var(--gray-500);">${esc(e.user_email || '—')}</td>
          <td>
            <div class="progress-track" style="width:100px;display:inline-block;vertical-align:middle;"><div class="progress-fill${e.progress_pct >= 100 ? ' done' : ''}" style="width:${e.progress_pct}%;"></div></div>
            <span style="font-size:12px;color:var(--gray-500);margin-right:6px;">${numFa(e.progress_pct)}٪ (${numFa(e.steps_completed)}/${numFa(e.steps_total)})</span>
          </td>
          <td style="color:var(--gray-500);">${e.deadline_at ? fmtDate(e.deadline_at) : '—'}</td>
          <td>${e.completed_at ? '<span class="badge badge-active">تکمیل‌شده</span>' : '<span class="badge badge-manager">در حال انجام</span>'}</td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function enrollSearchDebounced() {
    clearTimeout(state.enrollSearchTimer);
    state.enrollSearchTimer = setTimeout(runEnrollUserSearch, 350);
  }

  async function runEnrollUserSearch() {
    const box = document.getElementById('obEnrollUserResults');
    const q = document.getElementById('obEnrollUserSearch').value.trim();
    if (!q) { box.innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>'; return; }
    const program = state.items.find(p => p.id === state.enrollProgramId);
    const orgId = program ? program.org_id : App.currentUser.org_id;
    box.innerHTML = '<div class="checkbox-scroll-box-empty">در حال جستجو...</div>';
    try {
      const res = await api.get(`/users/?org_id=${orgId}&search=${encodeURIComponent(q)}&per_page=20`);
      const results = res.items || [];
      box.innerHTML = !results.length
        ? '<div class="checkbox-scroll-box-empty">کاربری یافت نشد</div>'
        : results.map(u => `
          <label class="checkbox-row">
            <input type="checkbox" ${state.enrollSelected.has(u.id) ? 'checked' : ''} data-role="toggle-enroll-user" data-id="${u.id}" data-label="${esc(`${u.full_name} (${u.email})`)}">
            ${esc(u.full_name)}
            <span class="checkbox-row-meta">${esc(u.email)}</span>
          </label>`).join('');
    } catch { box.innerHTML = '<div class="checkbox-scroll-box-empty">خطا در جستجو</div>'; }
  }

  function renderEnrollChips() {
    const box = document.getElementById('obEnrollSelected');
    if (!state.enrollSelected.size) { box.innerHTML = ''; return; }
    box.innerHTML = Array.from(state.enrollSelected.entries()).map(([id, label]) => `
      <span class="chip">${esc(label)}<span class="chip-remove" data-role="remove-enroll-chip" data-id="${id}">✕</span></span>`).join('');
  }

  async function submitManualEnroll() {
    if (!state.enrollSelected.size) { toastError('حداقل یک کاربر انتخاب کنید'); return; }
    const btn = document.getElementById('btn-ob-manual-enroll');
    setLoading(btn, true);
    try {
      await api.post(`/onboarding/programs/${state.enrollProgramId}/enroll`, {
        user_ids: Array.from(state.enrollSelected.keys()),
      });
      toastSuccess('ثبت‌نام با موفقیت انجام شد');
      state.enrollSelected = new Map();
      renderEnrollChips();
      document.getElementById('obEnrollUserSearch').value = '';
      document.getElementById('obEnrollUserResults').innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>';
      await loadEnrollments();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row/Checkbox Actions — به‌جای onclick اینلاین با متن کاربر ──
  document.getElementById('obTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role]');
    if (!btn) return;
    const { role, id, title } = btn.dataset;
    if (role === 'edit-program') openEdit(id);
    else if (role === 'open-enrollments') openEnrollments(id);
    else if (role === 'delete-program') remove(id, title);
  });
  document.getElementById('obStepsList')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role]');
    if (!btn) return;
    const { role, id, title } = btn.dataset;
    if (role === 'edit-step') openEditStep(id);
    else if (role === 'delete-step') removeStep(id, title);
  });
  document.getElementById('obEnrollUserResults')?.addEventListener('change', (e) => {
    const input = e.target.closest('[data-role="toggle-enroll-user"]');
    if (!input) return;
    if (input.checked) state.enrollSelected.set(input.dataset.id, input.dataset.label);
    else state.enrollSelected.delete(input.dataset.id);
    renderEnrollChips();
  });
  document.getElementById('obEnrollSelected')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="remove-enroll-chip"]');
    if (!btn) return;
    state.enrollSelected.delete(btn.dataset.id);
    renderEnrollChips();
  });

  return {
    load, searchDebounced, switchTab, nextTab, finishWizard, closeOnboardingModal,
    openCreate, openEdit, save, remove, onOrgChange,
    openCreateStep, openEditStep, saveStep, removeStep, refreshStepConditionalFields,
    openEnrollments, enrollSearchDebounced, submitManualEnroll,
  };
})();
