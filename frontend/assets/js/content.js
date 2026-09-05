// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «مدیریت محتوا» (course / article / podcast / book)
// ════════════════════════════════════════════════════════════════════
// org_admin/super_admin: ساخت/ویرایش/حذف محتوا + آیتم‌های داخل آن.
// همیشه محدود به سازمان خودشان (بک‌اند enforce می‌کند).
//
// فرم محتوا یک ویزارد ۳ تبی است — مطابق منطق استاندارد LMS:
//   تب ۱ «مشخصات»            → نوع محتوا و اطلاعات پایه (سازنده‌ی رکورد محتوا)
//   تب ۲ «دسترسی و کاور»      → وضعیت/کاور/انتشار هدف‌مند/قفل ترتیبی
//   تب ۳ «آیتم‌ها»            → برنامه‌ی درسی واقعی (چندین ویدیو/فایل/آزمون)
// در «ساخت محتوای جدید» تب‌ها به‌ترتیب باز می‌شوند (چون افزودن آیتم‌ها به
// content_id واقعی نیاز دارد که فقط بعد از تب ۱ ساخته می‌شود). در «ویرایش»
// هر سه تب بلافاصله باز و قابل‌جابه‌جایی آزادند.

const TYPE_LABELS = { course: 'دوره', article: 'مقاله', podcast: 'پادکست', book: 'کتاب' };
const STATUS_LABELS = { draft: 'پیش‌نویس', published: 'منتشرشده', archived: 'بایگانی‌شده' };
const ITEM_TYPE_LABELS = { text: 'متن', video: 'ویدیو', pdf: 'PDF', image: 'تصویر', link: 'لینک', file: 'فایل', quiz_ref: 'آزمون' };
const ITEM_TYPE_ICONS = { text: '📄', video: '🎬', pdf: '📕', image: '🖼️', link: '🔗', file: '📎', quiz_ref: '📝' };
const CTAB_ORDER = ['basic', 'access', 'items'];
const BULK_TYPE_BY_EXT = {
  mp4: 'video', webm: 'video', mov: 'video',
  pdf: 'pdf',
  jpg: 'image', jpeg: 'image', png: 'image', webp: 'image', gif: 'image',
};

// شناسه‌ی مجازی برای «دسته‌بندی عمومی» در انتخابگر سازمانِ مودال مدیریت دسته‌ها
const PUBLIC_ORG = '__public__';

