// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «ساختار سازمانی» (واحدها + پست‌ها)
// ════════════════════════════════════════════════════════════════════
// super_admin: از طریق دکمه‌ی «ساختار سازمانی» روی هر ردیف در صفحه‌ی
//              «شرکت‌ها» باز می‌شود (StructurePage.openFor(orgId, orgName)).
// org_admin/manager: مستقیماً از منوی سایدبار، همیشه روی سازمان خودشان.

const StructurePage = (() => {
  const state = { orgId: null, orgName: '', depts: [], positions: [] };

  /** super_admin از این مسیر وارد می‌شود (نه از Router.navigate معمولی). */
  function openFor(orgId, orgName) {
    state.orgId = orgId;
    state.orgName = orgName;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-structure').classList.add('active');
    document.querySelectorAll('.sidebar-nav [data-page]').forEach(el =>
      el.classList.toggle('active', el.dataset.page === 'orgs'));
    document.getElementById('headerTitle').textContent = 'ساختار سازمانی';
    setText('structTitle', `ساختار سازمانی — ${orgName}`);
    setText('structSubtitle', `مدیریت واحدها و پست‌های سازمانی «${orgName}»`);
    document.getElementById('structBackBtn').classList.remove('hidden');
    loadDepts();
    loadPositions();
  }

  /** org_admin/manager — صدا زده می‌شود توسط Router.register('structure', ...) */
  function loadOwn() {
    state.orgId = App.currentUser.org_id;
    state.orgName = '';
    setText('structTitle', 'ساختار سازمانی');
    setText('structSubtitle', 'مدیریت واحدها و پست‌های سازمان شما');
    document.getElementById('structBackBtn').classList.add('hidden');
    loadDepts();
    loadPositions();
  }

  // ─── Departments ────────────────────────────────────────────────
  async function loadDepts() {
    const tbody = document.getElementById('deptsTableBody');
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const items = await api.get(`/departments/?org_id=${state.orgId}`);
      state.depts = items || [];
      populateDeptFilter();
      if (!state.depts.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--gray-400);">واحدی ثبت نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = renderDeptRows(state.depts);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function renderDeptRows(items) {
    const byParent = {};
    items.forEach(d => { const k = d.parent_id || '__root__'; (byParent[k] ||= []).push(d); });
    let html = '';
    const visited = new Set();
    (function walk(parentKey, depth) {
      (byParent[parentKey] || []).forEach(d => {
        if (visited.has(d.id)) return;
        visited.add(d.id);
        const prefix = depth > 0 ? `<span style="color:var(--gray-300);">${'—'.repeat(depth)} </span>` : '';
        html += `
          <tr>
            <td style="padding-right:${16 + depth * 20}px;font-weight:500;">${prefix}${esc(d.name)}</td>
            <td style="color:var(--gray-500);">${d.manager_name ? esc(d.manager_name) : '—'}</td>
            <td>${numFa(d.user_count)}</td>
            <td>${statusBadge(d.is_active)}</td>
            <td>
              <div style="display:flex;gap:4px;flex-wrap:wrap;">
                <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="StructurePage.openEditDept('${d.id}')">ویرایش</button>
                <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-dept" data-id="${d.id}" data-title="${esc(d.name)}">حذف</button>
              </div>
            </td>
          </tr>`;
        walk(d.id, depth + 1);
      });
    })('__root__', 0);
    return html;
  }

  function populateDeptFilter() {
    const sel = document.getElementById('posDeptFilter');
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '<option value="">همه واحدها</option>' +
      state.depts.map(d => `<option value="${d.id}" ${d.id === cur ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
  }

  function populateParentDeptSelect(selectedId, excludeId) {
    const sel = document.getElementById('d-parent');
    sel.innerHTML = '<option value="">— بدون واحد مادر —</option>' +
      state.depts.filter(d => d.id !== excludeId)
        .map(d => `<option value="${d.id}" ${d.id === selectedId ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
  }

  function openCreateDept() {
    document.getElementById('deptModalTitle').textContent = 'واحد سازمانی جدید';
    document.getElementById('d-id').value = '';
    document.getElementById('d-name').value = '';
    document.getElementById('d-desc').value = '';
    document.getElementById('d-order').value = '0';
    populateParentDeptSelect('', '');
    openModal('modal-dept');
  }

  function openEditDept(id) {
    const d = state.depts.find(x => x.id === id);
    if (!d) return;
    document.getElementById('deptModalTitle').textContent = 'ویرایش واحد سازمانی';
    document.getElementById('d-id').value = d.id;
    document.getElementById('d-name').value = d.name || '';
    document.getElementById('d-desc').value = d.description || '';
    document.getElementById('d-order').value = d.order_index ?? 0;
    populateParentDeptSelect(d.parent_id, d.id);
    openModal('modal-dept');
  }

  async function saveDept() {
    const id = document.getElementById('d-id').value;
    const name = document.getElementById('d-name').value.trim();
    if (!name) { toastError('نام واحد اجباری است'); return; }
    const payload = {
      name,
      description: document.getElementById('d-desc').value.trim() || null,
      parent_id: document.getElementById('d-parent').value || null,
      order_index: parseInt(document.getElementById('d-order').value, 10) || 0,
    };
    if (!id) payload.org_id = state.orgId;

    const btn = document.getElementById('btn-save-dept');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/departments/${id}`, payload); toastSuccess('واحد با موفقیت ویرایش شد'); }
      else { await api.post('/departments/', payload); toastSuccess('واحد با موفقیت ایجاد شد'); }
      closeModal('modal-dept');
      await loadDepts();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeDept(id, name) {
    confirmAction(
      `آیا مطمئن هستید که می‌خواهید واحد "${name}" را حذف کنید؟ زیرواحدها و کاربران مرتبط آزاد می‌شوند (حذف نمی‌شوند).`,
      async () => {
        await api.delete(`/departments/${id}`);
        toastSuccess('واحد با موفقیت حذف شد');
        await loadDepts();
        await loadPositions();
      }
    );
  }

  // ─── Positions ──────────────────────────────────────────────────
  async function loadPositions() {
    const tbody = document.getElementById('positionsTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    const deptFilter = document.getElementById('posDeptFilter')?.value || '';
    const p = new URLSearchParams({ org_id: state.orgId });
    if (deptFilter) p.set('dept_id', deptFilter);
    try {
      const items = await api.get(`/positions/?${p}`);
      state.positions = items || [];
      if (!state.positions.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--gray-400);">پستی ثبت نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = state.positions.map(pos => `
        <tr>
          <td style="font-weight:500;">${esc(pos.name)}</td>
          <td style="color:var(--gray-500);">${pos.dept_name ? esc(pos.dept_name) : '—'}</td>
          <td><span class="badge badge-manager">سطح ${numFa(pos.level)}</span></td>
          <td>${numFa(pos.user_count)}</td>
          <td>${statusBadge(pos.is_active)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="StructurePage.openEditPosition('${pos.id}')">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-position" data-id="${pos.id}" data-title="${esc(pos.name)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function populateDeptSelectForPosition(selectedId) {
    const sel = document.getElementById('p-dept');
    sel.innerHTML = '<option value="">— بدون واحد —</option>' +
      state.depts.map(d => `<option value="${d.id}" ${d.id === selectedId ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
  }

  function openCreatePosition() {
    document.getElementById('posModalTitle').textContent = 'پست سازمانی جدید';
    document.getElementById('p-id').value = '';
    document.getElementById('p-name').value = '';
    document.getElementById('p-desc').value = '';
    document.getElementById('p-level').value = '1';
    populateDeptSelectForPosition('');
    openModal('modal-position');
  }

  function openEditPosition(id) {
    const pos = state.positions.find(x => x.id === id);
    if (!pos) return;
    document.getElementById('posModalTitle').textContent = 'ویرایش پست سازمانی';
    document.getElementById('p-id').value = pos.id;
    document.getElementById('p-name').value = pos.name || '';
    document.getElementById('p-desc').value = pos.description || '';
    document.getElementById('p-level').value = pos.level;
    populateDeptSelectForPosition(pos.dept_id);
    openModal('modal-position');
  }

  async function savePosition() {
    const id = document.getElementById('p-id').value;
    const name = document.getElementById('p-name').value.trim();
    if (!name) { toastError('عنوان پست اجباری است'); return; }
    const payload = {
      name,
      description: document.getElementById('p-desc').value.trim() || null,
      dept_id: document.getElementById('p-dept').value || null,
      level: parseInt(document.getElementById('p-level').value, 10) || 1,
    };
    if (!id) payload.org_id = state.orgId;

    const btn = document.getElementById('btn-save-position');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/positions/${id}`, payload); toastSuccess('پست با موفقیت ویرایش شد'); }
      else { await api.post('/positions/', payload); toastSuccess('پست با موفقیت ایجاد شد'); }
      closeModal('modal-position');
      await loadPositions();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removePosition(id, name) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید پست "${name}" را حذف کنید؟`, async () => {
      await api.delete(`/positions/${id}`);
      toastSuccess('پست با موفقیت حذف شد');
      await loadPositions();
    });
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row Actions — به‌جای onclick اینلاین با نام کاربر ──────
  document.getElementById('deptsTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-dept"]');
    if (btn) removeDept(btn.dataset.id, btn.dataset.title);
  });
  document.getElementById('positionsTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-position"]');
    if (btn) removePosition(btn.dataset.id, btn.dataset.title);
  });

  return {
    openFor, loadOwn,
    openCreateDept, openEditDept, saveDept, removeDept,
    openCreatePosition, openEditPosition, savePosition, removePosition,
    loadPositions,
  };
})();
