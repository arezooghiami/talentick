// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «ورود کارمند جدید» (Employee Onboarding) — Admin
// ════════════════════════════════════════════════════════════════════
// مستقل از OnboardingPage («مسیرهای یادگیری») از دید ادمین — اما هر دو
// روی همان API مشترک (/api/onboarding/programs) کار می‌کنند، فقط با
// purpose=employee_onboarding به‌جای purpose=learning. تفکیک کامل UI:
// نویگیشن/View/Modal جدا، فقط زیرساخت داده مشترک است.
//
// این صفحه سه تب دارد:
//   ۱) مسیرها          — CRUD کامل OnboardingProgram+ProgramStep (purpose=employee_onboarding)
//   ۲) کاتالوگ مدارک    — EmployeeDocumentType (مستقل از هر مسیر خاص)
//   ۳) پیشرفت کارکنان   — Monitoring (چه کسانی ثبت‌نام‌اند + وضعیت مدارک)
//
// انتساب کارمند به یک مسیر از فرم «کاربر جدید» در users.js انجام می‌شود
// (نه اینجا) — طبق تصمیم محصول: انتخاب صریح ادمین، بدون قدم دوم.
//
// دسترسی: فقط super_admin/org_admin (بک‌اند enforce می‌کند).

const EO_STEP_TYPE_LABELS = { content: 'محتوا', quiz: 'آزمون', document_upload: 'آپلود مدارک', custom: 'آزاد (بدون اکشن)' };
const EO_INPUT_TYPE_LABELS = { file: 'آپلود فایل', text: 'مقدار متنی' };
const EO_DOC_STATUS_LABELS = {
  not_uploaded: '<span class="badge badge-inactive">آپلود نشده</span>',
  uploaded: '<span class="badge badge-manager">ثبت‌شده</span>',
  approved: '<span class="badge badge-active">تأییدشده</span>',
  under_review: '<span class="badge badge-manager">در حال بررسی</span>',
  rejected: '<span class="badge" style="background:#FEF2F2;color:#DC2626;">رد‌شده</span>',
};
const EOP_TAB_ORDER = ['basic', 'steps'];

