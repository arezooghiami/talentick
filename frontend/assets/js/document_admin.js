// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «کتابخانه اسناد» (دسته‌بندی‌ها + اسناد)
// ════════════════════════════════════════════════════════════════════
// super_admin: از طریق دکمه‌ی «کتابخانه اسناد» روی هر ردیف در صفحه‌ی
//              «شرکت‌ها» باز می‌شود (DocumentsPage.openFor(orgId, orgName)).
// org_admin/manager: مستقیماً از منوی سایدبار، همیشه روی سازمان خودشان.

const DocumentsPage = (() => {
  const state = {
    orgId: null, orgName: '',
    categories: [], depts: [], docs: [], page: 1, search: '', searchTimer: null,
  };

  /** super_admin از این مسیر وارد می‌شود (نه از Router.navigate معمولی). */
  function openFor(orgId, orgName) {
    state.orgId = orgId;
    state.orgName = orgName;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-documents').classList.add('active');
    document.querySelectorAll('.sidebar-nav [data-page]').forEach(el =>
      el.classList.toggle('active', el.dataset.page === 'orgs'));
    document.getElementById('headerTitle').textContent = 'کتابخانه اسناد';
    setText('docsTitle', `کتابخانه اسناد — ${orgName}`);
    setText('docsSubtitle', `مدیریت قوانین، آیین‌نامه‌ها و مستندات «${orgName}»`);
    document.getElementById('docsBackBtn').classList.remove('hidden');
    load();
  }

  /** org_admin/manager — صدا زده می‌شود توسط Router.register('documents', ...) */
  function loadOwn() {
    state.orgId = App.currentUser.org_id;
    state.orgName = '';
    setText('docsTitle', 'کتابخانه اسناد');
    setText('docsSubtitle', 'مدیریت قوانین، آیین‌نامه‌ها و مستندات سازمان شما');
    document.getElementById('docsBackBtn').classList.add('hidden');
    load();
  }

  async function load() {
    await Promise.all([loadCategories(), loadDepts()]);
    await loadDocs(1);
  }

  // ─── Categories ─────────────────────────────────────────────────
  async function loadCategories() {
    const tbody = document.getElementById('docCategoriesTableBody');
    tbody.innerHTML = `<tr><td colspan="3" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const items = await api.get(`/documents/categories?org_id=${state.orgId}`);
      state.categories = items || [];
      populateCategoryFilter();
      populateCategorySelect();
      if (!state.categories.length) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;padding:30px;color:var(--gray-400);">دسته‌ای ثبت نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = state.categories.map(c => `
        <tr>
          <td style="font-weight:500;">${esc(c.name)}</td>
          <td>${numFa(c.document_count)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="DocumentsPage.openEditCategory('${c.id}')">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-doc-category" data-id="${c.id}" data-title="${esc(c.name)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function populateCategoryFilter() {
    const sel = document.getElementById('docCategoryFilter');
    const cur = sel.value;
    sel.innerHTML = '<option value="">همه دسته‌ها</option>' +
      state.categories.map(c => `<option value="${c.id}" ${c.id === cur ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  }

  function populateCategorySelect(selectedId) {
    const sel = document.getElementById('doc-category');
    sel.innerHTML = '<option value="">— بدون دسته —</option>' +
      state.categories.map(c => `<option value="${c.id}" ${c.id === selectedId ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  }

  function openCreateCategory() {
    document.getElementById('docCategoryModalTitle').textContent = 'دسته‌بندی جدید';
    document.getElementById('dc-id').value = '';
    document.getElementById('dc-name').value = '';
    document.getElementById('dc-order').value = '0';
    openModal('modal-doc-category');
  }

  function openEditCategory(id) {
    const c = state.categories.find(x => x.id === id);
    if (!c) return;
    document.getElementById('docCategoryModalTitle').textContent = 'ویرایش دسته‌بندی';
    document.getElementById('dc-id').value = c.id;
    document.getElementById('dc-name').value = c.name || '';
    document.getElementById('dc-order').value = c.order_index ?? 0;
    openModal('modal-doc-category');
  }

  async function saveCategory() {
    const id = document.getElementById('dc-id').value;
    const name = document.getElementById('dc-name').value.trim();
    if (!name) { toastError('نام دسته اجباری است'); return; }
    const payload = { name, order_index: parseInt(document.getElementById('dc-order').value, 10) || 0 };
    if (!id) payload.org_id = state.orgId;

    const btn = document.getElementById('btn-save-doc-category');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/documents/categories/${id}`, payload); toastSuccess('دسته با موفقیت ویرایش شد'); }
      else { await api.post('/documents/categories', payload); toastSuccess('دسته با موفقیت ایجاد شد'); }
      closeModal('modal-doc-category');
      await loadCategories();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeCategory(id, name) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید دسته "${name}" را حذف کنید؟ اسناد آن حذف نمی‌شوند — فقط بدون دسته می‌مانند.`, async () => {
      await api.delete(`/documents/categories/${id}`);
      toastSuccess('دسته با موفقیت حذف شد');
      await loadCategories();
      await loadDocs(state.page);
    });
  }

  // ─── Departments (برای چک‌باکس دسترسی) ─────────────────────────
  async function loadDepts() {
    try {
      state.depts = await api.get(`/departments/?org_id=${state.orgId}`) || [];
    } catch (e) {
      state.depts = [];
    }
  }

  function renderDeptChecks(selectedIds) {
    const wrap = document.getElementById('doc-dept-checks');
    if (!state.depts.length) {
      wrap.innerHTML = `<span style="color:var(--gray-400);font-size:12px;">واحدی ثبت نشده</span>`;
      return;
    }
    wrap.innerHTML = state.depts.map(d => `
      <label><input type="checkbox" value="${d.id}" ${selectedIds.includes(d.id) ? 'checked' : ''}> ${esc(d.name)}</label>
    `).join('');
  }

  function renderRoleChecks(selectedRoles) {
    document.querySelectorAll('#doc-role-checks input[type=checkbox]').forEach(cb => {
      cb.checked = selectedRoles.includes(cb.value);
    });
  }

  // ─── Documents ──────────────────────────────────────────────────
  function searchDebounced() {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => {
      state.search = document.getElementById('docSearch').value.trim();
      loadDocs(1);
    }, 350);
  }

  async function loadDocs(page = 1) {
    state.page = page;
    const tbody = document.getElementById('docsTableBody');
    tbody.innerHTML = `<tr><td colspan="7" class="loading-row">در حال بارگذاری...</td></tr>`;
    const categoryId = document.getElementById('docCategoryFilter')?.value || '';
    const p = new URLSearchParams({ page, page_size: 20, org_id: state.orgId });
    if (state.search) p.set('search', state.search);
    if (categoryId) p.set('category_id', categoryId);
    try {
      const res = await api.get(`/documents/?${p}`);
      state.docs = res.items || [];
      if (!state.docs.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--gray-400);">سندی ثبت نشده</td></tr>`;
        renderPagination('docsPagination', res.page, res.total_pages, loadDocs);
        return;
      }
      tbody.innerHTML = state.docs.map(d => `
        <tr>
          <td style="font-weight:500;">${esc(d.title)}</td>
          <td style="color:var(--gray-500);">${d.category_name ? esc(d.category_name) : '—'}</td>
          <td><a href="${esc(d.file_url)}" target="_blank" rel="noopener" style="color:var(--primary);">${esc((d.file_type || '').toUpperCase() || 'فایل')}</a></td>
          <td>${d.target_count > 0 ? `<span class="badge badge-manager">محدود (${numFa(d.target_count)})</span>` : `<span class="badge badge-active">کل سازمان</span>`}</td>
          <td style="color:var(--gray-500);">${d.uploaded_by_name ? esc(d.uploaded_by_name) : '—'}</td>
          <td style="color:var(--gray-500);">${fmtDate(d.created_at)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="DocumentsPage.openEditDoc('${d.id}')">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-doc" data-id="${d.id}" data-title="${esc(d.title)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
      renderPagination('docsPagination', res.page, res.total_pages, loadDocs);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function resetFileFields() {
    document.getElementById('doc-file-url').value = '';
    document.getElementById('doc-file-name').value = '';
    document.getElementById('doc-file-size').value = '';
    document.getElementById('doc-file-type').value = '';
    document.getElementById('doc-file-input').value = '';
    document.getElementById('doc-file-hint').textContent = 'فرمت‌های مجاز: PDF, Word, PowerPoint, Excel';
  }

  function openCreateDoc() {
    document.getElementById('documentModalTitle').textContent = 'سند جدید';
    document.getElementById('doc-id').value = '';
    document.getElementById('doc-title').value = '';
    document.getElementById('doc-desc').value = '';
    populateCategorySelect('');
    resetFileFields();
    renderDeptChecks([]);
    renderRoleChecks([]);
    openModal('modal-document');
  }

  async function openEditDoc(id) {
    const d = state.docs.find(x => x.id === id);
    if (!d) return;
    let detail;
    try { detail = await api.get(`/documents/${id}`); } catch (e) { toastError(e.message); return; }

    document.getElementById('documentModalTitle').textContent = 'ویرایش سند';
    document.getElementById('doc-id').value = detail.id;
    document.getElementById('doc-title').value = detail.title || '';
    document.getElementById('doc-desc').value = detail.description || '';
    populateCategorySelect(detail.category_id || '');
    document.getElementById('doc-file-url').value = detail.file_url || '';
    document.getElementById('doc-file-name').value = detail.file_name || '';
    document.getElementById('doc-file-size').value = detail.file_size || '';
    document.getElementById('doc-file-type').value = detail.file_type || '';
    document.getElementById('doc-file-input').value = '';
    document.getElementById('doc-file-hint').textContent = detail.file_name
      ? `فایل فعلی: ${detail.file_name}`
      : 'فرمت‌های مجاز: PDF, Word, PowerPoint, Excel';

    const deptIds = (detail.targets || []).filter(t => t.target_type === 'department').map(t => t.target_id);
    const roles = (detail.targets || []).filter(t => t.target_type === 'role').map(t => t.target_id);
    renderDeptChecks(deptIds);
    renderRoleChecks(roles);
    openModal('modal-document');
  }

  async function onFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;
    const hint = document.getElementById('doc-file-hint');
    hint.textContent = 'در حال آپلود...';
    try {
      const res = await api.upload(`/documents/upload?org_id=${state.orgId}`, file);
      document.getElementById('doc-file-url').value = res.url;
      document.getElementById('doc-file-name').value = res.filename || file.name;
      document.getElementById('doc-file-size').value = res.size || file.size;
      const ext = (file.name.split('.').pop() || '').toLowerCase();
      document.getElementById('doc-file-type').value = ext;
      hint.textContent = `فایل آپلود شد: ${res.filename || file.name}`;
    } catch (e) {
      hint.textContent = 'فرمت‌های مجاز: PDF, Word, PowerPoint, Excel';
      toastError(e.message);
    }
  }

  function collectTargets() {
    const targets = [];
    document.querySelectorAll('#doc-dept-checks input:checked').forEach(cb => {
      targets.push({ target_type: 'department', target_id: cb.value });
    });
    document.querySelectorAll('#doc-role-checks input:checked').forEach(cb => {
      targets.push({ target_type: 'role', target_id: cb.value });
    });
    return targets;
  }

  async function saveDoc() {
    const id = document.getElementById('doc-id').value;
    const title = document.getElementById('doc-title').value.trim();
    const fileUrl = document.getElementById('doc-file-url').value;
    if (!title) { toastError('عنوان سند اجباری است'); return; }
    if (!fileUrl) { toastError('آپلود فایل سند اجباری است'); return; }

    const payload = {
      title,
      description: document.getElementById('doc-desc').value.trim() || null,
      category_id: document.getElementById('doc-category').value || null,
      file_url: fileUrl,
      file_name: document.getElementById('doc-file-name').value || null,
      file_size: parseInt(document.getElementById('doc-file-size').value, 10) || null,
      file_type: document.getElementById('doc-file-type').value || null,
      targets: collectTargets(),
    };
    if (!id) payload.org_id = state.orgId;

    const btn = document.getElementById('btn-save-document');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/documents/${id}`, payload); toastSuccess('سند با موفقیت ویرایش شد'); }
      else { await api.post('/documents/', payload); toastSuccess('سند با موفقیت ثبت شد'); }
      closeModal('modal-document');
      await loadDocs(state.page);
      await loadCategories();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeDoc(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید سند "${title}" را حذف کنید؟`, async () => {
      await api.delete(`/documents/${id}`);
      toastSuccess('سند با موفقیت حذف شد');
      await loadDocs(state.page);
      await loadCategories();
    });
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row Actions — به‌جای onclick اینلاین با نام/عنوان کاربر ──
  document.getElementById('docCategoriesTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-doc-category"]');
    if (btn) removeCategory(btn.dataset.id, btn.dataset.title);
  });
  document.getElementById('docsTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-doc"]');
    if (btn) removeDoc(btn.dataset.id, btn.dataset.title);
  });

  return {
    openFor, loadOwn, loadDocs, searchDebounced,
    openCreateCategory, openEditCategory, saveCategory, removeCategory,
    openCreateDoc, openEditDoc, saveDoc, removeDoc, onFileSelected,
  };
})();
