// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «مدیریت محتوا» (course / article / podcast / book)
// ════════════════════════════════════════════════════════════════════
// org_admin/super_admin: ساخت/ویرایش/حذف محتوا + آیتم‌های داخل آن.
// همیشه محدود به سازمان خودشان (بک‌اند enforce می‌کند).

const TYPE_LABELS = { course: 'دوره', article: 'مقاله', podcast: 'پادکست', book: 'کتاب' };
const STATUS_LABELS = { draft: 'پیش‌نویس', published: 'منتشرشده', archived: 'بایگانی‌شده' };
const ITEM_TYPE_LABELS = { text: 'متن', video: 'ویدیو', pdf: 'PDF', image: 'تصویر', link: 'لینک', file: 'فایل', quiz_ref: 'آزمون' };
const ITEM_TYPE_ICONS = { text: '📄', video: '🎬', pdf: '📕', image: '🖼️', link: '🔗', file: '📎', quiz_ref: '📝' };

const ContentPage = (() => {
  const state = {
    type: 'course', page: 1, search: '', status: '',
    items: [], total: 0, totalPages: 1,
    // مودال آیتم‌ها
    activeContent: null, activeItems: [],
  };
  let searchTimer = null;

  function typeBadge(type) {
    return `<span class="badge badge-type-${type}">${TYPE_LABELS[type] || type}</span>`;
  }
  function statusBadge(s) {
    return `<span class="badge badge-${s}">${STATUS_LABELS[s] || s}</span>`;
  }

  // ─── Entry point از سایدبار (submenu محتوا) ────────────────────
  function goto(type) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-content').classList.add('active');
    document.querySelectorAll('.sidebar-nav [data-page]').forEach(el =>
      el.classList.toggle('active', el.dataset.page === 'content'));
    document.getElementById('headerTitle').textContent = 'مدیریت محتوا';
    setType(type);
  }

  // ─── Tabs / Load ────────────────────────────────────────────────
  function setType(type) {
    state.type = type;
    state.page = 1;
    document.querySelectorAll('#contentTabs .tab-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.type === type));
    load(1);
  }

  async function load(page = state.page) {
    state.page = page;
    state.status = document.getElementById('contentStatusFilter')?.value || '';
    const tbody = document.getElementById('contentTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    const p = new URLSearchParams({ page, page_size: 10, type: state.type });
    if (state.search) p.set('search', state.search);
    if (state.status) p.set('status', state.status);
    try {
      const res = await api.get(`/contents/?${p}`);
      state.items = res.items || [];
      state.total = res.total || 0;
      state.totalPages = res.total_pages || 1;
      setText('contentTotalLabel', `${numFa(state.total)} ${TYPE_LABELS[state.type]} یافت شد`);
      renderTable();
      renderPagination('contentPagination', state.page, state.totalPages, load);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function searchDebounced() {
    state.search = document.getElementById('contentSearch').value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load(1), 400);
  }

  function renderTable() {
    const tbody = document.getElementById('contentTableBody');
    if (!state.items.length) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon">🗂️</div>هنوز محتوایی از نوع «${TYPE_LABELS[state.type]}» ثبت نشده</div></td></tr>`;
      return;
    }
    const canEdit = App.isSuperAdmin || App.isOrgAdmin;
    tbody.innerHTML = state.items.map(c => `
      <tr>
        <td style="font-weight:600;">${esc(c.title)}</td>
        <td>${typeBadge(c.type)}</td>
        <td>${statusBadge(c.status)}</td>
        <td>${numFa(c.total_items_count)} آیتم</td>
        <td style="color:var(--gray-500);">${fmtDate(c.created_at)}</td>
        <td>
          <div style="display:flex;gap:4px;flex-wrap:wrap;">
            <button class="btn-action" style="background:var(--primary-light);color:var(--primary);" onclick="ContentPage.openItemsModal('${c.id}')">آیتم‌ها</button>
            ${canEdit ? `<button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="ContentPage.openEdit('${c.id}')">ویرایش</button>` : ''}
            ${canEdit ? `<button class="btn-action" style="background:#FEF2F2;color:#DC2626;" onclick="ContentPage.remove('${c.id}','${esc(c.title)}')">حذف</button>` : ''}
          </div>
        </td>
      </tr>`).join('');
  }

  // ─── Create / Edit Content ──────────────────────────────────────
  function openCreate() {
    document.getElementById('contentModalTitle').textContent = `${TYPE_LABELS[state.type]} جدید`;
    document.getElementById('c-id').value = '';
    document.getElementById('c-title').value = '';
    document.getElementById('c-type').value = state.type;
    document.getElementById('c-status').value = 'draft';
    document.getElementById('c-level').value = '';
    document.getElementById('c-author').value = '';
    document.getElementById('c-desc').value = '';
    document.getElementById('c-tags').value = '';
    document.getElementById('c-duration').value = '';
    document.getElementById('c-featured').checked = false;
    document.getElementById('c-thumb-url').value = '';
    setUploadName('c-thumb-name', '');
    openModal('modal-content');
  }

  function openEdit(id) {
    const c = state.items.find(x => x.id === id);
    if (!c) return;
    document.getElementById('contentModalTitle').textContent = 'ویرایش محتوا';
    document.getElementById('c-id').value = c.id;
    document.getElementById('c-title').value = c.title || '';
    document.getElementById('c-type').value = c.type;
    document.getElementById('c-status').value = c.status;
    document.getElementById('c-level').value = c.level || '';
    document.getElementById('c-author').value = c.author || '';
    document.getElementById('c-desc').value = c.description || '';
    document.getElementById('c-tags').value = (c.tags || []).join('، ');
    document.getElementById('c-duration').value = c.total_duration_min ?? '';
    document.getElementById('c-featured').checked = !!c.is_featured;
    document.getElementById('c-thumb-url').value = c.thumbnail_url || '';
    setUploadName('c-thumb-name', c.thumbnail_url ? 'تصویر فعلی ثبت شده' : '');
    openModal('modal-content');
  }

  async function save() {
    const id = document.getElementById('c-id').value;
    const title = document.getElementById('c-title').value.trim();
    if (!title) { toastError('عنوان محتوا اجباری است'); return; }

    const tagsRaw = document.getElementById('c-tags').value.trim();
    const payload = {
      title,
      description: document.getElementById('c-desc').value.trim() || null,
      level: document.getElementById('c-level').value || null,
      author: document.getElementById('c-author').value.trim() || null,
      status: document.getElementById('c-status').value,
      tags: tagsRaw ? tagsRaw.split(/[،,]/).map(t => t.trim()).filter(Boolean) : [],
      total_duration_min: document.getElementById('c-duration').value ? parseInt(document.getElementById('c-duration').value, 10) : null,
      is_featured: document.getElementById('c-featured').checked,
      thumbnail_url: document.getElementById('c-thumb-url').value || null,
    };
    if (!id) payload.type = document.getElementById('c-type').value;

    const btn = document.getElementById('btn-save-content');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/contents/${id}`, payload); toastSuccess('محتوا با موفقیت ویرایش شد'); }
      else { await api.post('/contents/', payload); toastSuccess('محتوا با موفقیت ایجاد شد'); }
      closeModal('modal-content');
      await load(id ? state.page : 1);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function remove(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید "${title}" را حذف کنید؟ تمام آیتم‌های داخل آن نیز حذف می‌شوند.`, async () => {
      await api.delete(`/contents/${id}`);
      toastSuccess('محتوا با موفقیت حذف شد');
      await load(1);
    });
  }

  async function uploadThumbnail(inputEl) {
    const file = inputEl.files?.[0];
    if (!file) return;
    try {
      const res = await api.upload('/contents/upload', file);
      document.getElementById('c-thumb-url').value = res.url;
      setUploadName('c-thumb-name', file.name, true);
      toastSuccess('تصویر با موفقیت آپلود شد');
    } catch (e) { toastError(e.message); }
    finally { inputEl.value = ''; }
  }

  // ─── Items Modal ────────────────────────────────────────────────
  async function openItemsModal(contentId) {
    const c = state.items.find(x => x.id === contentId);
    state.activeContent = contentId;
    document.getElementById('itemsModalTitle').textContent = c ? `آیتم‌های «${c.title}»` : 'آیتم‌های محتوا';
    openModal('modal-content-items');
    await loadItems();
  }

  async function loadItems() {
    const wrap = document.getElementById('contentItemsList');
    wrap.innerHTML = `<div class="loading-row" style="padding:20px;text-align:center;">در حال بارگذاری...</div>`;
    try {
      const detail = await api.get(`/contents/${state.activeContent}`);
      state.activeItems = detail.items || [];
      renderItems();
    } catch (e) {
      wrap.innerHTML = `<div style="color:var(--danger);text-align:center;padding:20px;">خطا در بارگذاری: ${esc(e.message)}</div>`;
    }
  }

  function renderItems() {
    const wrap = document.getElementById('contentItemsList');
    if (!state.activeItems.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📭</div>هنوز آیتمی اضافه نشده</div>`;
      return;
    }
    const canEdit = App.isSuperAdmin || App.isOrgAdmin;
    wrap.innerHTML = state.activeItems.map((it, idx) => `
      <div class="item-row">
        <div class="item-row-order">${numFa(idx + 1)}</div>
        <div class="item-row-icon">${ITEM_TYPE_ICONS[it.type] || '📄'}</div>
        <div class="item-row-info">
          <div class="item-row-title">${esc(it.title)}</div>
          <div class="item-row-meta">${ITEM_TYPE_LABELS[it.type] || it.type}${it.duration_min ? ' • ' + numFa(it.duration_min) + ' دقیقه' : ''}${it.is_free ? ' • رایگان' : ''}</div>
        </div>
        <div class="item-row-actions">
          ${canEdit ? `<button class="btn-icon" title="ویرایش" onclick="ContentPage.openEditItem('${it.id}')">✎</button>` : ''}
          ${canEdit ? `<button class="btn-icon" title="حذف" onclick="ContentPage.removeItem('${it.id}','${esc(it.title)}')">🗑</button>` : ''}
        </div>
      </div>`).join('');
  }

  function toggleItemFields() {
    const type = document.getElementById('i-type').value;
    document.getElementById('i-body-wrap').classList.toggle('hidden', type !== 'text');
    document.getElementById('i-upload-wrap').classList.toggle('hidden', !['video', 'pdf', 'image', 'file'].includes(type));
    document.getElementById('i-link-wrap').classList.toggle('hidden', type !== 'link');
    document.getElementById('i-quiz-wrap').classList.toggle('hidden', type !== 'quiz_ref');
  }

  function openCreateItem() {
    document.getElementById('itemModalTitle').textContent = 'آیتم جدید';
    document.getElementById('i-id').value = '';
    document.getElementById('i-title').value = '';
    document.getElementById('i-type').value = 'text';
    document.getElementById('i-body').value = '';
    document.getElementById('i-media-url').value = '';
    document.getElementById('i-link-url').value = '';
    document.getElementById('i-quiz-id').value = '';
    document.getElementById('i-duration').value = '';
    document.getElementById('i-order').value = state.activeItems.length;
    document.getElementById('i-free').checked = true;
    setUploadName('i-upload-name', '');
    toggleItemFields();
    openModal('modal-item');
  }

  function openEditItem(id) {
    const it = state.activeItems.find(x => x.id === id);
    if (!it) return;
    document.getElementById('itemModalTitle').textContent = 'ویرایش آیتم';
    document.getElementById('i-id').value = it.id;
    document.getElementById('i-title').value = it.title || '';
    document.getElementById('i-type').value = it.type;
    document.getElementById('i-body').value = it.body || '';
    document.getElementById('i-media-url').value = it.type === 'link' ? '' : (it.media_url || '');
    document.getElementById('i-link-url').value = it.type === 'link' ? (it.media_url || '') : '';
    document.getElementById('i-quiz-id').value = it.quiz_id || '';
    document.getElementById('i-duration').value = it.duration_min ?? '';
    document.getElementById('i-order').value = it.order_index ?? 0;
    document.getElementById('i-free').checked = !!it.is_free;
    setUploadName('i-upload-name', it.media_url && it.type !== 'link' ? 'فایل فعلی ثبت شده' : '');
    toggleItemFields();
    openModal('modal-item');
  }

  async function uploadItemMedia(inputEl) {
    const file = inputEl.files?.[0];
    if (!file) return;
    try {
      const res = await api.upload('/contents/upload', file);
      document.getElementById('i-media-url').value = res.url;
      setUploadName('i-upload-name', file.name, true);
      toastSuccess('فایل با موفقیت آپلود شد');
    } catch (e) { toastError(e.message); }
    finally { inputEl.value = ''; }
  }

  async function saveItem() {
    const id = document.getElementById('i-id').value;
    const title = document.getElementById('i-title').value.trim();
    if (!title) { toastError('عنوان آیتم اجباری است'); return; }
    const type = document.getElementById('i-type').value;
    const mediaUrl = type === 'link'
      ? document.getElementById('i-link-url').value.trim() || null
      : document.getElementById('i-media-url').value || null;

    const payload = {
      title,
      type,
      body: type === 'text' ? (document.getElementById('i-body').value.trim() || null) : null,
      media_url: mediaUrl,
      quiz_id: type === 'quiz_ref' ? (document.getElementById('i-quiz-id').value.trim() || null) : null,
      duration_min: document.getElementById('i-duration').value ? parseInt(document.getElementById('i-duration').value, 10) : null,
      order_index: parseInt(document.getElementById('i-order').value, 10) || 0,
      is_free: document.getElementById('i-free').checked,
    };

    const btn = document.getElementById('btn-save-item');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/contents/items/${id}`, payload); toastSuccess('آیتم با موفقیت ویرایش شد'); }
      else { await api.post(`/contents/${state.activeContent}/items`, payload); toastSuccess('آیتم با موفقیت اضافه شد'); }
      closeModal('modal-item');
      await loadItems();
      await load(state.page); // به‌روزرسانی تعداد آیتم در جدول اصلی
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeItem(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید آیتم "${title}" را حذف کنید؟`, async () => {
      await api.delete(`/contents/items/${id}`);
      toastSuccess('آیتم با موفقیت حذف شد');
      await loadItems();
      await load(state.page);
    });
  }

  // ─── Helpers ────────────────────────────────────────────────────
  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
  function setUploadName(id, name, hasFile = !!name) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = name || 'فایلی انتخاب نشده';
    el.classList.toggle('has-file', hasFile);
  }

  return {
    goto, setType, load, searchDebounced,
    openCreate, openEdit, save, remove, uploadThumbnail,
    openItemsModal, loadItems,
    toggleItemFields, openCreateItem, openEditItem, uploadItemMedia, saveItem, removeItem,
  };
})();
