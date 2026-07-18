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

const ContentPage = (() => {
  const state = {
    type: 'course', page: 1, search: '', status: '',
    items: [], total: 0, totalPages: 1,
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
    const tbody = document.getElementById('contentTableBody');
    tbody.innerHTML = `<tr><td colspan="8" class="loading-row">در حال بارگذاری...</td></tr>`;
    const p = new URLSearchParams({ page, page_size: 10, type: state.type });
    if (state.search) p.set('search', state.search);
    if (state.status) p.set('status', state.status);
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
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
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
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-state-icon">🗂️</div>هنوز محتوایی از نوع «${TYPE_LABELS[state.type]}» ثبت نشده</div></td></tr>`;
      return;
    }
    const canEdit = App.isSuperAdmin || App.isOrgAdmin;
    tbody.innerHTML = state.items.map(c => `
      <tr>
        <td style="font-weight:600;">${esc(c.title)}</td>
        ${App.isSuperAdmin ? `<td class="th-org">${esc(c.org_name || '—')}</td>` : ''}
        <td>${typeBadge(c.type)}</td>
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
      let orgId = null;
      if (App.isSuperAdmin) {
        orgId = document.getElementById('c-org-id').value;
        if (!orgId) { toastError('لطفاً سازمان را انتخاب کنید'); return; }
      }
      const btn = document.getElementById('btn-content-next');
      setLoading(btn, true);
      try {
        const payload = basicPayload();
        if (orgId) payload.org_id = orgId;
        const created = await api.post('/contents/', payload);
        state.contentId = created.id;
        document.getElementById('c-id').value = created.id;
        document.getElementById('c-type').disabled = true;
        document.getElementById('c-org-id').disabled = true;
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
  }

  function closeContentModal() {
    const wasCreatingDraft = state.mode === 'create' && state.contentId;
    closeModal('modal-content');
    if (wasCreatingDraft) load(1); // محتوا از مرحله ۱ به بعد از قبل روی سرور ساخته شده
  }

  // ─── ساخت / ویرایش محتوا ────────────────────────────────────────
  function resetTargetSelections() {
    state.selectedDepts = new Set();
    state.selectedPositions = new Set();
    state.selectedUsers = new Map();
    state.userSearchResults = [];
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
      level: document.getElementById('c-level').value || null,
      author: document.getElementById('c-author').value.trim() || null,
      tags: parseTagsInput(),
    };
  }

  function collectEditablePayload() {
    return {
      title: document.getElementById('c-title').value.trim(),
      description: document.getElementById('c-desc').value.trim() || null,
      level: document.getElementById('c-level').value || null,
      author: document.getElementById('c-author').value.trim() || null,
      tags: parseTagsInput(),
      status: document.getElementById('c-status').value,
      total_duration_min: document.getElementById('c-duration').value ? parseInt(document.getElementById('c-duration').value, 10) : null,
      is_featured: document.getElementById('c-featured').checked,
      sequential_progress: document.getElementById('c-sequential').checked,
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
    document.getElementById('c-thumb-url').value = '';
    setUploadName('c-thumb-name', '');
    resetTargetSelections();
    state.activeItems = [];
    renderItems();

    const orgSel = document.getElementById('c-org-id');
    orgSel.disabled = false;
    if (App.isSuperAdmin) {
      await loadOrgsForSelect('');
      state.targetOrgId = null;
      renderDeptCheckboxes(true);
      renderPositionCheckboxes(true);
    } else {
      state.targetOrgId = App.homeOrgId;
      await loadTargetingLists(state.targetOrgId);
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
    document.getElementById('c-thumb-url').value = c.thumbnail_url || '';
    setUploadName('c-thumb-name', c.thumbnail_url ? 'تصویر فعلی ثبت شده' : '');
    resetTargetSelections();

    state.targetOrgId = c.org_id;
    if (App.isSuperAdmin) {
      await loadOrgsForSelect(c.org_id);
      document.getElementById('c-org-id').disabled = true; // سازمان بعد از ساخت غیرقابل تغییر است
    }

    for (const t of (c.targets || [])) {
      if (t.target_type === 'department') state.selectedDepts.add(t.target_id);
      else if (t.target_type === 'position') state.selectedPositions.add(t.target_id);
      else if (t.target_type === 'user') state.selectedUsers.set(t.target_id, t.target_label || t.target_id);
    }
    renderUserChips();
    await loadTargetingLists(c.org_id);

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

  // ─── Targeting: سازمان (فقط super_admin) ────────────────────────
  async function loadOrgsForSelect(selectedId) {
    const sel = document.getElementById('c-org-id');
    try {
      if (!state.orgsLoaded) {
        const res = await api.get('/orgs/');
        state.orgs = Array.isArray(res) ? res : (res.items || []);
        state.orgsLoaded = true;
      }
      sel.innerHTML = '<option value="">— انتخاب سازمان —</option>' +
        state.orgs.map(o => `<option value="${o.id}" ${o.id === selectedId ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
    } catch {
      sel.innerHTML = '<option value="">خطا در بارگذاری سازمان‌ها</option>';
    }
  }

  async function onOrgChange() {
    const orgId = document.getElementById('c-org-id').value;
    resetTargetSelections();
    state.targetOrgId = orgId || null;
    if (!orgId) {
      renderDeptCheckboxes(true);
      renderPositionCheckboxes(true);
      return;
    }
    await loadTargetingLists(orgId);
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
    wrap.innerHTML = sorted.map((it, idx) => `
      <div class="item-row">
        <div class="item-row-order">${numFa(idx + 1)}</div>
        <div class="item-row-icon">${ITEM_TYPE_ICONS[it.type] || '📄'}</div>
        <div class="item-row-info">
          <div class="item-row-title">${esc(it.title)}</div>
          <div class="item-row-meta">${ITEM_TYPE_LABELS[it.type] || it.type}${it.duration_min ? ' • ' + numFa(it.duration_min) + ' دقیقه' : ''}${it.is_free ? ' • رایگان' : ''}</div>
        </div>
        <div class="item-row-actions">
          ${canEdit && idx > 0 ? `<button class="btn-icon" title="جابه‌جایی به بالا" onclick="ContentPage.moveItemUp('${it.id}')">▲</button>` : ''}
          ${canEdit && idx < sorted.length - 1 ? `<button class="btn-icon" title="جابه‌جایی به پایین" onclick="ContentPage.moveItemDown('${it.id}')">▼</button>` : ''}
          ${canEdit ? `<button class="btn-icon" title="ویرایش" onclick="ContentPage.openEditItem('${it.id}')">✎</button>` : ''}
          ${canEdit ? `<button class="btn-icon" title="حذف" data-role="delete-item" data-id="${it.id}" data-title="${esc(it.title)}">🗑</button>` : ''}
        </div>
      </div>`).join('');
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
    document.getElementById('i-duration').value = it.duration_min ?? '';
    document.getElementById('i-order').value = it.order_index ?? 0;
    document.getElementById('i-free').checked = !!it.is_free;
    setUploadName('i-upload-name', it.media_url && it.type !== 'link' ? 'فایل فعلی ثبت شده' : '');
    toggleItemFields();
    if (it.type === 'quiz_ref') populateQuizSelect(it.quiz_id);
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
      progressEl.textContent = `در حال آپلود ${numFa(done + failed + 1)} از ${numFa(files.length)}: ${file.name}`;
      try {
        const uploaded = await api.upload('/contents/upload', file);
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
  document.getElementById('contentItemsList')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-item"]');
    if (btn) removeItem(btn.dataset.id, btn.dataset.title);
  });

  return {
    goto, setType, load, searchDebounced,
    switchTab, prevTab, nextTab, finishWizard, closeContentModal,
    openCreate, openEdit, saveChanges, remove, uploadThumbnail,
    loadItems, toggleItemFields, openCreateItem, openEditItem, uploadItemMedia, saveItem, removeItem,
    moveItemUp, moveItemDown, pickBulkFiles, uploadBulkFiles,
    onOrgChange, toggleDeptTarget, togglePositionTarget,
    searchTargetUsers, toggleUserTarget, removeUserChip,
  };
})();
