// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «کاربران»
// ════════════════════════════════════════════════════════════════════
// super_admin: تمام کاربران پلتفرم (با ستون/فیلتر سازمان + انتخاب سازمان در مودال)
// org_admin/manager: فقط کاربران سازمان خودشان (org_admin مجاز به ساخت/حذف، manager فقط مشاهده+ویرایش جزئی)

const UsersPage = (() => {
  const state = { page: 1, pages: 1, items: [], orgs: [], depts: [], positions: [], lastImportCreds: [] };

  // ─── راه‌اندازی صفحه: بارگذاری فیلترها + لیست ────────────────────
  async function init() {
    if (App.isSuperAdmin) {
      await loadOrgFilterOptions();
      await Promise.all([loadDeptFilterOptions(null), loadPositionFilterOptions(null, null)]);
    } else {
      await Promise.all([
        loadDeptFilterOptions(App.currentUser.org_id),
        loadPositionFilterOptions(App.currentUser.org_id, null),
      ]);
    }
    await load(1);
  }

  async function loadOrgFilterOptions() {
    const sel = document.getElementById('usersOrgFilter');
    if (!sel || sel.dataset.loaded) return;
    try {
      state.orgs = await ensureOrgsLoaded();
      sel.innerHTML = '<option value="">همه سازمان‌ها</option>' +
        state.orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
      sel.dataset.loaded = '1';
    } catch { /* غیرحیاتی — فقط فیلتر است */ }
  }

  async function loadDeptFilterOptions(orgId) {
    const sel = document.getElementById('usersDeptFilter');
    if (!orgId) {
      sel.innerHTML = '<option value="">همه واحدها</option>';
      sel.disabled = true;
      return;
    }
    sel.disabled = false;
    try {
      const depts = await api.get(`/departments/?org_id=${orgId}`);
      sel.innerHTML = '<option value="">همه واحدها</option>' +
        (depts || []).map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
    } catch {
      sel.innerHTML = '<option value="">خطا در بارگذاری واحدها</option>';
    }
  }

  async function loadPositionFilterOptions(orgId, deptId) {
    const sel = document.getElementById('usersPositionFilter');
    if (!orgId) {
      sel.innerHTML = '<option value="">همه پست‌ها</option>';
      sel.disabled = true;
      return;
    }
    sel.disabled = false;
    try {
      const p = new URLSearchParams({ org_id: orgId });
      if (deptId) p.set('dept_id', deptId);
      const positions = await api.get(`/positions/?${p}`);
      sel.innerHTML = '<option value="">همه پست‌ها</option>' +
        (positions || []).map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join('');
    } catch {
      sel.innerHTML = '<option value="">خطا در بارگذاری پست‌ها</option>';
    }
  }

  async function onOrgFilterChange() {
    const orgId = document.getElementById('usersOrgFilter').value || null;
    document.getElementById('usersDeptFilter').value = '';
    document.getElementById('usersPositionFilter').value = '';
    await Promise.all([loadDeptFilterOptions(orgId), loadPositionFilterOptions(orgId, null)]);
    load(1);
  }

  async function onDeptFilterChange() {
    const orgId = App.isSuperAdmin ? (document.getElementById('usersOrgFilter').value || null) : App.currentUser.org_id;
    const deptId = document.getElementById('usersDeptFilter').value || null;
    document.getElementById('usersPositionFilter').value = '';
    await loadPositionFilterOptions(orgId, deptId);
    load(1);
  }

  async function ensureOrgsLoaded() {
    if (!state.orgs.length) {
      try { state.orgs = await api.get('/orgs/') || []; } catch { /* ignore */ }
    }
    return state.orgs;
  }

  async function load(page = state.page) {
    state.page = page;
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = `<tr><td colspan="${colCount()}" class="loading-row">در حال بارگذاری...</td></tr>`;

    const search = document.getElementById('usersSearch')?.value.trim() || '';
    const role = document.getElementById('usersRoleFilter')?.value || '';
    const active = document.getElementById('usersStatusFilter')?.value || '';
    const orgFilter = App.isSuperAdmin ? (document.getElementById('usersOrgFilter')?.value || '') : '';
    const deptFilter = document.getElementById('usersDeptFilter')?.value || '';
    const posFilter = document.getElementById('usersPositionFilter')?.value || '';
    const params = new URLSearchParams({ page, per_page: 20 });
    if (search) params.set('search', search);
    if (role) params.set('role', role);
    if (active) params.set('is_active', active);
    if (orgFilter) params.set('org_id', orgFilter);
    if (deptFilter) params.set('dept_id', deptFilter);
    if (posFilter) params.set('position_id', posFilter);

    try {
      const endpoint = App.isSuperAdmin ? '/users/all' : '/users/';
      const d = await api.get(`${endpoint}?${params}`);
      state.pages = d.pages;
      state.items = d.items;
      setText('usersTotalLabel', `مجموع ${numFa(d.total)} کاربر`);

      if (!d.items.length) {
        tbody.innerHTML = `<tr><td colspan="${colCount()}" style="text-align:center;padding:40px;color:var(--gray-400);">کاربری یافت نشد</td></tr>`;
        document.getElementById('usersPagination').innerHTML = '';
        return;
      }

      const offset = (d.page - 1) * 20;
      tbody.innerHTML = d.items.map((u, i) => renderRow(u, offset + i + 1)).join('');
      renderPagination('usersPagination', d.page, d.pages, load);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="${colCount()}" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function colCount() { return App.isSuperAdmin ? 10 : 9; }

  function renderRow(u, idx) {
    return `
      <tr>
        <td style="color:var(--gray-400);">${numFa(idx)}</td>
        <td><div style="display:flex;align-items:center;gap:8px;"><div class="user-avatar">${initials(u.full_name)}</div><span style="font-weight:500;">${esc(u.full_name)}</span></div></td>
        <td style="direction:ltr;text-align:right;color:var(--gray-500);">${esc(u.email)}</td>
        <td>${roleBadge(u.role)}</td>
        <td style="color:var(--gray-500);">${u.department ? esc(u.department) : '—'}</td>
        <td style="color:var(--gray-500);">${u.position ? esc(u.position) : '—'}</td>
        ${App.isSuperAdmin ? `<td>${esc(u.org_name)}</td>` : ''}
        <td>${statusBadge(u.is_active)}</td>
        <td style="color:var(--gray-500);">${fmtDate(u.created_at)}</td>
        <td>
          <div style="display:flex;gap:4px;flex-wrap:wrap;">
            <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="UsersPage.openEdit('${u.id}')">ویرایش</button>
            <button class="btn-action" style="background:#FFF7ED;color:#D97706;" data-role="reset-password" data-id="${u.id}" data-title="${esc(u.full_name)}" title="یک رمز موقت تصادفی می‌سازد — سرویس ایمیل وجود ندارد، رمز را باید دستی به کاربر بدهید">Reset رمز</button>
            <button class="btn-action ${u.is_active ? 'btn-toggle-on' : 'btn-toggle-off'}" onclick="UsersPage.toggleActive('${u.id}')">${u.is_active ? 'غیرفعال کن' : 'فعال کن'}</button>
            <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-user" data-id="${u.id}" data-title="${esc(u.full_name)}">حذف</button>
          </div>
        </td>
      </tr>`;
  }

  // ─── Reset Password (بدون سرویس ایمیل — رمز موقت را ادمین دستی می‌دهد) ──
  function resetPassword(id, name) {
    confirmAction(
      `رمز عبور "${name}" Reset می‌شود و یک رمز موقت تصادفی ساخته می‌شود. تمام session های فعال این کاربر باطل می‌شوند و او تا تغییر رمز، به هیچ بخش دیگری دسترسی نخواهد داشت. ادامه می‌دهید؟`,
      async () => {
        const res = await api.post(`/users/${id}/reset-password`);
        showTempPasswordModal(name, res.temp_password);
      }
    );
  }

  function showTempPasswordModal(name, tempPassword) {
    document.getElementById('tempPasswordUserName').textContent = name;
    document.getElementById('tempPasswordValue').textContent = tempPassword;
    openModal('modal-temp-password');
  }

  function copyTempPassword() {
    const pw = document.getElementById('tempPasswordValue').textContent;
    navigator.clipboard?.writeText(pw).then(
      () => toastSuccess('رمز موقت کپی شد'),
      () => toastError('کپی خودکار پشتیبانی نمی‌شود — رمز را دستی انتخاب کنید')
    );
  }

  async function toggleActive(id) {
    try {
      const d = await api.patch(`/users/${id}/toggle-active`);
      toastSuccess(d.message);
      load(state.page);
    } catch (e) { toastError(e.message); }
  }

  function remove(id, name) {
    confirmAction(
      `آیا مطمئن هستید که می‌خواهید "${name}" را حذف کنید؟ این عمل قابل بازگشت نیست.`,
      async () => {
        await api.delete(`/users/${id}`);
        toastSuccess('کاربر با موفقیت حذف شد');
        await load(state.page);
      }
    );
  }

  // ─── Create / Edit modal ────────────────────────────────────────
  async function openCreate() {
    document.getElementById('userModalTitle').textContent = 'کاربر جدید';
    document.getElementById('un-id').value = '';
    ['un-name', 'un-email', 'un-phone', 'un-password'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('un-role').value = 'employee';
    document.getElementById('un-password-wrap').classList.remove('hidden');

    if (App.isSuperAdmin) {
      document.getElementById('un-org-wrap').classList.remove('hidden');
      await populateOrgSelect();
      await populateDeptPositionSelects(document.getElementById('un-org').value, '', '');
    } else {
      document.getElementById('un-org-wrap').classList.add('hidden');
      await populateDeptPositionSelects(App.currentUser.org_id, '', '');
    }
    openModal('modal-user');
  }

  async function openEdit(id) {
    const u = state.items.find(x => x.id === id);
    if (!u) return;
    document.getElementById('userModalTitle').textContent = 'ویرایش کاربر';
    document.getElementById('un-id').value = u.id;
    document.getElementById('un-name').value = u.full_name;
    document.getElementById('un-email').value = u.email;
    document.getElementById('un-phone').value = '';
    document.getElementById('un-password').value = '';
    document.getElementById('un-role').value = u.role;
    document.getElementById('un-password-wrap').classList.add('hidden'); // تغییر پسورد جزو این فرم نیست

    const orgId = App.isSuperAdmin ? u.org_id : App.currentUser.org_id;
    if (App.isSuperAdmin) {
      document.getElementById('un-org-wrap').classList.remove('hidden');
      await populateOrgSelect(orgId);
    } else {
      document.getElementById('un-org-wrap').classList.add('hidden');
    }
    await populateDeptPositionSelects(orgId, u.dept_id, u.position_id);
    openModal('modal-user');
  }

  async function populateOrgSelect(selectedOrgId) {
    await ensureOrgsLoaded();
    const sel = document.getElementById('un-org');
    sel.innerHTML = state.orgs.map(o =>
      `<option value="${o.id}" ${o.id === selectedOrgId ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
    sel.onchange = () => populateDeptPositionSelects(sel.value, '', '');
  }

  async function populateDeptPositionSelects(orgId, selectedDeptId, selectedPosId) {
    const deptSel = document.getElementById('un-dept');
    const posSel = document.getElementById('un-position');
    if (!orgId) {
      deptSel.innerHTML = '<option value="">— ابتدا سازمان را انتخاب کنید —</option>';
      posSel.innerHTML = '<option value="">— ابتدا سازمان را انتخاب کنید —</option>';
      return;
    }
    try {
      const [depts, positions] = await Promise.all([
        api.get(`/departments/?org_id=${orgId}`),
        api.get(`/positions/?org_id=${orgId}`),
      ]);
      state.depts = depts || [];
      state.positions = positions || [];
      deptSel.innerHTML = '<option value="">— بدون واحد —</option>' +
        state.depts.map(d => `<option value="${d.id}" ${d.id === selectedDeptId ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
      posSel.innerHTML = '<option value="">— بدون پست —</option>' +
        state.positions.map(p => `<option value="${p.id}" ${p.id === selectedPosId ? 'selected' : ''}>${esc(p.name)}</option>`).join('');
    } catch (e) {
      deptSel.innerHTML = '<option value="">خطا در بارگذاری واحدها</option>';
      posSel.innerHTML = '<option value="">خطا در بارگذاری پست‌ها</option>';
    }
  }

  async function save() {
    const id = document.getElementById('un-id').value;
    const full_name = document.getElementById('un-name').value.trim();
    const email = document.getElementById('un-email').value.trim();
    const phone = document.getElementById('un-phone').value.trim();
    const role = document.getElementById('un-role').value;
    const password = document.getElementById('un-password').value;
    const dept_id = document.getElementById('un-dept').value || null;
    const position_id = document.getElementById('un-position').value || null;
    const org_id = App.isSuperAdmin ? document.getElementById('un-org').value : App.currentUser.org_id;

    if (!full_name || !email || !org_id) { toastError('نام، ایمیل و سازمان اجباری هستند'); return; }
    if (!id && (!password || password.length < 8)) { toastError('پسورد باید حداقل ۸ کاراکتر باشد'); return; }

    const btn = document.getElementById('btn-save-user');
    setLoading(btn, true);
    try {
      if (id) {
        await api.patch(`/users/${id}`, { full_name, email, role, phone: phone || null, dept_id, position_id });
        toastSuccess('کاربر با موفقیت ویرایش شد');
      } else {
        await api.post('/users/', { full_name, email, role, org_id, phone: phone || null, password, dept_id, position_id });
        toastSuccess('کاربر با موفقیت ایجاد شد');
      }
      closeModal('modal-user');
      await load(state.page);
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
  function setUploadName(id, name, hasFile = !!name) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = name || 'فایلی انتخاب نشده';
    el.classList.toggle('has-file', hasFile);
  }

  // search/filter با debounce
  const searchDebounced = (() => { let t; return () => { clearTimeout(t); t = setTimeout(() => load(1), 400); }; })();

  // ─── Excel: قالب / خروجی / Import ─────────────────────────────────
  function currentFilterParams() {
    const search = document.getElementById('usersSearch')?.value.trim() || '';
    const role = document.getElementById('usersRoleFilter')?.value || '';
    const active = document.getElementById('usersStatusFilter')?.value || '';
    const orgFilter = App.isSuperAdmin ? (document.getElementById('usersOrgFilter')?.value || '') : '';
    const deptFilter = document.getElementById('usersDeptFilter')?.value || '';
    const posFilter = document.getElementById('usersPositionFilter')?.value || '';
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (role) params.set('role', role);
    if (active) params.set('is_active', active);
    if (orgFilter) params.set('org_id', orgFilter);
    if (deptFilter) params.set('dept_id', deptFilter);
    if (posFilter) params.set('position_id', posFilter);
    return params;
  }

  async function downloadTemplate() {
    try {
      await api.download('/users/template', 'talentick-users-template.xlsx');
    } catch (e) { toastError(e.message); }
  }

  async function exportExcel() {
    try {
      await api.download(`/users/export?${currentFilterParams()}`, 'talentick-users-export.xlsx');
      toastSuccess('فایل Excel دانلود شد');
    } catch (e) { toastError(e.message); }
  }

  function onImportFileChange(inputEl) {
    const file = inputEl.files?.[0];
    setUploadName('ui-file-name', file ? file.name : '', !!file);
  }

  async function openImport() {
    document.getElementById('ui-file').value = '';
    setUploadName('ui-file-name', '');
    document.getElementById('ui-update-existing').checked = false;
    if (App.isSuperAdmin) {
      await ensureOrgsLoaded();
      const sel = document.getElementById('ui-org');
      sel.innerHTML = '<option value="">— انتخاب سازمان —</option>' +
        state.orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
    }
    openModal('modal-user-import');
  }

  async function submitImport() {
    const fileInput = document.getElementById('ui-file');
    const file = fileInput.files?.[0];
    if (!file) { toastError('لطفاً یک فایل Excel انتخاب کنید'); return; }
    let orgId = null;
    if (App.isSuperAdmin) {
      orgId = document.getElementById('ui-org').value;
      if (!orgId) { toastError('لطفاً سازمان مقصد را انتخاب کنید'); return; }
    }
    const updateExisting = document.getElementById('ui-update-existing').checked;

    const btn = document.getElementById('btn-import-users');
    setLoading(btn, true);
    try {
      const params = new URLSearchParams({ update_existing: updateExisting });
      if (orgId) params.set('org_id', orgId);
      const result = await api.upload(`/users/import?${params}`, file);
      closeModal('modal-user-import');
      showImportResult(result);
      await load(1);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function showImportResult(result) {
    state.lastImportCreds = result.created_users || [];

    document.getElementById('uiResultStats').innerHTML = [
      ['کل ردیف‌ها', result.total_rows, 'var(--gray-700)'],
      ['ساخته‌شده', result.created, 'var(--success)'],
      ['به‌روزرسانی‌شده', result.updated, 'var(--primary)'],
      ['رد‌شده / خطا', result.skipped + (result.errors?.length || 0), 'var(--danger)'],
    ].map(([label, value, color]) => `
      <div class="stat-card"><div class="stat-card-info"><div class="stat-card-label">${label}</div><div class="stat-card-value" style="color:${color};">${numFa(value)}</div></div></div>
    `).join('');

    const credsWrap = document.getElementById('uiResultCredsWrap');
    const credsList = document.getElementById('uiResultCredsList');
    if (state.lastImportCreds.length) {
      credsWrap.classList.remove('hidden');
      credsList.innerHTML = state.lastImportCreds.map((c, idx) => `
        <div style="display:flex;align-items:center;gap:8px;background:var(--gray-50);border:1.5px dashed var(--gray-300);border-radius:var(--radius-md);padding:9px 12px;">
          <span style="flex:1;font-size:12.5px;color:var(--gray-700);direction:ltr;text-align:left;">${esc(c.email)}</span>
          <code style="font-weight:700;letter-spacing:.4px;direction:ltr;color:var(--gray-800);">${esc(c.temp_password)}</code>
          <button class="btn-icon" title="کپی" onclick="UsersPage.copyCred(${idx})">📋</button>
        </div>`).join('');
    } else {
      credsWrap.classList.add('hidden');
    }

    const errorsWrap = document.getElementById('uiResultErrorsWrap');
    const errorsList = document.getElementById('uiResultErrorsList');
    if (result.errors?.length) {
      errorsWrap.classList.remove('hidden');
      errorsList.innerHTML = result.errors.map(er => `
        <div style="font-size:12.5px;color:var(--danger);background:#FEF2F2;border-radius:var(--radius-sm);padding:8px 10px;">
          سطر ${numFa(er.row)}${er.email ? ' (' + esc(er.email) + ')' : ''}: ${esc(er.message)}
        </div>`).join('');
    } else {
      errorsWrap.classList.add('hidden');
    }

    openModal('modal-user-import-result');
  }

  function copyCred(idx) {
    const c = state.lastImportCreds[idx];
    if (!c) return;
    navigator.clipboard?.writeText(c.temp_password).then(
      () => toastSuccess(`رمز ${c.email} کپی شد`),
      () => toastError('کپی خودکار پشتیبانی نمی‌شود — رمز را دستی انتخاب کنید')
    );
  }

  function closeImportResult() {
    closeModal('modal-user-import-result');
  }

  // ─── Delegated Row Actions — به‌جای onclick اینلاین با نام کاربر ──────
  document.getElementById('usersTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role]');
    if (!btn) return;
    const { role, id, title } = btn.dataset;
    if (role === 'reset-password') resetPassword(id, title);
    else if (role === 'delete-user') remove(id, title);
  });

  return {
    init, load, openCreate, openEdit, save, toggleActive, remove, searchDebounced, resetPassword, copyTempPassword,
    onOrgFilterChange, onDeptFilterChange,
    downloadTemplate, exportExcel, openImport, onImportFileChange, submitImport, copyCred, closeImportResult,
  };
})();