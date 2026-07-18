// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «اطلاعیه‌ها» (تک‌فایل عکس/ویدیو) — org_admin/super_admin
// ════════════════════════════════════════════════════════════════════
// خارج از سیستم محتوای آموزشی (Content) — برای اطلاع‌رسانی سریع که در
// صفحه‌ی خانه‌ی کارمند، پیش از بخش‌های آموزشی نمایش داده می‌شود.

const AnnouncementsPage = (() => {
  const state = {
    page: 1, search: '', searchTimer: null, items: [],
    targetOrgId: null, depts: [], orgsLoaded: false,
  };

  async function load(page = state.page) {
    state.page = page;
    if (App.isSuperAdmin) await loadOrgFilterOptions();
    const tbody = document.getElementById('annTableBody');
    tbody.innerHTML = `<tr><td colspan="7" class="loading-row">در حال بارگذاری...</td></tr>`;
    const orgFilter = document.getElementById('annOrgFilter')?.value || '';
    const p = new URLSearchParams({ page, page_size: 20 });
    if (state.search) p.set('search', state.search);
    if (App.isSuperAdmin && orgFilter) p.set('org_id', orgFilter);
    try {
      const res = await api.get(`/announcements/?${p}`);
      state.items = res.items || [];
      setText('annTotalLabel', `مجموع ${numFa(res.total)} اطلاعیه`);
      if (!state.items.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--gray-400);">اطلاعیه‌ای ثبت نشده</td></tr>`;
        renderPagination('annPagination', res.page, res.total_pages, load);
        return;
      }
      tbody.innerHTML = state.items.map(a => `
        <tr>
          <td style="font-weight:500;">${esc(a.title)}</td>
          <td class="th-org" data-roles="super_admin" style="color:var(--gray-500);">${esc(a.org_name || '—')}</td>
          <td>${a.media_type === 'video' ? '🎬 ویدیو' : '🖼️ عکس'}</td>
          <td style="color:var(--gray-500);font-size:12px;">${fmtWindow(a)}</td>
          <td>${a.target_count > 0 ? `<span class="badge badge-manager">محدود (${numFa(a.target_count)})</span>` : `<span class="badge badge-active">کل سازمان</span>`}</td>
          <td>${statusBadge(a.is_active)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="AnnouncementsPage.openEdit('${a.id}')">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-ann" data-id="${a.id}" data-title="${esc(a.title)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
      renderPagination('annPagination', res.page, res.total_pages, load);
      Router.applyRoleVisibility(App.currentUser.role);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function fmtWindow(a) {
    if (!a.starts_at && !a.ends_at) return 'نامحدود';
    const s = a.starts_at ? fmtDate(a.starts_at) : '—';
    const e = a.ends_at ? fmtDate(a.ends_at) : '—';
    return `${s} تا ${e}`;
  }

  function searchDebounced() {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => { state.search = document.getElementById('annSearch').value.trim(); load(1); }, 350);
  }

  async function loadOrgFilterOptions() {
    const sel = document.getElementById('annOrgFilter');
    if (!sel || sel.dataset.loaded) return;
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">همه سازمان‌ها</option>' +
        orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
      sel.dataset.loaded = '1';
    } catch { /* غیرحیاتی — فقط فیلتر است */ }
  }

  async function loadOrgsForSelect(selectedId) {
    const sel = document.getElementById('ann-org-id');
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">— انتخاب سازمان —</option>' +
        orgs.map(o => `<option value="${o.id}" ${o.id === selectedId ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
    } catch { /* ignore */ }
  }

  // ─── Departments (برای چک‌باکس دسترسی) ─────────────────────────
  async function loadDepts(orgId) {
    if (!orgId) { state.depts = []; renderDeptChecks([]); return; }
    try {
      state.depts = await api.get(`/departments/?org_id=${orgId}`) || [];
    } catch (e) {
      state.depts = [];
    }
    renderDeptChecks([]);
  }

  function renderDeptChecks(selectedIds) {
    const wrap = document.getElementById('ann-dept-checks');
    if (!state.depts.length) {
      wrap.innerHTML = `<span style="color:var(--gray-400);font-size:12px;">واحدی ثبت نشده</span>`;
      return;
    }
    wrap.innerHTML = state.depts.map(d => `
      <label><input type="checkbox" value="${d.id}" ${selectedIds.includes(d.id) ? 'checked' : ''}> ${esc(d.name)}</label>
    `).join('');
  }

  function renderRoleChecks(selectedRoles) {
    document.querySelectorAll('#ann-role-checks input[type=checkbox]').forEach(cb => {
      cb.checked = selectedRoles.includes(cb.value);
    });
  }

  async function onOrgChange() {
    const orgId = document.getElementById('ann-org-id').value;
    state.targetOrgId = orgId || null;
    resetFileFields();
    await loadDepts(orgId);
    renderRoleChecks([]);
  }

  // ─── Create / Edit ──────────────────────────────────────────────
  function resetFileFields() {
    document.getElementById('ann-media-url').value = '';
    document.getElementById('ann-file-name').value = '';
    document.getElementById('ann-file-size').value = '';
    document.getElementById('ann-media-type').value = '';
    document.getElementById('ann-file-input').value = '';
    document.getElementById('ann-file-hint').textContent = 'فرمت‌های مجاز: JPG, PNG, WEBP, GIF, MP4, WEBM, MOV';
  }

  function toDatetimeLocal(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  async function openCreate() {
    document.getElementById('annModalTitle').textContent = 'اطلاعیه جدید';
    document.getElementById('ann-id').value = '';
    document.getElementById('ann-title').value = '';
    document.getElementById('ann-desc').value = '';
    document.getElementById('ann-starts').value = '';
    document.getElementById('ann-ends').value = '';
    document.getElementById('ann-is-active').checked = true;
    resetFileFields();
    renderRoleChecks([]);

    if (App.isSuperAdmin) {
      state.targetOrgId = null;
      await loadOrgsForSelect('');
      document.getElementById('ann-org-id').disabled = false;
      renderDeptChecks([]);
    } else {
      state.targetOrgId = App.currentUser.org_id;
      await loadDepts(state.targetOrgId);
    }
    openModal('modal-announcement');
  }

  async function openEdit(id) {
    let a;
    try { a = await api.get(`/announcements/${id}`); } catch (e) { toastError(e.message); return; }

    document.getElementById('annModalTitle').textContent = 'ویرایش اطلاعیه';
    document.getElementById('ann-id').value = a.id;
    document.getElementById('ann-title').value = a.title || '';
    document.getElementById('ann-desc').value = a.description || '';
    document.getElementById('ann-starts').value = toDatetimeLocal(a.starts_at);
    document.getElementById('ann-ends').value = toDatetimeLocal(a.ends_at);
    document.getElementById('ann-is-active').checked = !!a.is_active;
    document.getElementById('ann-media-url').value = a.media_url || '';
    document.getElementById('ann-file-name').value = a.file_name || '';
    document.getElementById('ann-file-size').value = a.file_size || '';
    document.getElementById('ann-media-type').value = a.media_type || '';
    document.getElementById('ann-file-input').value = '';
    document.getElementById('ann-file-hint').textContent = a.file_name
      ? `فایل فعلی: ${a.file_name}`
      : 'فرمت‌های مجاز: JPG, PNG, WEBP, GIF, MP4, WEBM, MOV';

    state.targetOrgId = a.org_id;
    if (App.isSuperAdmin) {
      await loadOrgsForSelect(a.org_id);
      document.getElementById('ann-org-id').disabled = true; // سازمان بعد از ساخت غیرقابل تغییر است
    }
    await loadDepts(a.org_id);

    const deptIds = (a.targets || []).filter(t => t.target_type === 'department').map(t => t.target_id);
    const roles = (a.targets || []).filter(t => t.target_type === 'role').map(t => t.target_id);
    renderDeptChecks(deptIds);
    renderRoleChecks(roles);
    openModal('modal-announcement');
  }

  async function onFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (!state.targetOrgId) { toastError('ابتدا سازمان را انتخاب کنید'); event.target.value = ''; return; }
    const hint = document.getElementById('ann-file-hint');
    hint.textContent = 'در حال آپلود...';
    try {
      const res = await api.upload(`/announcements/upload?org_id=${state.targetOrgId}`, file);
      document.getElementById('ann-media-url').value = res.url;
      document.getElementById('ann-file-name').value = res.filename || file.name;
      document.getElementById('ann-file-size').value = res.size || file.size;
      const isVideo = (res.content_type || file.type || '').startsWith('video/');
      document.getElementById('ann-media-type').value = isVideo ? 'video' : 'image';
      hint.textContent = `فایل آپلود شد: ${res.filename || file.name}`;
    } catch (e) {
      hint.textContent = 'فرمت‌های مجاز: JPG, PNG, WEBP, GIF, MP4, WEBM, MOV';
      toastError(e.message);
    }
  }

  function collectTargets() {
    const targets = [];
    document.querySelectorAll('#ann-dept-checks input:checked').forEach(cb => {
      targets.push({ target_type: 'department', target_id: cb.value });
    });
    document.querySelectorAll('#ann-role-checks input:checked').forEach(cb => {
      targets.push({ target_type: 'role', target_id: cb.value });
    });
    return targets;
  }

  function toIsoOrNull(localValue) {
    return localValue ? new Date(localValue).toISOString() : null;
  }

  async function save() {
    const id = document.getElementById('ann-id').value;
    const title = document.getElementById('ann-title').value.trim();
    const mediaUrl = document.getElementById('ann-media-url').value;
    if (App.isSuperAdmin && !id && !document.getElementById('ann-org-id').value) {
      toastError('انتخاب سازمان اجباری است'); return;
    }
    if (!title) { toastError('عنوان اطلاعیه اجباری است'); return; }
    if (!mediaUrl) { toastError('آپلود فایل اطلاعیه اجباری است'); return; }

    const payload = {
      title,
      description: document.getElementById('ann-desc').value.trim() || null,
      media_url: mediaUrl,
      media_type: document.getElementById('ann-media-type').value,
      file_name: document.getElementById('ann-file-name').value || null,
      file_size: parseInt(document.getElementById('ann-file-size').value, 10) || null,
      starts_at: toIsoOrNull(document.getElementById('ann-starts').value),
      ends_at: toIsoOrNull(document.getElementById('ann-ends').value),
      is_active: document.getElementById('ann-is-active').checked,
      targets: collectTargets(),
    };
    if (!id) payload.org_id = state.targetOrgId;

    const btn = document.getElementById('btn-save-announcement');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/announcements/${id}`, payload); toastSuccess('اطلاعیه با موفقیت ویرایش شد'); }
      else { await api.post('/announcements/', payload); toastSuccess('اطلاعیه با موفقیت ثبت شد'); }
      closeModal('modal-announcement');
      await load(state.page);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function remove(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید اطلاعیه "${title}" را حذف کنید؟`, async () => {
      await api.delete(`/announcements/${id}`);
      toastSuccess('اطلاعیه با موفقیت حذف شد');
      await load(state.page);
    });
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row Actions — به‌جای onclick اینلاین با عنوان کاربر ────
  // دلیل در content.js توضیح داده شده: esc() فقط HTML را می‌بندد، نه
  // فرار از رشته‌ی جاوااسکریپت داخل onclick را.
  document.getElementById('annTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-ann"]');
    if (btn) remove(btn.dataset.id, btn.dataset.title);
  });

  return {
    load, searchDebounced, onOrgChange, onFileSelected,
    openCreate, openEdit, save, remove,
  };
})();