const EmployeeOnboardingPage = (() => {
  const state = {
    orgId: null,
    // مسیرها
    progPage: 1, progSearch: '', progSearchTimer: null, progItems: [],
    progMode: null, programId: null, activeProgTab: 'basic', maxUnlockedProgTab: 'basic',
    activeSteps: [], contentsForSelect: [], quizzesForSelect: [],
    // کاتالوگ مدارک
    docTypes: [],
    // Monitoring
    monPage: 1, monSearch: '', monSearchTimer: null, monItems: [],
  };

  // ─── راه‌اندازی + انتخاب سازمان (فقط super_admin) ──────────────
  async function init() {
    if (App.isSuperAdmin) {
      await loadOrgOptions();
      state.orgId = document.getElementById('eoOrgFilter').value || null;
    } else {
      state.orgId = App.currentUser.org_id;
    }
    if (state.orgId) await loadAll();
    else renderNoOrgSelected();
  }

  async function loadOrgOptions() {
    const sel = document.getElementById('eoOrgFilter');
    if (sel.dataset.loaded) return;
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">— انتخاب سازمان —</option>' +
        orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
      sel.dataset.loaded = '1';
    } catch { /* ignore */ }
  }

  async function onOrgChange() {
    state.orgId = document.getElementById('eoOrgFilter').value || null;
    if (state.orgId) await loadAll();
    else renderNoOrgSelected();
  }

  function renderNoOrgSelected() {
    document.getElementById('eoProgTableBody').innerHTML = '<tr><td colspan="5" class="loading-row">ابتدا سازمان را انتخاب کنید...</td></tr>';
    document.getElementById('eoDocTypesTableBody').innerHTML = '<tr><td colspan="7" class="loading-row">ابتدا سازمان را انتخاب کنید...</td></tr>';
    document.getElementById('eoMonTableBody').innerHTML = '<tr><td colspan="6" class="loading-row">ابتدا سازمان را انتخاب کنید...</td></tr>';
  }

  async function loadAll() {
    await Promise.all([loadPrograms(1), loadDocTypes()]);
    await loadMonitoring(1);
  }

  function showTab(tabId, btn) {
    document.querySelectorAll('#view-employee-onboarding > .tab-bar .tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('#view-employee-onboarding > .tab-content').forEach(tc => tc.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
  }

  // ═══ تب: مسیرها (OnboardingProgram با purpose=employee_onboarding) ══

  function searchProgramsDebounced() {
    clearTimeout(state.progSearchTimer);
    state.progSearchTimer = setTimeout(() => loadPrograms(1), 350);
  }

  async function loadPrograms(page = 1) {
    if (!state.orgId) return;
    state.progPage = page;
    const tbody = document.getElementById('eoProgTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>';
    state.progSearch = document.getElementById('eoProgSearch').value.trim();
    const p = new URLSearchParams({ page, page_size: 20, org_id: state.orgId, purpose: 'employee_onboarding' });
    if (state.progSearch) p.set('search', state.progSearch);
    try {
      const res = await api.get(`/onboarding/programs?${p}`);
      state.progItems = res.items || [];
      setText('eoProgTotalLabel', `${numFa(res.total)} مسیر`);
      if (!state.progItems.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--gray-400);">هنوز مسیری تعریف نشده</td></tr>';
        document.getElementById('eoProgPagination').innerHTML = '';
        return;
      }
      tbody.innerHTML = state.progItems.map(p => `
        <tr>
          <td style="font-weight:600;">${esc(p.name)}</td>
          <td>${numFa(p.step_count)} مرحله</td>
          <td>${numFa(p.enrollment_count)} نفر</td>
          <td>${statusBadge(p.is_active)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="edit-eo-program" data-id="${p.id}">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-eo-program" data-id="${p.id}" data-title="${esc(p.name)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
      renderPagination('eoProgPagination', res.page, res.total_pages, loadPrograms);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  // ─── ویزارد: تب‌ها ──────────────────────────────────────────────
  function switchProgramTab(tab) {
    if (state.progMode === 'create') {
      const targetIdx = EOP_TAB_ORDER.indexOf(tab);
      const maxIdx = EOP_TAB_ORDER.indexOf(state.maxUnlockedProgTab);
      if (targetIdx > maxIdx) return;
    }
    state.activeProgTab = tab;
    document.querySelectorAll('#eopModalTabs .tab-btn').forEach(b => b.classList.toggle('active', b.dataset.eoptab === tab));
    document.querySelectorAll('#modal-eo-program .obtab-content').forEach(el => el.classList.toggle('active', el.id === 'eoptab-' + tab));
    updateProgFooterButtons();
  }

  function setProgTabsUnlocked(maxTab) {
    state.maxUnlockedProgTab = maxTab;
    const maxIdx = EOP_TAB_ORDER.indexOf(maxTab);
    document.querySelectorAll('#eopModalTabs .tab-btn').forEach(b => {
      b.disabled = state.progMode === 'create' && EOP_TAB_ORDER.indexOf(b.dataset.eoptab) > maxIdx;
    });
  }

  function updateProgFooterButtons() {
    const next = document.getElementById('btn-eop-next');
    const save = document.getElementById('btn-eop-save');
    const finish = document.getElementById('btn-eop-finish');
    if (state.progMode === 'edit') {
      next.classList.add('hidden'); finish.classList.add('hidden'); save.classList.remove('hidden');
      return;
    }
    save.classList.add('hidden');
    const idx = EOP_TAB_ORDER.indexOf(state.activeProgTab);
    next.classList.toggle('hidden', idx === EOP_TAB_ORDER.length - 1);
    finish.classList.toggle('hidden', idx !== EOP_TAB_ORDER.length - 1);
  }

  function basicProgramPayload() {
    return {
      name: document.getElementById('eop-name').value.trim(),
      description: document.getElementById('eop-desc').value.trim() || null,
      purpose: 'employee_onboarding',
      deadline_days: document.getElementById('eop-deadline').value ? parseInt(document.getElementById('eop-deadline').value, 10) : null,
      points_override: document.getElementById('eop-points').value !== '' ? parseInt(document.getElementById('eop-points').value, 10) : null,
      is_active: true,
    };
  }

  async function nextProgramTab() {
    if (state.activeProgTab !== 'basic') return;
    const name = document.getElementById('eop-name').value.trim();
    if (!name) { toastError('نام مسیر اجباری است'); return; }
    const btn = document.getElementById('btn-eop-next');
    setLoading(btn, true);
    try {
      const payload = basicProgramPayload();
      payload.org_id = state.orgId;
      const created = await api.post('/onboarding/programs', payload);
      state.programId = created.id;
      document.getElementById('eop-id').value = created.id;
      toastSuccess('مشخصات ذخیره شد — حالا مراحل را اضافه کنید');
      await loadContentsAndQuizzesForSelect(state.orgId);
      state.activeSteps = created.steps || [];
      renderSteps();
      setProgTabsUnlocked('steps');
      switchProgramTab('steps');
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  async function finishProgramWizard() { closeModal('modal-eo-program'); await loadPrograms(1); }

  function closeProgramModal() {
    const wasCreatingDraft = state.progMode === 'create' && state.programId;
    closeModal('modal-eo-program');
    if (wasCreatingDraft) loadPrograms(1); // مسیر از تب ۱ به بعد از قبل روی سرور ساخته شده
  }

  function openCreateProgram() {
    if (!state.orgId) { toastError('ابتدا سازمان را انتخاب کنید'); return; }
    state.progMode = 'create'; state.programId = null; state.activeSteps = [];
    document.getElementById('eopModalTitle').textContent = 'مسیر Employee Onboarding جدید';
    document.getElementById('eop-id').value = '';
    ['eop-name', 'eop-desc'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('eop-deadline').value = '';
    document.getElementById('eop-points').value = '';
    document.getElementById('eop-is-active-wrap').classList.add('hidden');
    state.activeSteps = [];
    renderSteps();
    setProgTabsUnlocked('basic');
    switchProgramTab('basic');
    openModal('modal-eo-program');
  }

  async function openEditProgram(id) {
    let detail;
    try { detail = await api.get(`/onboarding/programs/${id}`); } catch (e) { toastError(e.message); return; }
    state.progMode = 'edit'; state.programId = detail.id; state.activeSteps = detail.steps || [];

    document.getElementById('eopModalTitle').textContent = 'ویرایش مسیر';
    document.getElementById('eop-id').value = detail.id;
    document.getElementById('eop-name').value = detail.name || '';
    document.getElementById('eop-desc').value = detail.description || '';
    document.getElementById('eop-deadline').value = detail.deadline_days ?? '';
    document.getElementById('eop-points').value = detail.points_override ?? '';
    document.getElementById('eop-is-active').checked = !!detail.is_active;
    document.getElementById('eop-is-active-wrap').classList.remove('hidden');

    await loadContentsAndQuizzesForSelect(state.orgId);
    setProgTabsUnlocked('steps');
    renderSteps();
    switchProgramTab('basic');
    openModal('modal-eo-program');
  }

  function collectEditableProgramPayload() {
    const p = basicProgramPayload();
    delete p.purpose; // بعد از ساخت قابل تغییر نیست — در PATCH ارسال نمی‌شود
    p.is_active = document.getElementById('eop-is-active').checked;
    return p;
  }

  async function saveProgram() {
    const btn = document.getElementById('btn-eop-save');
    setLoading(btn, true);
    try {
      await api.patch(`/onboarding/programs/${state.programId}`, collectEditableProgramPayload());
      toastSuccess('مسیر با موفقیت ویرایش شد');
      closeModal('modal-eo-program');
      await loadPrograms(state.progPage);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeProgram(id, name) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید مسیر "${name}" را حذف کنید؟ همه‌ی ثبت‌نام‌ها و پیشرفت کارکنان روی آن نیز حذف می‌شود.`, async () => {
      await api.delete(`/onboarding/programs/${id}`);
      toastSuccess('مسیر با موفقیت حذف شد');
      await loadPrograms(1);
    });
  }

  // ─── مراحل ──────────────────────────────────────────────────────
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
    const wrap = document.getElementById('eopStepsList');
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
          <div class="item-row-meta">${EO_STEP_TYPE_LABELS[s.type] || s.type}${s.content_title ? ' — ' + esc(s.content_title) : ''}${s.quiz_title ? ' — ' + esc(s.quiz_title) : ''}</div>
        </div>
        <div class="item-row-actions">
          <button class="btn-icon" title="ویرایش" data-role="edit-eo-step" data-id="${s.id}">✎</button>
          <button class="btn-icon" title="حذف" data-role="delete-eo-step" data-id="${s.id}" data-title="${esc(s.title)}">🗑</button>
        </div>
      </div>`).join('');
  }

  function refreshStepConditionalFields() {
    const type = document.getElementById('eops-type').value;
    document.getElementById('eops-content-wrap').classList.toggle('hidden', type !== 'content');
    document.getElementById('eops-quiz-wrap').classList.toggle('hidden', type !== 'quiz');
    document.getElementById('eops-doc-hint').classList.toggle('hidden', type !== 'document_upload');
    if (type === 'content' && !document.getElementById('eops-content-id').dataset.loaded) {
      document.getElementById('eops-content-id').innerHTML = '<option value="">— انتخاب محتوا —</option>' +
        state.contentsForSelect.map(c => `<option value="${c.id}">${esc(c.title)}</option>`).join('');
      document.getElementById('eops-content-id').dataset.loaded = '1';
    }
    if (type === 'quiz' && !document.getElementById('eops-quiz-id').dataset.loaded) {
      document.getElementById('eops-quiz-id').innerHTML = '<option value="">— انتخاب آزمون —</option>' +
        state.quizzesForSelect.map(q => `<option value="${q.id}">${esc(q.title)}</option>`).join('');
      document.getElementById('eops-quiz-id').dataset.loaded = '1';
    }
  }

  function openCreateStep() {
    document.getElementById('eopStepModalTitle').textContent = 'مرحله‌ی جدید';
    document.getElementById('eops-id').value = '';
    document.getElementById('eops-title').value = '';
    document.getElementById('eops-desc').value = '';
    document.getElementById('eops-type').value = 'custom';
    document.getElementById('eops-required').checked = true;
    document.getElementById('eops-points').value = '';
    document.getElementById('eops-content-id').dataset.loaded = '';
    document.getElementById('eops-quiz-id').dataset.loaded = '';
    refreshStepConditionalFields();
    openModal('modal-eo-program-step');
  }

  function openEditStep(id) {
    const s = state.activeSteps.find(x => x.id === id);
    if (!s) return;
    document.getElementById('eopStepModalTitle').textContent = 'ویرایش مرحله';
    document.getElementById('eops-id').value = s.id;
    document.getElementById('eops-title').value = s.title || '';
    document.getElementById('eops-desc').value = s.description || '';
    document.getElementById('eops-type').value = s.type;
    document.getElementById('eops-required').checked = !!s.is_required;
    document.getElementById('eops-points').value = s.points_override ?? '';
    document.getElementById('eops-content-id').dataset.loaded = '';
    document.getElementById('eops-quiz-id').dataset.loaded = '';
    refreshStepConditionalFields();
    if (s.content_id) document.getElementById('eops-content-id').value = s.content_id;
    if (s.quiz_id) document.getElementById('eops-quiz-id').value = s.quiz_id;
    openModal('modal-eo-program-step');
  }

  async function saveStep() {
    const id = document.getElementById('eops-id').value;
    const title = document.getElementById('eops-title').value.trim();
    const type = document.getElementById('eops-type').value;
    if (!title) { toastError('عنوان مرحله اجباری است'); return; }
    const payload = {
      title,
      description: document.getElementById('eops-desc').value.trim() || null,
      type,
      content_id: type === 'content' ? (document.getElementById('eops-content-id').value || null) : null,
      quiz_id: type === 'quiz' ? (document.getElementById('eops-quiz-id').value || null) : null,
      is_required: document.getElementById('eops-required').checked,
      points_override: document.getElementById('eops-points').value !== '' ? parseInt(document.getElementById('eops-points').value, 10) : null,
    };
    const btn = document.getElementById('btn-eops-save');
    setLoading(btn, true);
    try {
      if (id) await api.patch(`/onboarding/steps/${id}`, payload);
      else await api.post(`/onboarding/programs/${state.programId}/steps`, payload);
      toastSuccess('مرحله با موفقیت ذخیره شد');
      closeModal('modal-eo-program-step');
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

  // ═══ تب: کاتالوگ مدارک (Document Types) ═════════════════════════

  async function loadDocTypes() {
    const tbody = document.getElementById('eoDocTypesTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="loading-row">در حال بارگذاری...</td></tr>';
    try {
      state.docTypes = await api.get(`/employee-onboarding/document-types?org_id=${state.orgId}`) || [];
      if (!state.docTypes.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--gray-400);">هنوز مدرکی در کاتالوگ تعریف نشده</td></tr>';
        return;
      }
      tbody.innerHTML = state.docTypes.map(d => {
        const detail = d.input_type === 'file'
          ? (d.allowed_extensions?.length ? esc(d.allowed_extensions.join('، ')) : 'همه فرمت‌ها') +
            (d.max_size_mb ? ` — حداکثر ${numFa(d.max_size_mb)}MB` : '')
          : '—';
        return `
        <tr>
          <td style="font-weight:500;">${esc(d.name)}</td>
          <td>${EO_INPUT_TYPE_LABELS[d.input_type] || d.input_type}</td>
          <td>${d.is_required ? '<span class="badge badge-manager">اجباری</span>' : '<span class="badge badge-employee">اختیاری</span>'}</td>
          <td style="color:var(--gray-500);font-size:12px;">${detail}</td>
          <td>${numFa(d.submission_count)} نفر</td>
          <td>${statusBadge(d.is_active)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="edit-doctype" data-id="${d.id}">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-doctype" data-id="${d.id}" data-title="${esc(d.name)}">حذف</button>
            </div>
          </td>
        </tr>`;
      }).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function onDocTypeInputTypeChange() {
    const isFile = document.getElementById('eo-dt-input-type').value === 'file';
    document.getElementById('eo-dt-file-fields').classList.toggle('hidden', !isFile);
  }

  function openCreateDocType() {
    document.getElementById('eoDocTypeModalTitle').textContent = 'قلم جدید';
    document.getElementById('eo-dt-id').value = '';
    document.getElementById('eo-dt-name').value = '';
    document.getElementById('eo-dt-desc').value = '';
    document.getElementById('eo-dt-input-type').value = 'file';
    document.getElementById('eo-dt-required').checked = true;
    document.getElementById('eo-dt-extensions').value = '';
    document.getElementById('eo-dt-max-size').value = '';
    document.getElementById('eo-dt-template-input').value = '';
    document.getElementById('eo-dt-template-url').value = '';
    document.getElementById('eo-dt-template-hint').textContent = 'اگر کارمند باید یک فرم خاص را دانلود/پر/آپلود کند';
    document.getElementById('eo-dt-order').value = '0';
    document.getElementById('eo-dt-active').checked = true;
    onDocTypeInputTypeChange();
    openModal('modal-eo-doctype');
  }

  function openEditDocType(id) {
    const d = state.docTypes.find(x => x.id === id);
    if (!d) return;
    document.getElementById('eoDocTypeModalTitle').textContent = 'ویرایش قلم';
    document.getElementById('eo-dt-id').value = d.id;
    document.getElementById('eo-dt-name').value = d.name || '';
    document.getElementById('eo-dt-desc').value = d.description || '';
    document.getElementById('eo-dt-input-type').value = d.input_type || 'file';
    document.getElementById('eo-dt-required').checked = !!d.is_required;
    document.getElementById('eo-dt-extensions').value = (d.allowed_extensions || []).join(', ');
    document.getElementById('eo-dt-max-size').value = d.max_size_mb ?? '';
    document.getElementById('eo-dt-template-input').value = '';
    document.getElementById('eo-dt-template-url').value = d.template_file_url || '';
    document.getElementById('eo-dt-template-hint').textContent = d.template_file_url
      ? 'فرم خام فعلی ثبت شده — انتخاب فایل جدید آن را جایگزین می‌کند'
      : 'اگر کارمند باید یک فرم خاص را دانلود/پر/آپلود کند';
    document.getElementById('eo-dt-order').value = d.order_index ?? 0;
    document.getElementById('eo-dt-active').checked = !!d.is_active;
    onDocTypeInputTypeChange();
    openModal('modal-eo-doctype');
  }

  async function onTemplateFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;
    const hint = document.getElementById('eo-dt-template-hint');
    hint.textContent = 'در حال آپلود...';
    try {
      const res = await api.upload(`/employee-onboarding/document-types/upload-template?org_id=${state.orgId}`, file);
      document.getElementById('eo-dt-template-url').value = res.url;
      hint.textContent = `آپلود شد: ${res.filename || file.name}`;
    } catch (e) {
      hint.textContent = 'اگر کارمند باید یک فرم خاص را دانلود/پر/آپلود کند';
      toastError(e.message);
    }
  }

  async function saveDocType() {
    const id = document.getElementById('eo-dt-id').value;
    const name = document.getElementById('eo-dt-name').value.trim();
    if (!name) { toastError('نام قلم اجباری است'); return; }
    const inputType = document.getElementById('eo-dt-input-type').value;
    const payload = {
      name,
      description: document.getElementById('eo-dt-desc').value.trim() || null,
      input_type: inputType,
      is_required: document.getElementById('eo-dt-required').checked,
      order_index: parseInt(document.getElementById('eo-dt-order').value, 10) || 0,
      is_active: document.getElementById('eo-dt-active').checked,
    };
    if (inputType === 'file') {
      const extRaw = document.getElementById('eo-dt-extensions').value.trim();
      payload.allowed_extensions = extRaw ? extRaw.split(',').map(s => s.trim().toLowerCase().replace(/^\./, '')).filter(Boolean) : [];
      payload.max_size_mb = document.getElementById('eo-dt-max-size').value ? parseInt(document.getElementById('eo-dt-max-size').value, 10) : null;
      payload.template_file_url = document.getElementById('eo-dt-template-url').value || null;
    } else {
      payload.allowed_extensions = [];
      payload.max_size_mb = null;
      payload.template_file_url = null;
    }
    if (!id) payload.org_id = state.orgId;

    const btn = document.getElementById('btn-save-eo-doctype');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/employee-onboarding/document-types/${id}`, payload); toastSuccess('قلم با موفقیت ویرایش شد'); }
      else { await api.post('/employee-onboarding/document-types', payload); toastSuccess('قلم با موفقیت به کاتالوگ اضافه شد'); }
      closeModal('modal-eo-doctype');
      await loadDocTypes();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeDocType(id, name) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید «${name}» را از کاتالوگ حذف کنید؟`, async () => {
      await api.delete(`/employee-onboarding/document-types/${id}`);
      toastSuccess('حذف شد');
      await loadDocTypes();
    });
  }

  // ═══ تب: پیشرفت کارکنان (Monitoring) — همچنین بخش «مدارک» در پروفایل کاربر ═

  function searchDebounced() {
    clearTimeout(state.monSearchTimer);
    state.monSearchTimer = setTimeout(() => loadMonitoring(1), 350);
  }

  async function loadMonitoring(page = 1) {
    if (!state.orgId) return;
    state.monPage = page;
    const tbody = document.getElementById('eoMonTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>';
    state.monSearch = document.getElementById('eoMonSearch').value.trim();
    const blockedOnly = document.getElementById('eoMonBlockedOnly').checked;
    const p = new URLSearchParams({ page, page_size: 20, org_id: state.orgId });
    if (state.monSearch) p.set('search', state.monSearch);
    if (blockedOnly) p.set('blocked_only', 'true');
    try {
      const res = await api.get(`/employee-onboarding/monitoring?${p}`);
      state.monItems = res.items || [];
      if (!state.monItems.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--gray-400);">هنوز کسی در مسیرهای Employee Onboarding ثبت‌نام نشده</td></tr>';
        document.getElementById('eoMonPagination').innerHTML = '';
        return;
      }
      tbody.innerHTML = state.monItems.map(s => `
        <tr>
          <td style="font-weight:500;">${esc(s.user_name)}</td>
          <td>${enrollmentsCell(s)}</td>
          <td>${documentsCell(s)}</td>
          <td>${s.is_blocked ? '<span class="badge badge-manager">مسدود</span>' : '<span class="badge badge-active">آزاد شده</span>'}</td>
          <td style="color:var(--gray-500);">${s.last_activity_at ? fmtDate(s.last_activity_at) : '—'}</td>
          <td><button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="view-eo-detail" data-id="${s.user_id}">جزئیات</button></td>
        </tr>`).join('');
      renderPagination('eoMonPagination', res.page, res.total_pages, loadMonitoring);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function enrollmentsCell(s) {
    if (!s.enrollments || !s.enrollments.length) return '<span style="color:var(--gray-400);">ثبت‌نام نشده</span>';
    const allDone = s.enrollments.every(e => e.completed_at);
    if (allDone) return '<span class="badge badge-active">تکمیل‌شده</span>';
    const avgPct = Math.round(s.enrollments.reduce((sum, e) => sum + e.progress_pct, 0) / s.enrollments.length);
    return `<span class="badge badge-manager">${numFa(avgPct)}٪</span>`;
  }

  function documentsCell(s) {
    if (!s.documents || !s.documents.required_count) return '<span style="color:var(--gray-400);">موردی تعریف نشده</span>';
    return s.documents.completed
      ? '<span class="badge badge-active">تکمیل‌شده</span>'
      : `<span class="badge badge-manager">${numFa(s.documents.submitted_count)}/${numFa(s.documents.required_count)}</span>`;
  }

  /** برای فراخوانی از users.js (دکمه‌ی «مدارک» روی هر ردیف کاربر) هم استفاده می‌شود. */
  async function viewDetail(userId) {
    document.getElementById('eoMonDetailBody').innerHTML = '<div class="loading-row">در حال بارگذاری...</div>';
    openModal('modal-eo-monitoring-detail');
    try {
      const s = await api.get(`/employee-onboarding/monitoring/${userId}`);
      document.getElementById('eoMonDetailTitle').textContent = `وضعیت — ${s.user_name}`;

      const enrollmentsHtml = (s.enrollments || []).length ? `
        <div class="form-section-title">مسیر(های) Employee Onboarding</div>
        ${s.enrollments.map(e => `
          <p style="font-size:13px;color:var(--gray-600);margin:0 0 8px;">
            ${esc(e.program_name)} — ${e.completed_at ? 'تکمیل‌شده' : `${numFa(e.progress_pct)}٪ پیشرفت (${numFa(e.steps_completed)}/${numFa(e.steps_total)} مرحله)`}
          </p>`).join('')}
      ` : '<p style="font-size:13px;color:var(--gray-400);">در هیچ مسیری ثبت‌نام نشده</p>';

      const docsRows = (s.documents.items || []).map(it => `
        <tr>
          <td>${esc(it.document_type_name)}${it.is_required ? '' : ' <span class="badge badge-employee" style="font-size:10px;">اختیاری</span>'}</td>
          <td>${EO_DOC_STATUS_LABELS[it.status] || esc(it.status)}</td>
          <td style="font-size:12px;color:var(--gray-500);">${it.input_type === 'text' ? esc(it.text_value || '—') : (it.file_url ? `<a href="${esc(it.file_url)}" target="_blank" rel="noopener">مشاهده فایل</a>` : '—')}</td>
        </tr>`).join('');

      document.getElementById('eoMonDetailBody').innerHTML = `
        ${enrollmentsHtml}
        <div class="form-section-title" style="margin-top:14px;">مدارک</div>
        <table style="width:100%;">
          <thead><tr><th>عنوان</th><th>وضعیت</th><th>مقدار</th></tr></thead>
          <tbody>${docsRows || '<tr><td colspan="3" style="color:var(--gray-400);">موردی در کاتالوگ سازمان تعریف نشده</td></tr>'}</tbody>
        </table>
      `;
    } catch (e) {
      document.getElementById('eoMonDetailBody').innerHTML = `<p style="color:var(--danger);">${esc(e.message)}</p>`;
    }
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row Actions ────────────────────────────────────────
  document.getElementById('eoProgTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role]');
    if (!btn) return;
    const { role, id, title } = btn.dataset;
    if (role === 'edit-eo-program') openEditProgram(id);
    else if (role === 'delete-eo-program') removeProgram(id, title);
  });
  document.getElementById('eopStepsList')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role]');
    if (!btn) return;
    const { role, id, title } = btn.dataset;
    if (role === 'edit-eo-step') openEditStep(id);
    else if (role === 'delete-eo-step') removeStep(id, title);
  });
  document.getElementById('eoDocTypesTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role]');
    if (!btn) return;
    const { role, id, title } = btn.dataset;
    if (role === 'edit-doctype') openEditDocType(id);
    else if (role === 'delete-doctype') removeDocType(id, title);
  });
  document.getElementById('eoMonTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="view-eo-detail"]');
    if (btn) viewDetail(btn.dataset.id);
  });

  return {
    init, onOrgChange, showTab,
    searchProgramsDebounced, openCreateProgram, openEditProgram, switchProgramTab, nextProgramTab,
    finishProgramWizard, closeProgramModal, saveProgram, removeProgram,
    openCreateStep, openEditStep, saveStep, removeStep, refreshStepConditionalFields,
    openCreateDocType, openEditDocType, onDocTypeInputTypeChange, onTemplateFileSelected, saveDocType, removeDocType,
    searchDebounced, loadMonitoring, viewDetail,
  };
})();