const ContentPage = (() => {
  const state = {
    type: 'course', page: 1, search: '', status: '',
    items: [], total: 0, totalPages: 1,
    categories: [], modalCategories: [], categoryModalOrgId: null,
    categoryOptions: [], selectedCategories: new Set(),
    // ویزارد محتوا
    mode: null, contentId: null, activeTab: 'basic', maxUnlockedTab: 'basic',
    activeItems: [], quizzesLoaded: false,
    // انتشار هدف‌مند (targeting)
    orgs: [], orgsLoaded: false, targetOrgId: null,
    depts: [], positions: [],
    selectedDepts: new Set(), selectedPositions: new Set(), selectedUsers: new Map(),
    userSearchResults: [],
  };
  let searchTimer = null;
  let targetUserSearchTimer = null;

  function typeBadge(type) {
    return `<span class="badge badge-type-${type}">${TYPE_LABELS[type] || type}</span>`;
  }
  function statusBadge(s) {
    return `<span class="badge badge-${s}">${STATUS_LABELS[s] || s}</span>`;
  }

  // ─── Entry point از سایدبار (submenu محتوا) ────────────────────
  async function goto(type) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-content').classList.add('active');
    document.querySelectorAll('.sidebar-nav [data-page]').forEach(el =>
      el.classList.toggle('active', el.dataset.page === 'content'));
    document.getElementById('headerTitle').textContent = 'مدیریت محتوا';
    if (App.isSuperAdmin) await loadOrgFilterOptions();
    await loadCategories();
    setType(type);
  }

  async function loadOrgFilterOptions() {
    const sel = document.getElementById('contentOrgFilter');
    if (!sel || sel.dataset.loaded) return;
    try {
      const res = await api.get('/orgs/');
      const orgs = Array.isArray(res) ? res : (res.items || []);
      sel.innerHTML = '<option value="">همه سازمان‌ها</option>' +
        orgs.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
      sel.dataset.loaded = '1';
    } catch { /* غیرحیاتی — فقط فیلتر است */ }
  }

  function onOrgFilterChange() {
    loadCategories();
    load(1);
  }

  // ─── دسته‌بندی‌های محتوا: فیلتر بالای صفحه ─────────────────────────
  // org_admin: همیشه سازمان خودش — super_admin: سازمانِ فیلتر بالای صفحه؛
  // اگر «همه سازمان‌ها» انتخاب شده باشد (بدون org_id)، دسته‌بندی‌های همه‌ی
  // سازمان‌ها با هم نمایش داده می‌شود (هم‌راستا با لیست محتوا که در این
  // حالت هم محتوای همه سازمان‌ها را نشان می‌دهد). این فقط dropdown فیلتر
  // را پر می‌کند — مدیریت خودِ دسته‌ها در مودال جداگانه‌ای انجام می‌شود
  // (پایین‌تر) تا این صفحه شلوغ نشود.
  async function loadCategories() {
    const orgId = App.isSuperAdmin ? (document.getElementById('contentOrgFilter')?.value || '') : App.homeOrgId;
    try {
      const items = await api.get(orgId ? `/contents/categories?org_id=${orgId}` : '/contents/categories');
      state.categories = items || [];
      populateCategoryFilter();
    } catch { /* غیرحیاتی — فقط فیلتر است */ }
  }

  function populateCategoryFilter() {
    const sel = document.getElementById('contentCategoryFilter');
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '<option value="">همه دسته‌ها</option>' +
      state.categories.map(c => `<option value="${c.id}" ${c.id === cur ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  }

  // ─── مودال «دسته‌بندی‌های محتوا» — لیست + فرم ساخت/ویرایش ──────────
  // org_admin: همیشه سازمان خودش، بدون نیاز به انتخاب. super_admin: با
  // انتخابگر سازمان داخل خودِ مودال (پیش‌فرض = فیلتر بالای صفحه اگر
  // انتخاب شده باشد) — مستقل از فیلتر بالای صفحه تا تغییر سازمان داخل
  // مودال باعث تغییر لیست محتوای پشت مودال نشود.
  async function openCategoriesModal() {
    if (App.isSuperAdmin) {
      const preselect = document.getElementById('contentOrgFilter')?.value || PUBLIC_ORG;
      await populateCategoryManageOrgSelect(preselect);
      state.categoryModalOrgId = preselect;
    } else {
      state.categoryModalOrgId = App.homeOrgId;
    }
    showCategoryList();
    await loadCategoriesModalList();
    openModal('modal-content-categories');
  }

  async function ensureOrgsLoaded() {
    if (state.orgsLoaded) return true;
    try {
      const res = await api.get('/orgs/');
      state.orgs = Array.isArray(res) ? res : (res.items || []);
      state.orgsLoaded = true;
      return true;
    } catch {
      return false;
    }
  }

  async function populateCategoryManageOrgSelect(selectedId) {
    const sel = document.getElementById('cc-manage-org');
    if (!sel) return;
    const ok = await ensureOrgsLoaded();
    if (!ok) { sel.innerHTML = '<option value="">خطا در بارگذاری سازمان‌ها</option>'; return; }
    sel.innerHTML =
      `<option value="${PUBLIC_ORG}" ${selectedId === PUBLIC_ORG ? 'selected' : ''}>— عمومی (همه سازمان‌ها) —</option>` +
      state.orgs.map(o => `<option value="${o.id}" ${o.id === selectedId ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
  }

  function onCategoryManageOrgChange() {
    state.categoryModalOrgId = document.getElementById('cc-manage-org').value || PUBLIC_ORG;
    showCategoryList();
    loadCategoriesModalList();
  }

  async function loadCategoriesModalList() {
    const orgId = state.categoryModalOrgId;
    const tbody = document.getElementById('contentCategoriesTableBody');
    if (!orgId) {
      state.modalCategories = [];
      if (tbody) tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--gray-400);">ابتدا سازمان را از بالا انتخاب کنید</td></tr>`;
      return;
    }
    const isPublic = orgId === PUBLIC_ORG;
    if (tbody) tbody.innerHTML = `<tr><td colspan="3" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const url = isPublic ? '/contents/categories?scope=public' : `/contents/categories?org_id=${orgId}`;
      const items = await api.get(url);
      state.modalCategories = items || [];
      if (!tbody) return;
      if (!state.modalCategories.length) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--gray-400);">دسته‌ای ثبت نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = state.modalCategories.map(c => {
        // در نمای یک سازمان، دسته‌های عمومی فقط برای اطلاع نشان داده می‌شوند
        // (ویرایش/حذفشان از نمای «عمومی» انجام می‌شود).
        const readOnly = c.is_public && !isPublic;
        const actions = readOnly
          ? '<span style="color:var(--gray-400);font-size:12px;">دستهٔ عمومی</span>'
          : `<button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="ContentPage.openEditCategory('${c.id}')">ویرایش</button>
             <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-content-category" data-id="${c.id}" data-title="${esc(c.name)}">حذف</button>`;
        return `
        <tr>
          <td style="font-weight:500;">${esc(c.name)}${c.is_public ? ' <span class="badge" style="background:#EEF2FF;color:#4338CA;font-size:11px;padding:1px 6px;border-radius:6px;">عمومی</span>' : ''}</td>
          <td>${numFa(c.content_count)}</td>
          <td><div style="display:flex;gap:4px;flex-wrap:wrap;">${actions}</div></td>
        </tr>`;
      }).join('');
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function showCategoryList() {
    document.getElementById('cc-list-view').classList.remove('hidden');
    document.getElementById('cc-form-view').classList.add('hidden');
  }

  function showCategoryForm() {
    document.getElementById('cc-list-view').classList.add('hidden');
    document.getElementById('cc-form-view').classList.remove('hidden');
  }

  function hideCategoryForm() {
    showCategoryList();
  }

  function openCreateCategory() {
    if (!state.categoryModalOrgId) { toastError('ابتدا سازمان را از بالا انتخاب کنید'); return; }
    document.getElementById('cc-form-title').textContent =
      state.categoryModalOrgId === PUBLIC_ORG ? 'دستهٔ عمومی جدید' : 'دسته جدید';
    document.getElementById('cc-id').value = '';
    document.getElementById('cc-name').value = '';
    showCategoryForm();
  }

  function openEditCategory(id) {
    const c = state.modalCategories.find(x => x.id === id);
    if (!c) return;
    document.getElementById('cc-form-title').textContent = 'ویرایش دسته‌بندی';
    document.getElementById('cc-id').value = c.id;
    document.getElementById('cc-name').value = c.name || '';
    showCategoryForm();
  }

  async function saveCategory() {
    const id = document.getElementById('cc-id').value;
    const name = document.getElementById('cc-name').value.trim();
    if (!name) { toastError('نام دسته اجباری است'); return; }
    const payload = { name };
    if (!id) payload.org_id = state.categoryModalOrgId === PUBLIC_ORG ? null : state.categoryModalOrgId;

    const btn = document.getElementById('btn-save-content-category');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/contents/categories/${id}`, payload); toastSuccess('دسته با موفقیت ویرایش شد'); }
      else { await api.post('/contents/categories', payload); toastSuccess('دسته با موفقیت ایجاد شد'); }
      hideCategoryForm();
      await loadCategoriesModalList();
      await loadCategories();
      await load(state.page);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeCategory(id, name) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید دسته "${name}" را حذف کنید؟ محتوای این دسته حذف نمی‌شود — فقط بدون دسته می‌ماند.`, async () => {
      await api.delete(`/contents/categories/${id}`);
      toastSuccess('دسته با موفقیت حذف شد');
      await loadCategoriesModalList();
      await loadCategories();
      await load(state.page);
    });
  }

  // دراپ‌داون چندانتخابی و قابل‌جستجوی دسته‌بندی داخل ویزارد محتوا — مستقل از
  // فیلتر بالای صفحه، چون سازمانِ محتوا (c-org-id) می‌تواند با سازمانِ
  // انتخاب‌شده در فیلتر فرق کند. یک محتوا می‌تواند صفر، یک یا چند دسته داشته
  // باشد. با تعداد زیاد دسته، جستجو به‌جای اسکرول در چک‌باکس‌ها راحت‌تر است
  // (همان کامپوننت .ms استفاده‌شده برای واحدهای هدف آنبوردینگ).
  async function loadCategoryOptions(orgId) {
    closeCategoryDropdown();
    const searchEl = document.getElementById('c-category-search');
    if (searchEl) searchEl.value = '';
    try {
      // محتوای سازمانی: دسته‌های همان سازمان + دسته‌های عمومی.
      // محتوای عمومی (بدون سازمان): فقط دسته‌های عمومی.
      const url = orgId ? `/contents/categories?org_id=${orgId}` : '/contents/categories?scope=public';
      const items = await api.get(url);
      state.categoryOptions = items || [];
    } catch {
      state.categoryOptions = [];
    }
    renderCategoryValues();
    renderCategoryOptions();
  }

  function renderCategoryValues() {
    const box = document.getElementById('c-category-values');
    if (!box) return;
    if (!state.categoryOptions.length) {
      box.innerHTML = '<span class="ms-placeholder">دسته‌ای ثبت نشده</span>';
      return;
    }
    if (!state.selectedCategories.size) {
      box.innerHTML = '<span class="ms-placeholder">— بدون دسته —</span>';
      return;
    }
    const byId = new Map(state.categoryOptions.map(c => [c.id, c.name]));
    box.innerHTML = Array.from(state.selectedCategories).map(id => `
      <span class="ms-tag" title="${esc(byId.get(id) || '')}">
        <span>${esc(byId.get(id) || '—')}</span>
        <span class="ms-tag-x" data-role="c-category-untag" data-id="${esc(id)}">✕</span>
      </span>`).join('');
  }

  function renderCategoryOptions() {
    const box = document.getElementById('c-category-options');
    if (!box) return;
    if (!state.categoryOptions.length) {
      box.innerHTML = '<div class="ms-empty">دسته‌ای ثبت نشده</div>';
      return;
    }
    const q = (document.getElementById('c-category-search')?.value || '').trim();
    const list = q ? state.categoryOptions.filter(c => (c.name || '').includes(q)) : state.categoryOptions;
    box.innerHTML = list.length
      ? list.map(c => `
        <label class="ms-option">
          <input type="checkbox" data-role="c-category-opt" value="${esc(c.id)}" ${state.selectedCategories.has(c.id) ? 'checked' : ''}>
          ${esc(c.name)}
          ${c.is_public ? '<span class="ms-option-meta">عمومی</span>' : ''}
        </label>`).join('')
      : '<div class="ms-empty">دسته‌ای با این نام پیدا نشد</div>';
  }

  function toggleCategoryDropdown() {
    document.getElementById('c-category-ms').classList.contains('open') ? closeCategoryDropdown() : openCategoryDropdown();
  }
  function openCategoryDropdown() {
    document.getElementById('c-category-ms').classList.add('open');
    document.getElementById('c-category-panel').classList.remove('hidden');
    renderCategoryOptions();
    const s = document.getElementById('c-category-search');
    setTimeout(() => s && s.focus(), 0);
  }
  function closeCategoryDropdown() {
    document.getElementById('c-category-ms')?.classList.remove('open');
    document.getElementById('c-category-panel')?.classList.add('hidden');
  }
  function filterCategoryOptions() { renderCategoryOptions(); }

  function onCategoryOptionChange(e) {
    const input = e.target.closest('input[data-role="c-category-opt"]');
    if (!input) return;
    if (input.checked) state.selectedCategories.add(input.value);
    else state.selectedCategories.delete(input.value);
    renderCategoryValues();
  }

  // ─── Tabs / Load (لیست محتوا) ───────────────────────────────────
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
    const orgFilter = document.getElementById('contentOrgFilter')?.value || '';
    const categoryFilter = document.getElementById('contentCategoryFilter')?.value || '';
    const tbody = document.getElementById('contentTableBody');
    tbody.innerHTML = `<tr><td colspan="9" class="loading-row">در حال بارگذاری...</td></tr>`;
    const p = new URLSearchParams({ page, page_size: 10, type: state.type });
    if (state.search) p.set('search', state.search);
    if (state.status) p.set('status', state.status);
    if (categoryFilter) p.set('category_id', categoryFilter);
    if (App.isSuperAdmin && orgFilter) p.set('org_id', orgFilter);
    try {
      const res = await api.get(`/contents/?${p}`);
      state.items = res.items || [];
      state.total = res.total || 0;
      state.totalPages = res.total_pages || 1;
      setText('contentTotalLabel', `${numFa(state.total)} ${TYPE_LABELS[state.type]} یافت شد`);
      renderTable();
      renderPagination('contentPagination', state.page, state.totalPages, load);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function searchDebounced() {
    state.search = document.getElementById('contentSearch').value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load(1), 400);
  }

  function accessBadges(c) {
    const badges = [];
    badges.push(c.target_count > 0
      ? `<span class="badge badge-targeted" title="این محتوا فقط برای واحد/پست/کاربران خاصی نمایش داده می‌شود">🎯 ${numFa(c.target_count)} محدودیت</span>`
      : `<span class="badge badge-orgwide">🌐 کل سازمان</span>`);
    if (c.sequential_progress) {
      badges.push(`<span class="badge badge-sequential" title="کاربر باید آیتم‌ها را به ترتیب تکمیل کند">🔒 ترتیبی</span>`);
    }
    return `<div style="display:flex;gap:4px;flex-wrap:wrap;">${badges.join('')}</div>`;
  }

  function renderTable() {
    const tbody = document.getElementById('contentTableBody');
    if (!state.items.length) {
      tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-state-icon">🗂️</div>هنوز محتوایی از نوع «${TYPE_LABELS[state.type]}» ثبت نشده</div></td></tr>`;
      return;
    }
    const canEdit = App.isSuperAdmin || App.isOrgAdmin;
    tbody.innerHTML = state.items.map(c => `
      <tr>
        <td style="font-weight:600;">${esc(c.title)}</td>
        ${App.isSuperAdmin ? `<td class="th-org">${c.org_name ? esc(c.org_name) : '<span style="color:var(--gray-400);">عمومی</span>'}</td>` : ''}
        <td>${typeBadge(c.type)}</td>
        <td style="color:var(--gray-500);">${(c.categories && c.categories.length) ? esc(c.categories.map(x => x.name).join('، ')) : '—'}</td>
        <td>${statusBadge(c.status)}</td>
        <td>${accessBadges(c)}</td>
        <td>${numFa(c.total_items_count)} آیتم</td>
        <td style="color:var(--gray-500);">${fmtDate(c.created_at)}</td>
        <td>
          <div style="display:flex;gap:4px;flex-wrap:wrap;">
            <button class="btn-action" style="background:var(--primary-light);color:var(--primary);" onclick="ContentPage.openEdit('${c.id}','items')">آیتم‌ها</button>
            ${canEdit ? `<button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="ContentPage.openEdit('${c.id}')">ویرایش</button>` : ''}
            ${canEdit ? `<button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-content" data-id="${c.id}" data-title="${esc(c.title)}">حذف</button>` : ''}
          </div>
        </td>
      </tr>`).join('');
  }

  // ─── Wizard: تب‌ها ───────────────────────────────────────────────
  function switchTab(tab) {
    if (state.mode === 'create') {
      const targetIdx = CTAB_ORDER.indexOf(tab);
      const maxIdx = CTAB_ORDER.indexOf(state.maxUnlockedTab);
      if (targetIdx > maxIdx) return; // هنوز باز نشده
    }
    state.activeTab = tab;
    document.querySelectorAll('#contentModalTabs .tab-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.ctab === tab));
    document.querySelectorAll('.ctab-content').forEach(el =>
      el.classList.toggle('active', el.id === 'ctab-' + tab));
    updateFooterButtons();
  }

  function setTabsUnlocked(maxTab) {
    state.maxUnlockedTab = maxTab;
    const maxIdx = CTAB_ORDER.indexOf(maxTab);
    document.querySelectorAll('#contentModalTabs .tab-btn').forEach(b => {
      b.disabled = state.mode === 'create' && CTAB_ORDER.indexOf(b.dataset.ctab) > maxIdx;
    });
  }

  function updateFooterButtons() {
    const back = document.getElementById('btn-content-back');
    const next = document.getElementById('btn-content-next');
    const save = document.getElementById('btn-content-save');
    const finish = document.getElementById('btn-content-finish');

    if (state.mode === 'edit') {
      back.classList.add('hidden');
      next.classList.add('hidden');
      finish.classList.add('hidden');
      save.classList.remove('hidden');
      return;
    }
    save.classList.add('hidden');
    const idx = CTAB_ORDER.indexOf(state.activeTab);
    back.classList.toggle('hidden', idx === 0);
    next.classList.toggle('hidden', idx === CTAB_ORDER.length - 1);
    finish.classList.toggle('hidden', idx !== CTAB_ORDER.length - 1);
  }

  function prevTab() {
    const idx = CTAB_ORDER.indexOf(state.activeTab);
    if (idx > 0) switchTab(CTAB_ORDER[idx - 1]);
  }

  async function nextTab() {
    if (state.activeTab === 'basic') {
      const title = document.getElementById('c-title').value.trim();
      if (!title) { toastError('عنوان محتوا اجباری است'); return; }
      const isPublic = App.isSuperAdmin && document.getElementById('c-is-public').checked;
      let orgId = null;
      if (App.isSuperAdmin && !isPublic) {
        orgId = document.getElementById('c-org-id').value;
        if (!orgId) { toastError('لطفاً سازمان را انتخاب کنید'); return; }
      }
      const btn = document.getElementById('btn-content-next');
      setLoading(btn, true);
      try {
        const payload = basicPayload();
        if (isPublic) payload.is_public = true;
        else if (orgId) payload.org_id = orgId;
        const created = await api.post('/contents/', payload);
        state.contentId = created.id;
        document.getElementById('c-id').value = created.id;
        document.getElementById('c-type').disabled = true;
        document.getElementById('c-org-id').disabled = true;
        if (App.isSuperAdmin) document.getElementById('c-is-public').disabled = true;
        toggleTargetingSection(isPublic);
        toastSuccess('مشخصات پایه ذخیره شد — حالا دسترسی و کاور را تنظیم کنید');
        setTabsUnlocked('access');
        switchTab('access');
      } catch (e) { toastError(e.message); }
      finally { setLoading(btn, false); }
      return;
    }

    if (state.activeTab === 'access') {
      const btn = document.getElementById('btn-content-next');
      setLoading(btn, true);
      try {
        await api.patch(`/contents/${state.contentId}`, collectEditablePayload());
        state.activeItems = [];
        renderItems();
        setTabsUnlocked('items');
        switchTab('items');
      } catch (e) { toastError(e.message); }
      finally { setLoading(btn, false); }
      return;
    }
  }

  async function finishWizard() {
    closeModal('modal-content');
    await load(1);
    await loadCategories();
  }

  function closeContentModal() {
    const wasCreatingDraft = state.mode === 'create' && state.contentId;
    closeModal('modal-content');
    if (wasCreatingDraft) { load(1); loadCategories(); } // محتوا از مرحله ۱ به بعد از قبل روی سرور ساخته شده
  }

  // ─── ساخت / ویرایش محتوا ────────────────────────────────────────
  function resetTargetSelections() {
    state.selectedDepts = new Set();
    state.selectedPositions = new Set();
    state.selectedUsers = new Map();
    state.userSearchResults = [];
    state.selectedCategories = new Set();
    document.getElementById('c-target-user-search').value = '';
    renderUserChips();
    document.getElementById('c-target-users').innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>';
  }

  function parseTagsInput() {
    const tagsRaw = document.getElementById('c-tags').value.trim();
    return tagsRaw ? tagsRaw.split(/[،,]/).map(t => t.trim()).filter(Boolean) : [];
  }

  function basicPayload() {
    return {
      title: document.getElementById('c-title').value.trim(),
      type: document.getElementById('c-type').value,
      description: document.getElementById('c-desc').value.trim() || null,
      category_ids: Array.from(state.selectedCategories),
      level: document.getElementById('c-level').value || null,
      author: document.getElementById('c-author').value.trim() || null,
      tags: parseTagsInput(),
    };
  }

  function collectEditablePayload() {
    return {
      title: document.getElementById('c-title').value.trim(),
      description: document.getElementById('c-desc').value.trim() || null,
      category_ids: Array.from(state.selectedCategories),
      level: document.getElementById('c-level').value || null,
      author: document.getElementById('c-author').value.trim() || null,
      tags: parseTagsInput(),
      status: document.getElementById('c-status').value,
      total_duration_min: document.getElementById('c-duration').value ? parseInt(document.getElementById('c-duration').value, 10) : null,
      is_featured: document.getElementById('c-featured').checked,
      sequential_progress: document.getElementById('c-sequential').checked,
      points_override: document.getElementById('c-points').value !== '' ? parseInt(document.getElementById('c-points').value, 10) : null,
      thumbnail_url: document.getElementById('c-thumb-url').value || null,
      targets: collectTargets(),
    };
  }

  async function openCreate() {
    state.mode = 'create';
    state.contentId = null;
    document.getElementById('contentModalTitle').textContent = `${TYPE_LABELS[state.type]} جدید`;
    document.getElementById('c-id').value = '';
    document.getElementById('c-title').value = '';
    document.getElementById('c-type').value = state.type;
    document.getElementById('c-type').disabled = false;
    document.getElementById('c-status').value = 'draft';
    document.getElementById('c-level').value = '';
    document.getElementById('c-author').value = '';
    document.getElementById('c-desc').value = '';
    document.getElementById('c-tags').value = '';
    document.getElementById('c-duration').value = '';
    document.getElementById('c-featured').checked = false;
    document.getElementById('c-sequential').checked = false;
    document.getElementById('c-points').value = '';
    document.getElementById('c-thumb-url').value = '';
    setUploadName('c-thumb-name', '');
    renderThumbPreview('');
    resetTargetSelections();
    state.activeItems = [];
    renderItems();
    document.getElementById('c-public-badge').classList.add('hidden');
    toggleTargetingSection(false);

    const orgSel = document.getElementById('c-org-id');
    orgSel.disabled = false;
    if (App.isSuperAdmin) {
      document.getElementById('c-is-public-wrap').classList.remove('hidden');
      document.getElementById('c-is-public').checked = false;
      document.getElementById('c-is-public').disabled = false;
      document.getElementById('c-org-wrap').classList.remove('hidden');
      await loadOrgsForSelect('');
      state.targetOrgId = null;
      renderDeptCheckboxes(true);
      renderPositionCheckboxes(true);
      await loadCategoryOptions(null);
    } else {
      state.targetOrgId = App.homeOrgId;
      await loadTargetingLists(state.targetOrgId);
      await loadCategoryOptions(state.targetOrgId);
    }

    setTabsUnlocked('basic');
    switchTab('basic');
    openModal('modal-content');
  }

  async function openEdit(id, jumpToTab = 'basic') {
    let c;
    try { c = await api.get(`/contents/${id}`); }
    catch (e) { toastError(e.message); return; }

    state.mode = 'edit';
    state.contentId = c.id;

    document.getElementById('contentModalTitle').textContent = 'ویرایش محتوا';
    document.getElementById('c-id').value = c.id;
    document.getElementById('c-title').value = c.title || '';
    document.getElementById('c-type').value = c.type;
    document.getElementById('c-type').disabled = true; // نوع بعد از ساخت غیرقابل تغییر است
    document.getElementById('c-status').value = c.status;
    document.getElementById('c-level').value = c.level || '';
    document.getElementById('c-author').value = c.author || '';
    document.getElementById('c-desc').value = c.description || '';
    document.getElementById('c-tags').value = (c.tags || []).join('، ');
    document.getElementById('c-duration').value = c.total_duration_min ?? '';
    document.getElementById('c-featured').checked = !!c.is_featured;
    document.getElementById('c-sequential').checked = !!c.sequential_progress;
    document.getElementById('c-points').value = c.points_override ?? '';
    document.getElementById('c-thumb-url').value = c.thumbnail_url || '';
    setUploadName('c-thumb-name', c.thumbnail_url ? 'تصویر فعلی ثبت شده' : '');
    renderThumbPreview(c.thumbnail_url || '');
    resetTargetSelections();

    // is_public فقط در ساخت قابل تنظیم است — در ویرایش فقط وضعیت فعلی نمایش داده می‌شود
    document.getElementById('c-is-public-wrap').classList.add('hidden');
    toggleTargetingSection(!c.org_id);
    state.targetOrgId = c.org_id;
    if (App.isSuperAdmin) {
      if (c.org_id) {
        document.getElementById('c-public-badge').classList.add('hidden');
        document.getElementById('c-org-wrap').classList.remove('hidden');
        await loadOrgsForSelect(c.org_id);
        document.getElementById('c-org-id').disabled = true; // سازمان بعد از ساخت غیرقابل تغییر است
      } else {
        document.getElementById('c-public-badge').classList.remove('hidden');
        document.getElementById('c-org-wrap').classList.add('hidden');
      }
    }

    for (const t of (c.targets || [])) {
      if (t.target_type === 'department') state.selectedDepts.add(t.target_id);
      else if (t.target_type === 'position') state.selectedPositions.add(t.target_id);
      else if (t.target_type === 'user') state.selectedUsers.set(t.target_id, t.target_label || t.target_id);
    }
    renderUserChips();
    await loadTargetingLists(c.org_id);
    state.selectedCategories = new Set((c.categories || []).map(x => x.id));
    await loadCategoryOptions(c.org_id);

    state.activeItems = c.items || [];
    renderItems();

    setTabsUnlocked('items'); // در ویرایش همه‌ی تب‌ها باز است
    switchTab(jumpToTab);
    openModal('modal-content');
  }

  async function saveChanges() {
    const title = document.getElementById('c-title').value.trim();
    if (!title) { toastError('عنوان محتوا اجباری است'); return; }
    const btn = document.getElementById('btn-content-save');
    setLoading(btn, true);
    try {
      await api.patch(`/contents/${state.contentId}`, collectEditablePayload());
      toastSuccess('تغییرات با موفقیت ذخیره شد');
      await load(state.page);
      await loadCategories();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function collectTargets() {
    const targets = [];
    for (const id of state.selectedDepts) targets.push({ target_type: 'department', target_id: id });
    for (const id of state.selectedPositions) targets.push({ target_type: 'position', target_id: id });
    for (const id of state.selectedUsers.keys()) targets.push({ target_type: 'user', target_id: id });
    return targets;
  }

  function remove(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید "${title}" را حذف کنید؟ تمام آیتم‌های داخل آن نیز حذف می‌شوند.`, async () => {
      await api.delete(`/contents/${id}`);
      toastSuccess('محتوا با موفقیت حذف شد');
      await load(1);
      await loadCategories();
    });
  }

  // آدرس فایل روی مسیر سازمانِ صحیح ذخیره شود (نه سازمانِ کاربر آپلودکننده) —
  // وگرنه routers/files.py بعداً با 403 دسترسی به فایل را رد می‌کند.
  // اولویت با content_id است: بک‌اند مسیر را از org_id واقعی همان رکورد
  // محتوا تعیین می‌کند. state.contentId همیشه پیش از هر آپلود ست شده
  // (مرحله‌ی ۱ ویزارد محتوا را می‌سازد، و در ویرایش هم از قبل موجود است) —
  // فرم ویرایش c-is-public/c-org-id را درست پر نمی‌کند، پس به آن‌ها تکیه نکن.
  function getContentUploadParams() {
    if (state.contentId) return { content_id: state.contentId };
    const isPublic = App.isSuperAdmin && document.getElementById('c-is-public').checked;
    if (isPublic) return { is_public: true };
    if (App.isSuperAdmin) {
      const orgId = document.getElementById('c-org-id').value;
      if (orgId) return { org_id: orgId };
    }
    return {};
  }

  async function uploadThumbnail(inputEl) {
    const file = inputEl.files?.[0];
    if (!file) return;
    try {
      const res = await api.uploadDirect('/contents/upload', file, (pct) => setUploadName('c-thumb-name', `در حال آپلود... ${numFa(pct)}٪`, true), getContentUploadParams());
      document.getElementById('c-thumb-url').value = res.url;
      setUploadName('c-thumb-name', file.name, true);
      renderThumbPreview(res.url);
      toastSuccess('تصویر با موفقیت آپلود شد');
    } catch (e) { toastError(e.message); setUploadName('c-thumb-name', ''); }
    finally { inputEl.value = ''; }
  }

  // ─── Targeting: سازمان (فقط super_admin) ────────────────────────
  async function loadOrgsForSelect(selectedId) {
    const sel = document.getElementById('c-org-id');
    const ok = await ensureOrgsLoaded();
    if (!ok) { sel.innerHTML = '<option value="">خطا در بارگذاری سازمان‌ها</option>'; return; }
    sel.innerHTML = '<option value="">— انتخاب سازمان —</option>' +
      state.orgs.map(o => `<option value="${o.id}" ${o.id === selectedId ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
  }

  async function onOrgChange() {
    const orgId = document.getElementById('c-org-id').value;
    resetTargetSelections();
    state.targetOrgId = orgId || null;
    if (!orgId) {
      renderDeptCheckboxes(true);
      renderPositionCheckboxes(true);
      await loadCategoryOptions(null);
      return;
    }
    await loadTargetingLists(orgId);
    await loadCategoryOptions(orgId);
  }

  // ─── محتوای Public (بدون سازمان) — فقط super_admin، فقط در حالت ساخت ──
  function onPublicToggle() {
    const checked = document.getElementById('c-is-public').checked;
    document.getElementById('c-org-wrap').classList.toggle('hidden', checked);
    if (checked) {
      resetTargetSelections();
      state.targetOrgId = null;
      loadCategoryOptions(null);
    } else {
      const orgId = document.getElementById('c-org-id').value;
      if (orgId) { loadTargetingLists(orgId); loadCategoryOptions(orgId); }
      else { renderDeptCheckboxes(true); renderPositionCheckboxes(true); loadCategoryOptions(null); }
    }
  }

  function toggleTargetingSection(isPublic) {
    document.getElementById('c-targeting-section').classList.toggle('hidden', isPublic);
    document.getElementById('c-targeting-public-note').classList.toggle('hidden', !isPublic);
  }

  // ─── Targeting: واحدها و پست‌ها ──────────────────────────────────
  async function loadTargetingLists(orgId) {
    if (!orgId) return;
    try {
      const [depts, positions] = await Promise.all([
        api.get(`/departments/?org_id=${orgId}`),
        api.get(`/positions/?org_id=${orgId}`),
      ]);
      state.depts = depts || [];
      state.positions = positions || [];
    } catch {
      state.depts = [];
      state.positions = [];
    }
    renderDeptCheckboxes();
    renderPositionCheckboxes();
  }

  function renderDeptCheckboxes(needsOrg = false) {
    const box = document.getElementById('c-target-depts');
    if (needsOrg) { box.innerHTML = '<div class="checkbox-scroll-box-empty">ابتدا سازمان را انتخاب کنید</div>'; return; }
    if (!state.depts.length) { box.innerHTML = '<div class="checkbox-scroll-box-empty">واحدی ثبت نشده</div>'; return; }
    box.innerHTML = state.depts.map(d => `
      <label class="checkbox-row">
        <input type="checkbox" ${state.selectedDepts.has(d.id) ? 'checked' : ''} onchange="ContentPage.toggleDeptTarget('${d.id}', this.checked)">
        ${esc(d.name)}
        <span class="checkbox-row-meta">${numFa(d.user_count || 0)} کاربر</span>
      </label>`).join('');
  }

  function renderPositionCheckboxes(needsOrg = false) {
    const box = document.getElementById('c-target-positions');
    if (needsOrg) { box.innerHTML = '<div class="checkbox-scroll-box-empty">ابتدا سازمان را انتخاب کنید</div>'; return; }
    if (!state.positions.length) { box.innerHTML = '<div class="checkbox-scroll-box-empty">پستی ثبت نشده</div>'; return; }
    box.innerHTML = state.positions.map(p => `
      <label class="checkbox-row">
        <input type="checkbox" ${state.selectedPositions.has(p.id) ? 'checked' : ''} onchange="ContentPage.togglePositionTarget('${p.id}', this.checked)">
        ${esc(p.name)}
        <span class="checkbox-row-meta">${numFa(p.user_count || 0)} کاربر</span>
      </label>`).join('');
  }

  function toggleDeptTarget(id, checked) {
    if (checked) state.selectedDepts.add(id); else state.selectedDepts.delete(id);
  }

  function togglePositionTarget(id, checked) {
    if (checked) state.selectedPositions.add(id); else state.selectedPositions.delete(id);
  }

  // ─── Targeting: کاربران خاص ──────────────────────────────────────
  function searchTargetUsers() {
    clearTimeout(targetUserSearchTimer);
    targetUserSearchTimer = setTimeout(runTargetUserSearch, 350);
  }

  async function runTargetUserSearch() {
    const box = document.getElementById('c-target-users');
    const q = document.getElementById('c-target-user-search').value.trim();
    if (!q) { box.innerHTML = '<div class="checkbox-scroll-box-empty">برای جستجو تایپ کنید</div>'; return; }
    if (!state.targetOrgId) { box.innerHTML = '<div class="checkbox-scroll-box-empty">ابتدا سازمان را انتخاب کنید</div>'; return; }
    box.innerHTML = '<div class="checkbox-scroll-box-empty">در حال جستجو...</div>';
    try {
      const res = await api.get(`/users/?org_id=${state.targetOrgId}&search=${encodeURIComponent(q)}&per_page=20`);
      state.userSearchResults = res.items || [];
      renderTargetUserResults();
    } catch {
      box.innerHTML = '<div class="checkbox-scroll-box-empty">خطا در جستجوی کاربران</div>';
    }
  }

  function renderTargetUserResults() {
    const box = document.getElementById('c-target-users');
    if (!state.userSearchResults.length) { box.innerHTML = '<div class="checkbox-scroll-box-empty">کاربری یافت نشد</div>'; return; }
    box.innerHTML = state.userSearchResults.map(u => `
      <label class="checkbox-row">
        <input type="checkbox" ${state.selectedUsers.has(u.id) ? 'checked' : ''} onchange="ContentPage.toggleUserTarget('${u.id}', this.checked)">
        ${esc(u.full_name)}
        <span class="checkbox-row-meta">${esc(u.email)}</span>
      </label>`).join('');
  }

  function toggleUserTarget(id, checked) {
    if (checked) {
      const u = state.userSearchResults.find(x => x.id === id);
      state.selectedUsers.set(id, u ? `${u.full_name} (${u.email})` : id);
    } else {
      state.selectedUsers.delete(id);
    }
    renderUserChips();
  }

  function removeUserChip(id) {
    state.selectedUsers.delete(id);
    renderUserChips();
    renderTargetUserResults();
  }

  function renderUserChips() {
    const box = document.getElementById('c-target-users-selected');
    if (!state.selectedUsers.size) { box.innerHTML = ''; return; }
    box.innerHTML = Array.from(state.selectedUsers.entries()).map(([id, label]) => `
      <span class="chip">${esc(label)}<span class="chip-remove" onclick="ContentPage.removeUserChip('${id}')">✕</span></span>`).join('');
  }

  // ─── تب ۳: آیتم‌ها / برنامه‌ی درسی ───────────────────────────────
  async function loadItems() {
    const wrap = document.getElementById('contentItemsList');
    wrap.innerHTML = `<div class="loading-row" style="padding:20px;text-align:center;">در حال بارگذاری...</div>`;
    try {
      const detail = await api.get(`/contents/${state.contentId}`);
      state.activeItems = detail.items || [];
      renderItems();
    } catch (e) {
      wrap.innerHTML = `<div style="color:var(--danger);text-align:center;padding:20px;">خطا در بارگذاری: ${esc(e.message)}</div>`;
    }
  }

  function sortedItems() {
    return [...state.activeItems].sort((a, b) => a.order_index - b.order_index);
  }

  function renderItems() {
    const wrap = document.getElementById('contentItemsList');
    if (!state.activeItems.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📭</div>هنوز آیتمی اضافه نشده — یا با «افزودن آیتم تکی» یا با «افزودن دسته‌جمعی» شروع کنید</div>`;
      return;
    }
    const canEdit = App.isSuperAdmin || App.isOrgAdmin;
    const sorted = sortedItems();
    wrap.innerHTML = sorted.map((it, idx) => {
      const downloadable = ['video', 'pdf', 'image', 'file'].includes(it.type) && !!it.media_url;
      const icon = it.type === 'image' && it.media_url
        ? `<img class="item-row-thumb" data-src="${esc(it.media_url)}" alt="">`
        : `<div class="item-row-icon">${ITEM_TYPE_ICONS[it.type] || '📄'}</div>`;
      return `
      <div class="item-row">
        <div class="item-row-order">${numFa(idx + 1)}</div>
        ${icon}
        <div class="item-row-info">
          <div class="item-row-title">${esc(it.title)}</div>
          <div class="item-row-meta">${ITEM_TYPE_LABELS[it.type] || it.type}${it.duration_min ? ' • ' + numFa(it.duration_min) + ' دقیقه' : ''}${it.is_free ? ' • رایگان' : ''}</div>
        </div>
        <div class="item-row-actions">
          ${downloadable ? `<button class="btn-icon" title="دانلود فایل" data-role="download-item" data-id="${it.id}">⬇️</button>` : ''}
          ${canEdit && idx > 0 ? `<button class="btn-icon" title="جابه‌جایی به بالا" onclick="ContentPage.moveItemUp('${it.id}')">▲</button>` : ''}
          ${canEdit && idx < sorted.length - 1 ? `<button class="btn-icon" title="جابه‌جایی به پایین" onclick="ContentPage.moveItemDown('${it.id}')">▼</button>` : ''}
          ${canEdit ? `<button class="btn-icon" title="ویرایش" onclick="ContentPage.openEditItem('${it.id}')">✎</button>` : ''}
          ${canEdit ? `<button class="btn-icon" title="حذف" data-role="delete-item" data-id="${it.id}" data-title="${esc(it.title)}">🗑</button>` : ''}
        </div>
      </div>`;
    }).join('');
    hydrateAuthedImages(wrap);
  }

  // پسوند فایل اصلی هیچ‌جا ذخیره نمی‌شود (فقط media_url) — پسوند را از خودِ
  // URI آپلودشده استخراج می‌کنیم تا نام فایل دانلودی بی‌پسوند نباشد.
  function filenameWithExt(base, url) {
    const ext = /\.([a-zA-Z0-9]{1,8})$/.exec((url || '').split('?')[0])?.[1];
    if (!ext || /\.[a-zA-Z0-9]{1,8}$/.test(base)) return base;
    return `${base}.${ext}`;
  }

  function downloadItem(id) {
    const it = state.activeItems.find(x => x.id === id);
    if (!it || !it.media_url) return;
    downloadAuthedFile(it.media_url, filenameWithExt(it.title || 'file', it.media_url));
  }

  async function swapOrder(id, dir) {
    const sorted = sortedItems();
    const idx = sorted.findIndex(x => x.id === id);
    const swapIdx = idx + dir;
    if (idx === -1 || swapIdx < 0 || swapIdx >= sorted.length) return;
    const a = sorted[idx], b = sorted[swapIdx];
    try {
      await Promise.all([
        api.patch(`/contents/items/${a.id}`, { order_index: b.order_index }),
        api.patch(`/contents/items/${b.id}`, { order_index: a.order_index }),
      ]);
      await loadItems();
    } catch (e) { toastError(e.message); }
  }
  function moveItemUp(id) { return swapOrder(id, -1); }
  function moveItemDown(id) { return swapOrder(id, 1); }

  function toggleItemFields() {
    const type = document.getElementById('i-type').value;
    document.getElementById('i-body-wrap').classList.toggle('hidden', type !== 'text');
    document.getElementById('i-upload-wrap').classList.toggle('hidden', !['video', 'pdf', 'image', 'file'].includes(type));
    document.getElementById('i-link-wrap').classList.toggle('hidden', type !== 'link');
    document.getElementById('i-quiz-wrap').classList.toggle('hidden', type !== 'quiz_ref');
    if (type === 'quiz_ref' && !state.quizzesLoaded) populateQuizSelect();
  }

  async function populateQuizSelect(selectedId) {
    const sel = document.getElementById('i-quiz-id');
    const keep = selectedId || sel.value;
    try {
      const res = await api.get('/quizzes/?is_active=true&page_size=100');
      state.quizzesLoaded = true;
      sel.innerHTML = '<option value="">— بدون آزمون —</option>' +
        (res.items || []).map(q => `<option value="${q.id}" ${q.id === keep ? 'selected' : ''}>${esc(q.title)}</option>`).join('');
    } catch {
      sel.innerHTML = '<option value="">خطا در بارگذاری لیست آزمون‌ها</option>';
    }
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
    document.getElementById('i-points').value = '';
    setUploadName('i-upload-name', '');
    renderItemUploadPreview('', 'text');
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
    document.getElementById('i-duration').value = it.duration_min ?? '';
    document.getElementById('i-order').value = it.order_index ?? 0;
    document.getElementById('i-free').checked = !!it.is_free;
    document.getElementById('i-points').value = it.points_override ?? '';
    setUploadName('i-upload-name', it.media_url && it.type !== 'link' ? 'فایل فعلی ثبت شده' : '');
    renderItemUploadPreview(it.type !== 'link' ? (it.media_url || '') : '', it.type);
    toggleItemFields();
    if (it.type === 'quiz_ref') populateQuizSelect(it.quiz_id);
    openModal('modal-item');
  }

  async function uploadItemMedia(inputEl) {
    const file = inputEl.files?.[0];
    if (!file) return;
    try {
      const res = await api.uploadDirect('/contents/upload', file, (pct) => setUploadName('i-upload-name', `در حال آپلود... ${numFa(pct)}٪`, true), getContentUploadParams());
      document.getElementById('i-media-url').value = res.url;
      setUploadName('i-upload-name', file.name, true);
      renderItemUploadPreview(res.url, document.getElementById('i-type').value);
      toastSuccess('فایل با موفقیت آپلود شد');
    } catch (e) { toastError(e.message); setUploadName('i-upload-name', ''); }
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
      points_override: document.getElementById('i-points').value !== '' ? parseInt(document.getElementById('i-points').value, 10) : null,
    };

    const btn = document.getElementById('btn-save-item');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/contents/items/${id}`, payload); toastSuccess('آیتم با موفقیت ویرایش شد'); }
      else { await api.post(`/contents/${state.contentId}/items`, payload); toastSuccess('آیتم با موفقیت اضافه شد'); }
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

  // ─── تب ۳: افزودن دسته‌جمعی (چند فایل هم‌زمان) ───────────────────
  function pickBulkFiles() {
    document.getElementById('c-bulk-files').click();
  }

  function inferItemType(filename) {
    const ext = (filename.split('.').pop() || '').toLowerCase();
    return BULK_TYPE_BY_EXT[ext] || 'file';
  }

  function titleFromFilename(filename) {
    return filename.replace(/\.[^.]+$/, '');
  }

  async function uploadBulkFiles(inputEl) {
    const files = Array.from(inputEl.files || []);
    if (!files.length) return;
    const progressEl = document.getElementById('c-bulk-progress');
    let nextOrder = state.activeItems.length
      ? Math.max(...state.activeItems.map(it => it.order_index)) + 1
      : 0;
    let done = 0, failed = 0;
    for (const file of files) {
      const label = `در حال آپلود ${numFa(done + failed + 1)} از ${numFa(files.length)}: ${file.name}`;
      progressEl.textContent = label;
      try {
        const uploaded = await api.uploadDirect('/contents/upload', file, (pct) => { progressEl.textContent = `${label} (${numFa(pct)}٪)`; }, getContentUploadParams());
        await api.post(`/contents/${state.contentId}/items`, {
          title: titleFromFilename(file.name),
          type: inferItemType(file.name),
          media_url: uploaded.url,
          order_index: nextOrder++,
          is_free: true,
        });
        done++;
      } catch {
        failed++;
      }
    }
    progressEl.textContent = failed
      ? `${numFa(done)} فایل با موفقیت اضافه شد — ${numFa(failed)} فایل با خطا مواجه شد`
      : `${numFa(done)} فایل با موفقیت اضافه شد`;
    inputEl.value = '';
    await loadItems();
    await load(state.page);
  }

  // ─── Helpers ────────────────────────────────────────────────────
  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
  function setUploadName(id, name, hasFile = !!name) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = name || 'فایلی انتخاب نشده';
    el.classList.toggle('has-file', hasFile);
  }
  function renderThumbPreview(url) {
    const preview = document.getElementById('c-thumb-preview');
    if (!preview) return;
    preview.innerHTML = url ? `<img data-src="${esc(url)}" alt="" style="width:120px;height:80px;object-fit:cover;border-radius:6px;background:var(--gray-100);">` : '';
    if (url) hydrateAuthedImages(preview);
  }

  // پیش‌نمایش فایل آپلودشده‌ی یک آیتم — همانند پیش‌نمایش کاور، تا مدیر
  // بدون نیاز به دانلود جداگانه ببیند دقیقاً چه فایلی ثبت شده.
  function renderItemUploadPreview(url, type) {
    const preview = document.getElementById('i-upload-preview');
    if (!preview) return;
    if (!url) { preview.innerHTML = ''; return; }
    if (type === 'image') {
      preview.innerHTML = `<div style="display:flex;align-items:center;gap:10px;">
        <img data-src="${esc(url)}" alt="" style="width:64px;height:64px;object-fit:cover;border-radius:6px;background:var(--gray-100);">
        <button type="button" class="btn btn-secondary" style="font-size:12px;padding:6px 10px;" onclick="ContentPage.downloadCurrentItemMedia()">دانلود فایل ↓</button>
      </div>`;
      hydrateAuthedImages(preview);
    } else {
      preview.innerHTML = `<div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:20px;">${ITEM_TYPE_ICONS[type] || '📎'}</span>
        <span style="font-size:12px;color:var(--gray-500);">فایل فعلی آپلود شده</span>
        <button type="button" class="btn btn-secondary" style="font-size:12px;padding:6px 10px;" onclick="ContentPage.downloadCurrentItemMedia()">دانلود ↓</button>
      </div>`;
    }
  }

  function downloadCurrentItemMedia() {
    const url = document.getElementById('i-media-url').value;
    const title = document.getElementById('i-title').value.trim() || 'file';
    if (url) downloadAuthedFile(url, filenameWithExt(title, url));
  }

  // ─── Delegated Row Actions (نه onclick اینلاین با عنوان کاربر داخلش) ──
  // چون confirmAction عنوان را با textContent نشان می‌دهد، امن است — اما
  // onclick="fn('${esc(title)}')" روی یک attribute تک‌کوتیشن، امن نیست:
  // esc() فرار از HTML را می‌بندد ولی فرار از رشته‌ی جاوااسکریپت داخل
  // onclick را نه (یک تک‌کوتیشن در عنوان کافی است). به همین دلیل عنوان از
  // data-title (که مرورگر هنگام خواندن dataset خودش HTML-decode می‌کند)
  // خوانده می‌شود، نه از یک رشته‌ی تولیدشده با template literal.
  document.getElementById('contentTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-content"]');
    if (btn) remove(btn.dataset.id, btn.dataset.title);
  });
  document.getElementById('contentCategoriesTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-content-category"]');
    if (btn) removeCategory(btn.dataset.id, btn.dataset.title);
  });
  document.getElementById('contentItemsList')?.addEventListener('click', (e) => {
    const delBtn = e.target.closest('[data-role="delete-item"]');
    if (delBtn) { removeItem(delBtn.dataset.id, delBtn.dataset.title); return; }
    const dlBtn = e.target.closest('[data-role="download-item"]');
    if (dlBtn) downloadItem(dlBtn.dataset.id);
  });

  // ─── دراپ‌داون چندانتخابی دسته‌بندی: تغییر گزینه‌ها، حذف تگ، بستن با کلیک بیرون ──
  document.getElementById('c-category-options')?.addEventListener('change', onCategoryOptionChange);
  document.getElementById('c-category-values')?.addEventListener('click', (e) => {
    const x = e.target.closest('[data-role="c-category-untag"]');
    if (!x) return;
    e.stopPropagation(); // تریگر را toggle نکن
    state.selectedCategories.delete(x.dataset.id);
    renderCategoryValues();
    renderCategoryOptions();
  });
  document.addEventListener('click', (e) => {
    const ms = document.getElementById('c-category-ms');
    if (ms && ms.classList.contains('open') && !ms.contains(e.target)) closeCategoryDropdown();
  });

  return {
    goto, setType, load, searchDebounced, onOrgFilterChange,
    openCategoriesModal, onCategoryManageOrgChange,
    openCreateCategory, openEditCategory, saveCategory, removeCategory, hideCategoryForm,
    switchTab, prevTab, nextTab, finishWizard, closeContentModal,
    openCreate, openEdit, saveChanges, remove, uploadThumbnail,
    loadItems, toggleItemFields, openCreateItem, openEditItem, uploadItemMedia, saveItem, removeItem,
    moveItemUp, moveItemDown, pickBulkFiles, uploadBulkFiles, downloadItem, downloadCurrentItemMedia,
    onOrgChange, onPublicToggle, toggleDeptTarget, togglePositionTarget,
    toggleCategoryDropdown, filterCategoryOptions,
    searchTargetUsers, toggleUserTarget, removeUserChip,
  };
})();
