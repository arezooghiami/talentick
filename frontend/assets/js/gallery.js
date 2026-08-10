// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «گالری» (مجموعه عکس) — org_admin/super_admin
// ════════════════════════════════════════════════════════════════════
// خارج از سیستم محتوای آموزشی (Content) — یک مجموعه عکس با عنوان،
// توضیحات، کاور و وضعیت فعال/غیرفعال. سوپر ادمین می‌تواند Public
// (بدون سازمان) یا مخصوص یک سازمان خاص تعریف کند.

const GalleryPage = (() => {
  const state = {
    page: 1, search: '', searchTimer: null, items: [],
    targetOrgId: null, photos: [],
  };

  // hydrateAuthedImages(): تعریف مشترک در utils.js

  async function load(page = state.page) {
    state.page = page;
    if (App.isSuperAdmin) await loadOrgFilterOptions();
    const tbody = document.getElementById('galTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    const orgFilter = document.getElementById('galOrgFilter')?.value || '';
    const p = new URLSearchParams({ page, page_size: 20 });
    if (state.search) p.set('search', state.search);
    if (App.isSuperAdmin && orgFilter) p.set('org_id', orgFilter);
    try {
      const res = await api.get(`/galleries/?${p}`);
      state.items = res.items || [];
      setText('galTotalLabel', `مجموع ${numFa(res.total)} گالری`);
      if (!state.items.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--gray-400);">گالری‌ای ثبت نشده</td></tr>`;
        renderPagination('galPagination', res.page, res.total_pages, load);
        return;
      }
      tbody.innerHTML = state.items.map(g => `
        <tr>
          <td>${g.cover_image_url ? `<img data-src="${esc(g.cover_image_url)}" alt="" style="width:44px;height:44px;object-fit:cover;border-radius:6px;background:var(--gray-100);">` : '<span style="color:var(--gray-300);">—</span>'}</td>
          <td style="font-weight:500;">${esc(g.title)}</td>
          <td class="th-org" data-roles="super_admin" style="color:var(--gray-500);">${esc(g.org_name || 'عمومی')}</td>
          <td>${numFa(g.photo_count)} عکس</td>
          <td>${statusBadge(g.is_active)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="GalleryPage.openEdit('${g.id}')">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-gal" data-id="${g.id}" data-title="${esc(g.title)}">حذف</button>
            </div>
          </td>
        </tr>`).join('');
      renderPagination('galPagination', res.page, res.total_pages, load);
      Router.applyRoleVisibility(App.currentUser.role);
      hydrateAuthedImages(tbody);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function searchDebounced() {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => { state.search = document.getElementById('galSearch').value.trim(); load(1); }, 350);
  }

  async function loadOrgFilterOptions() {
    const sel = document.getElementById('galOrgFilter');
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
    const sel = document.getElementById('gal-org-id');
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">— انتخاب سازمان —</option>' +
        orgs.map(o => `<option value="${o.id}" ${o.id === selectedId ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
    } catch { /* ignore */ }
  }

  function onPublicToggle() {
    const isPublic = document.getElementById('gal-is-public').checked;
    document.getElementById('gal-org-wrap').classList.toggle('hidden', isPublic);
    state.targetOrgId = isPublic ? null : (document.getElementById('gal-org-id').value || null);
  }

  function onOrgChange() {
    state.targetOrgId = document.getElementById('gal-org-id').value || null;
  }

  // ─── Cover ──────────────────────────────────────────────────────
  function renderCover(url) {
    document.getElementById('gal-cover-url').value = url || '';
    const preview = document.getElementById('gal-cover-preview');
    preview.innerHTML = url ? `<img data-src="${esc(url)}" alt="" style="width:120px;height:80px;object-fit:cover;border-radius:6px;background:var(--gray-100);">` : '';
    if (url) hydrateAuthedImages(preview);
  }

  async function onCoverSelected(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (!state.targetOrgId && !document.getElementById('gal-is-public').checked) {
      toastError('ابتدا سازمان را انتخاب کنید'); event.target.value = ''; return;
    }
    try {
      const res = await api.upload(coverUploadPath(), file);
      renderCover(res.url);
    } catch (e) { toastError(e.message); }
    finally { event.target.value = ''; }
  }

  // ─── Photos ─────────────────────────────────────────────────────
  function renderPhotos() {
    const wrap = document.getElementById('gal-photos-grid');
    if (!state.photos.length) {
      wrap.innerHTML = `<span style="color:var(--gray-400);font-size:12px;">عکسی افزوده نشده</span>`;
      return;
    }
    wrap.innerHTML = state.photos.map((p, i) => `
      <div class="gal-photo-thumb" style="position:relative;display:inline-block;margin:4px;">
        <img data-src="${esc(p.image_url)}" alt="" style="width:72px;height:72px;object-fit:cover;border-radius:6px;background:var(--gray-100);">
        <button type="button" class="btn-action" style="position:absolute;top:-6px;left:-6px;background:#FEF2F2;color:#DC2626;padding:2px 6px;" onclick="GalleryPage.removePhoto(${i})">✕</button>
      </div>`).join('');
    hydrateAuthedImages(wrap);
  }

  function removePhoto(index) {
    state.photos.splice(index, 1);
    renderPhotos();
  }

  function coverUploadPath() {
    return state.targetOrgId ? `/galleries/upload?org_id=${state.targetOrgId}` : '/galleries/upload';
  }

  async function onPhotosSelected(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    if (!state.targetOrgId && !document.getElementById('gal-is-public').checked) {
      toastError('ابتدا سازمان را انتخاب کنید'); event.target.value = ''; return;
    }
    for (const file of files) {
      try {
        const res = await api.upload(coverUploadPath(), file);
        state.photos.push({ image_url: res.url, order_index: state.photos.length });
      } catch (e) { toastError(e.message); }
    }
    renderPhotos();
    event.target.value = '';
  }

  // ─── Create / Edit ──────────────────────────────────────────────
  async function openCreate() {
    document.getElementById('galModalTitle').textContent = 'گالری جدید';
    document.getElementById('gal-id').value = '';
    document.getElementById('gal-title').value = '';
    document.getElementById('gal-desc').value = '';
    document.getElementById('gal-is-active').checked = true;
    document.getElementById('gal-cover-input').value = '';
    document.getElementById('gal-photos-input').value = '';
    state.photos = [];
    renderCover('');
    renderPhotos();

    const publicCheck = document.getElementById('gal-is-public');
    if (App.isSuperAdmin) {
      publicCheck.checked = false;
      publicCheck.disabled = false;
      state.targetOrgId = null;
      await loadOrgsForSelect('');
      document.getElementById('gal-org-id').disabled = false;
      onPublicToggle();
    } else {
      publicCheck.checked = false;
      publicCheck.disabled = true;
      document.getElementById('gal-org-wrap').classList.add('hidden');
      state.targetOrgId = App.currentUser.org_id;
    }
    openModal('modal-gallery');
  }

  async function openEdit(id) {
    let g;
    try { g = await api.get(`/galleries/${id}`); } catch (e) { toastError(e.message); return; }

    document.getElementById('galModalTitle').textContent = 'ویرایش گالری';
    document.getElementById('gal-id').value = g.id;
    document.getElementById('gal-title').value = g.title || '';
    document.getElementById('gal-desc').value = g.description || '';
    document.getElementById('gal-is-active').checked = !!g.is_active;
    document.getElementById('gal-cover-input').value = '';
    document.getElementById('gal-photos-input').value = '';
    renderCover(g.cover_image_url);
    state.photos = (g.photos || []).map(p => ({ image_url: p.image_url, order_index: p.order_index }));
    renderPhotos();

    state.targetOrgId = g.org_id;
    const publicCheck = document.getElementById('gal-is-public');
    publicCheck.checked = !g.org_id;
    publicCheck.disabled = true; // حالت Public/سازمان بعد از ساخت غیرقابل تغییر است
    if (App.isSuperAdmin) {
      await loadOrgsForSelect(g.org_id);
      document.getElementById('gal-org-id').disabled = true;
    }
    document.getElementById('gal-org-wrap').classList.toggle('hidden', !g.org_id);
    openModal('modal-gallery');
  }

  async function save() {
    const id = document.getElementById('gal-id').value;
    const title = document.getElementById('gal-title').value.trim();
    if (!title) { toastError('عنوان گالری اجباری است'); return; }
    const isPublic = document.getElementById('gal-is-public').checked;
    if (App.isSuperAdmin && !id && !isPublic && !document.getElementById('gal-org-id').value) {
      toastError('انتخاب سازمان اجباری است'); return;
    }

    const payload = {
      title,
      description: document.getElementById('gal-desc').value.trim() || null,
      cover_image_url: document.getElementById('gal-cover-url').value || null,
      is_active: document.getElementById('gal-is-active').checked,
      photos: state.photos.map((p, i) => ({ image_url: p.image_url, order_index: i })),
    };
    if (!id) {
      payload.is_public = isPublic;
      payload.org_id = isPublic ? null : state.targetOrgId;
    }

    const btn = document.getElementById('btn-save-gallery');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/galleries/${id}`, payload); toastSuccess('گالری با موفقیت ویرایش شد'); }
      else { await api.post('/galleries/', payload); toastSuccess('گالری با موفقیت ثبت شد'); }
      closeModal('modal-gallery');
      await load(state.page);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function remove(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید گالری "${title}" را حذف کنید؟`, async () => {
      await api.delete(`/galleries/${id}`);
      toastSuccess('گالری با موفقیت حذف شد');
      await load(state.page);
    });
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  document.getElementById('galTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-gal"]');
    if (btn) remove(btn.dataset.id, btn.dataset.title);
  });

  return {
    load, searchDebounced, onOrgChange, onPublicToggle,
    onCoverSelected, onPhotosSelected, removePhoto,
    openCreate, openEdit, save, remove,
  };
})();
