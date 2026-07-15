// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «کاربران»
// ════════════════════════════════════════════════════════════════════
// super_admin: تمام کاربران پلتفرم (با ستون/فیلتر سازمان + انتخاب سازمان در مودال)
// org_admin/manager: فقط کاربران سازمان خودشان (org_admin مجاز به ساخت/حذف، manager فقط مشاهده+ویرایش جزئی)

const UsersPage = (() => {
  const state = { page: 1, pages: 1, items: [], orgs: [], depts: [], positions: [] };

  async function load(page = state.page) {
    state.page = page;
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = `<tr><td colspan="${colCount()}" class="loading-row">در حال بارگذاری...</td></tr>`;

    const search = document.getElementById('usersSearch')?.value.trim() || '';
    const role = document.getElementById('usersRoleFilter')?.value || '';
    const active = document.getElementById('usersStatusFilter')?.value || '';
    const params = new URLSearchParams({ page, per_page: 20 });
    if (search) params.set('search', search);
    if (role) params.set('role', role);
    if (active) params.set('is_active', active);

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
            <button class="btn-action" style="background:#FFF7ED;color:#D97706;" onclick="UsersPage.resetPassword('${u.id}','${esc(u.full_name)}')" title="یک رمز موقت تصادفی می‌سازد — سرویس ایمیل وجود ندارد، رمز را باید دستی به کاربر بدهید">Reset رمز</button>
            <button class="btn-action ${u.is_active ? 'btn-toggle-on' : 'btn-toggle-off'}" onclick="UsersPage.toggleActive('${u.id}')">${u.is_active ? 'غیرفعال کن' : 'فعال کن'}</button>
            <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" onclick="UsersPage.remove('${u.id}','${esc(u.full_name)}')">حذف</button>
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
    if (!state.orgs.length) {
      try { state.orgs = await api.get('/orgs/') || []; } catch { /* ignore */ }
    }
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

  // search/filter با debounce
  const searchDebounced = (() => { let t; return () => { clearTimeout(t); t = setTimeout(() => load(1), 400); }; })();

  return { load, openCreate, openEdit, save, toggleActive, remove, searchDebounced, resetPassword, copyTempPassword };
})();