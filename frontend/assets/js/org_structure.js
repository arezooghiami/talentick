// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «ساختار سازمانی» (واحدها + پست‌ها)
// ════════════════════════════════════════════════════════════════════
// super_admin: از طریق دکمه‌ی «ساختار سازمانی» روی هر ردیف در صفحه‌ی
//              «شرکت‌ها» باز می‌شود (StructurePage.openFor(orgId, orgName)).
// org_admin/manager: مستقیماً از منوی سایدبار، همیشه روی سازمان خودشان.

const StructurePage = (() => {
  const state = {
    orgId: null, orgName: '', depts: [], positions: [],
    structTab: 'tree',        // 'tree' | 'table' — نمای پیش‌فرض واحدها
    collapsed: new Set(),      // id واحدهایی که در نمای درختی جمع شده‌اند
    dragId: null,              // واحد در حال کشیده‌شدن
    membersByDept: {},         // deptId → آرایه‌ی تودرتوی افراد (بر اساس سطح پست)
    membersLoaded: false,      // آیا داده‌ی افراد یک‌بار از سرور گرفته شده؟
    membersExpanded: new Set(), // id واحدهایی که فهرست افرادشان باز است
  };

  /** super_admin از این مسیر وارد می‌شود (نه از Router.navigate معمولی). */
  function openFor(orgId, orgName) {
    state.orgId = orgId;
    state.orgName = orgName;
    state.collapsed.clear();
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
    const tree = document.getElementById('deptsTree');
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>`;
    if (tree) tree.innerHTML = `<div class="org-tree-loading">در حال بارگذاری...</div>`;
    try {
      const items = await api.get(`/departments/?org_id=${state.orgId}`);
      state.depts = items || [];
      // شناسه‌های جمع‌شده‌ای که دیگر وجود ندارند را پاک کن
      const ids = new Set(state.depts.map(d => d.id));
      state.collapsed.forEach(id => { if (!ids.has(id)) state.collapsed.delete(id); });
      state.membersExpanded.forEach(id => { if (!ids.has(id)) state.membersExpanded.delete(id); });
      if (state.membersLoaded) await loadMembers();
      populateDeptFilter();
      renderDeptTable();
      renderDeptTree();
      applyStructTab();
    } catch (e) {
      const err = `خطا در بارگذاری: ${esc(e.message)}`;
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--danger);">${err}</td></tr>`;
      if (tree) tree.innerHTML = `<div class="org-tree-empty" style="color:var(--danger);">${err}</div>`;
    }
  }

  // ─── نمایش افرادِ هر واحد — باز/بسته‌شدنِ مستقلِ هر واحد ────────
  async function loadMembers() {
    const tree = await api.get(`/departments/tree?org_id=${state.orgId}&include_members=true`);
    const map = {};
    (function walk(nodes) {
      (nodes || []).forEach(n => { map[n.id] = n.members || []; walk(n.children); });
    })(tree);
    state.membersByDept = map;
    state.membersLoaded = true;
  }

  /** داده‌ی افراد را در صورت نیاز یک‌بار می‌گیرد. true اگر آماده باشد. */
  async function ensureMembersLoaded() {
    if (state.membersLoaded) return true;
    try {
      await loadMembers();
      return true;
    } catch (e) {
      toastError(e.message || 'خطا در بارگذاری افراد');
      return false;
    }
  }

  /** باز/بسته‌کردنِ فهرست افرادِ یک واحدِ مشخص. */
  async function togglePeople(deptId) {
    if (state.membersExpanded.has(deptId)) {
      state.membersExpanded.delete(deptId);
      renderDeptTree();
      return;
    }
    if (!state.membersLoaded) {
      const row = document.querySelector(`.org-tree-row[data-id="${deptId}"] [data-people="${deptId}"]`);
      if (row) row.classList.add('is-loading');
      const ok = await ensureMembersLoaded();
      if (!ok) { renderDeptTree(); return; }
    }
    state.membersExpanded.add(deptId);
    renderDeptTree();
  }

  /** دکمه‌ی سراسری: اگر همه باز باشند همه را ببند، وگرنه همه را باز کن. */
  async function toggleAllPeople() {
    const ok = await ensureMembersLoaded();
    if (!ok) return;
    const withPeople = state.depts.filter(d => (state.membersByDept[d.id] || []).length).map(d => d.id);
    const allOpen = withPeople.length > 0 && withPeople.every(id => state.membersExpanded.has(id));
    state.membersExpanded = new Set(allOpen ? [] : withPeople);
    syncAllPeopleBtn();
    renderDeptTree();
  }

  function syncAllPeopleBtn() {
    const btn = document.getElementById('structMembersToggle');
    if (!btn) return;
    const withPeople = state.depts.filter(d => (state.membersByDept[d.id] || []).length).map(d => d.id);
    const allOpen = withPeople.length > 0 && withPeople.every(id => state.membersExpanded.has(id));
    btn.classList.toggle('active', state.membersExpanded.size > 0);
    btn.textContent = allOpen ? '👥 بستن همه‌ی افراد' : '👥 نمایش همه‌ی افراد';
  }

  // ─── نمای واحدها: جدولی / درختی ─────────────────────────────────
  function setStructTab(tab) {
    state.structTab = tab;
    applyStructTab();
  }

  function applyStructTab() {
    const isTree = state.structTab === 'tree';
    document.querySelectorAll('#structViewToggle .tab-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.structView === state.structTab));
    document.getElementById('deptsTreePane')?.classList.toggle('hidden', !isTree);
    document.getElementById('deptsTablePane')?.classList.toggle('hidden', isTree);
    const bulk = document.getElementById('deptsTreeBulk');
    if (bulk) bulk.classList.toggle('hidden', !isTree || !state.depts.length);
  }

  function deptChildren(parentId) {
    return state.depts
      .filter(d => (d.parent_id || null) === (parentId || null))
      .sort((a, b) => (a.order_index - b.order_index) || (a.name > b.name ? 1 : -1));
  }

  function isDescendant(candidateId, ancestorId) {
    // آیا candidateId زیرمجموعه‌ی ancestorId است؟ (برای جلوگیری از حلقه در drag)
    let stack = deptChildren(ancestorId);
    while (stack.length) {
      const d = stack.pop();
      if (d.id === candidateId) return true;
      stack = stack.concat(deptChildren(d.id));
    }
    return false;
  }

  // ─── نمای جدولی (سلسله‌مراتب با تورفتگی) ────────────────────────
  function renderDeptTable() {
    const tbody = document.getElementById('deptsTableBody');
    if (!state.depts.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--gray-400);">واحدی ثبت نشده</td></tr>`;
      return;
    }
    let html = '';
    (function walk(parentId, depth) {
      deptChildren(parentId).forEach(d => {
        const prefix = depth > 0 ? `<span style="color:var(--gray-300);">${'└'.padStart(depth * 2, ' ')} </span>` : '';
        html += `
          <tr>
            <td style="padding-right:${16 + depth * 18}px;font-weight:500;">${prefix}${esc(d.name)}</td>
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
    })(null, 0);
    tbody.innerHTML = html;
  }

  // ─── نمای درختی گرافیکی (قابل کشیدن‌ورهاکردن) ───────────────────
  function renderDeptTree() {
    const wrap = document.getElementById('deptsTree');
    if (!wrap) return;
    if (!state.depts.length) {
      wrap.innerHTML = `
        <div class="org-tree-empty">
          <div class="org-tree-empty-icon">🗂️</div>
          <div class="org-tree-empty-title">هنوز واحدی تعریف نشده است</div>
          <div class="org-tree-empty-desc">اولین واحد سازمانی (مثلاً «مدیرعامل» یا یک معاونت) را بسازید تا ساختار شکل بگیرد.</div>
          <button class="btn btn-primary" onclick="StructurePage.openCreateDept()">➕ ساخت اولین واحد</button>
        </div>`;
      return;
    }
    wrap.innerHTML = `<div class="org-tree" id="orgTreeRoot">${renderTreeLevel(null, 0)}</div>`;
    bindTreeDnd(wrap);
    if (state.membersExpanded.size) hydrateAuthedImages(wrap);
    syncAllPeopleBtn();
  }

  // ─── رندر بازگشتی افرادِ یک واحد (تودرتو بر اساس سطح پست) ────────
  function renderMembersBlock(deptId) {
    if (!state.membersExpanded.has(deptId)) return '';
    const members = state.membersByDept[deptId] || [];
    if (!members.length) {
      return `<div class="org-tree-members"><div class="org-members-cap">عضوِ فعالی در این واحد نیست</div></div>`;
    }
    return `<div class="org-tree-members">
      <div class="org-members-cap">اعضای واحد — بر اساس مدیر مستقیم (و در نبودِ آن، سطح پست)</div>
      ${renderMemberNodes(members)}
    </div>`;
  }

  function renderMemberNodes(nodes) {
    return nodes.map(m => {
      const hasKids = m.children && m.children.length;
      const avatar = m.avatar_url
        ? `<img class="org-member-av" data-src="${esc(m.avatar_url)}" alt="">`
        : `<span class="org-member-av">${esc(initials(m.full_name || ''))}</span>`;
      const role = m.position_name
        ? `<span class="org-member-role">${esc(m.position_name)}</span>`
        : `<span class="org-member-role is-empty">بدون پست سازمانی</span>`;
      return `
        <div class="org-member-node">
          <div class="org-member-row${m.is_manager ? ' is-manager' : ''}${m.is_active ? '' : ' is-inactive'}">
            ${avatar}
            <span class="org-member-id">
              <span class="org-member-name">${esc(m.full_name)}</span>
              ${role}
            </span>
            <span class="org-member-meta">
              ${m.is_manager ? `<span class="org-member-lead">مدیر واحد</span>` : ''}
              ${m.position_level ? `<span class="org-member-lvl">سطح <b>${numFa(m.position_level)}</b></span>` : ''}
            </span>
          </div>
          ${hasKids ? `<div class="org-member-children">${renderMemberNodes(m.children)}</div>` : ''}
        </div>`;
    }).join('');
  }

  function renderTreeLevel(parentId, depth) {
    const kids = deptChildren(parentId);
    if (!kids.length) return '';
    return kids.map(d => {
      const childKids = deptChildren(d.id);
      const hasKids = childKids.length > 0;
      const isCol = state.collapsed.has(d.id);
      const icon = depth === 0 ? '🏢' : hasKids ? '📂' : '👥';
      const chevron = hasKids
        ? `<button class="org-tree-toggle" data-toggle="${d.id}" aria-label="${isCol ? 'باز کردن' : 'جمع کردن'}">${isCol ? '▸' : '▾'}</button>`
        : `<span class="org-tree-toggle is-empty"></span>`;
      const manager = d.manager_name
        ? `<span class="org-tree-chip"><span aria-hidden="true">👤</span>${esc(d.manager_name)}</span>`
        : `<button class="org-tree-chip is-assign" data-edit="${d.id}"><span aria-hidden="true">＋</span>تعیین مدیر</button>`;
      const inactive = d.is_active ? '' : `<span class="badge badge-inactive">غیرفعال</span>`;
      const peopleOpen = state.membersExpanded.has(d.id);
      const peopleChip = d.user_count > 0
        ? `<button class="org-tree-chip is-people${peopleOpen ? ' is-open' : ''}" data-people="${d.id}"
                   aria-expanded="${peopleOpen}" title="${peopleOpen ? 'بستن فهرست افراد' : 'نمایش افرادِ این واحد'}">
             <span aria-hidden="true">👥</span>${numFa(d.user_count)} نفر
             <span class="org-tree-chip-caret" aria-hidden="true">${peopleOpen ? '▾' : '▸'}</span>
           </button>`
        : `<span class="org-tree-chip"><span aria-hidden="true">👥</span>${numFa(d.user_count)} نفر</span>`;
      return `
        <div class="org-tree-node" data-node="${d.id}">
          <div class="org-tree-row${depth === 0 ? ' is-root' : ''}${d.is_active ? '' : ' is-inactive'}"
               draggable="true" data-id="${d.id}" data-parent="${d.parent_id || ''}" data-name="${esc(d.name)}">
            <span class="org-tree-handle" aria-hidden="true">⠿</span>
            ${chevron}
            <span class="org-tree-icon" aria-hidden="true">${icon}</span>
            <span class="org-tree-name">${esc(d.name)}</span>
            <span class="org-tree-meta">
              ${manager}
              ${peopleChip}
              ${inactive}
            </span>
            <span class="org-tree-actions">
              <button class="btn-action" style="background:var(--primary-light);color:var(--primary-darker);" data-add="${d.id}" title="افزودن زیرواحد">＋ زیرواحد</button>
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-edit="${d.id}" title="ویرایش واحد">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-del="${d.id}" data-name="${esc(d.name)}" title="حذف واحد">حذف</button>
            </span>
          </div>
          ${renderMembersBlock(d.id)}
          ${hasKids && !isCol ? `<div class="org-tree-children">${renderTreeLevel(d.id, depth + 1)}</div>` : ''}
        </div>`;
    }).join('');
  }

  function toggleAllTree(collapse) {
    state.collapsed.clear();
    if (collapse) state.depts.forEach(d => {
      if (deptChildren(d.id).length) state.collapsed.add(d.id);
    });
    renderDeptTree();
  }

  // ─── Drag & Drop روی نمای درختی ────────────────────────────────
  function bindTreeDnd(wrap) {
    wrap.querySelectorAll('.org-tree-row').forEach(row => {
      row.addEventListener('dragstart', e => {
        state.dragId = row.dataset.id;
        row.classList.add('is-dragging');
        e.dataTransfer.effectAllowed = 'move';
        try { e.dataTransfer.setData('text/plain', row.dataset.id); } catch (_) {}
      });
      row.addEventListener('dragend', () => {
        state.dragId = null;
        wrap.querySelectorAll('.org-tree-row').forEach(r =>
          r.classList.remove('is-dragging', 'drop-inside', 'drop-before', 'drop-after'));
      });
      row.addEventListener('dragover', e => {
        if (!state.dragId || state.dragId === row.dataset.id) return;
        if (isDescendant(row.dataset.id, state.dragId)) return; // نگذار زیرِ زیرمجموعه‌ی خودش برود
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const r = row.getBoundingClientRect();
        const zone = (e.clientY - r.top) / r.height;
        row.classList.toggle('drop-before', zone < 0.28);
        row.classList.toggle('drop-after', zone > 0.72);
        row.classList.toggle('drop-inside', zone >= 0.28 && zone <= 0.72);
      });
      row.addEventListener('dragleave', () => {
        row.classList.remove('drop-inside', 'drop-before', 'drop-after');
      });
      row.addEventListener('drop', e => {
        e.preventDefault();
        const mode = row.classList.contains('drop-inside') ? 'inside'
                   : row.classList.contains('drop-before') ? 'before' : 'after';
        row.classList.remove('drop-inside', 'drop-before', 'drop-after');
        applyDrop(state.dragId, row.dataset.id, mode);
      });
    });
  }

  async function applyDrop(dragId, targetId, mode) {
    if (!dragId || dragId === targetId) return;
    const target = state.depts.find(d => d.id === targetId);
    if (!target) return;
    if (isDescendant(targetId, dragId)) return;

    const newParent = mode === 'inside' ? targetId : (target.parent_id || null);
    // فهرست همتایان جدید بدون واحد جابه‌جاشده
    let siblings = deptChildren(newParent).filter(d => d.id !== dragId).map(d => d.id);
    if (mode === 'inside') {
      siblings.push(dragId); // ته لیست زیرواحدها
    } else {
      const at = siblings.indexOf(targetId);
      siblings.splice(mode === 'before' ? at : at + 1, 0, dragId);
    }
    // اگر واقعاً چیزی عوض نشده، بی‌خیال
    const dragged = state.depts.find(d => d.id === dragId);
    const prevParent = dragged.parent_id || null;
    const prevOrder = deptChildren(prevParent).map(d => d.id);
    if (newParent === prevParent && JSON.stringify(prevOrder) === JSON.stringify(siblings)) return;

    const items = siblings.map((id, i) => ({ id, parent_id: newParent, order_index: i }));

    // خوش‌بینانه: state را به‌روز کن و دوباره رندر بگیر
    items.forEach(it => {
      const d = state.depts.find(x => x.id === it.id);
      if (d) { d.parent_id = it.parent_id; d.order_index = it.order_index; }
    });
    if (newParent) state.collapsed.delete(newParent);
    renderDeptTree();

    try {
      await api.patch('/departments/reorder', { items, org_id: state.orgId });
      toastSuccess(`«${esc(dragged.name)}» جابه‌جا شد`);
      await loadDepts();
    } catch (err) {
      toastError(err.message || 'جابه‌جایی ناموفق بود');
      await loadDepts(); // برگرد به وضعیت سرور
    }
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
    // واحدهایی که زیرمجموعه‌ی واحد در حال ویرایش‌اند هم نباید قابل انتخاب باشند (حلقه)
    const blocked = new Set(excludeId ? [excludeId] : []);
    if (excludeId) {
      let stack = deptChildren(excludeId);
      while (stack.length) { const d = stack.pop(); blocked.add(d.id); stack = stack.concat(deptChildren(d.id)); }
    }
    sel.innerHTML = '<option value="">— بدون واحد مادر (سطح اول) —</option>' +
      state.depts.filter(d => !blocked.has(d.id))
        .map(d => `<option value="${d.id}" ${d.id === selectedId ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
  }

  // ─── انتخاب «مدیر واحد» — دراپ‌داون قابل‌سرچ (جستجوی سمت سرور) ────
  // تعداد کاربران سازمان می‌تواند زیاد باشد؛ به‌جای بارگذاری همه، هنگام
  // تایپ یک درخواست debounce‌شده به /users/?search=... زده می‌شود.
  const mgr = {
    box: null, input: null, hidden: null, menu: null,
    debounce: null, open: false, results: [], activeIdx: -1, bound: false,
  };

  function managerChoices() {
    return [{ id: '', full_name: '— بدون مدیر —', department: null }, ...mgr.results];
  }

  function initManagerSelect() {
    if (mgr.bound) return;
    mgr.box = document.getElementById('d-manager-box');
    mgr.input = document.getElementById('d-manager-search');
    mgr.hidden = document.getElementById('d-manager');
    mgr.menu = document.getElementById('d-manager-menu');
    if (!mgr.box || !mgr.input || !mgr.hidden || !mgr.menu) return;

    mgr.input.addEventListener('input', () => {
      mgr.hidden.value = '';           // تایپ آزاد = انتخاب قبلی باطل شد
      openManagerMenu();
      mgr.menu.innerHTML = `<div class="search-select-hint">در حال جستجو…</div>`;
      clearTimeout(mgr.debounce);
      mgr.debounce = setTimeout(() => runManagerSearch(mgr.input.value.trim()), 300);
    });
    mgr.input.addEventListener('focus', () => {
      openManagerMenu();
      runManagerSearch(mgr.input.value.trim());
    });
    mgr.input.addEventListener('keydown', onManagerKeydown);
    mgr.menu.addEventListener('mousedown', (e) => {
      const opt = e.target.closest('[data-uid]');
      if (!opt) return;
      e.preventDefault();                // نگذار input بلور شود
      pickManager(opt.dataset.uid, opt.dataset.name);
    });
    document.addEventListener('click', (e) => {
      if (mgr.open && !mgr.box.contains(e.target)) closeManagerMenu();
    });
    mgr.bound = true;
  }

  function openManagerMenu() {
    if (mgr.open) return;
    mgr.open = true;
    mgr.menu.classList.remove('hidden');
  }
  function closeManagerMenu() {
    mgr.open = false;
    mgr.activeIdx = -1;
    mgr.menu.classList.add('hidden');
  }

  async function runManagerSearch(term) {
    const p = new URLSearchParams({ org_id: state.orgId, per_page: '20' });
    if (term) p.set('search', term);
    try {
      const res = await api.get(`/users/?${p}`);
      mgr.results = res.items || [];
    } catch (_) {
      mgr.results = [];
    }
    mgr.activeIdx = -1;
    renderManagerMenu();
  }

  function renderManagerMenu() {
    if (!mgr.open) return;
    const choices = managerChoices();
    const cur = mgr.hidden.value;
    let html = choices.map((c, i) => `
      <div class="search-select-option${i === mgr.activeIdx ? ' is-active' : ''}${c.id && c.id === cur ? ' is-selected' : ''}"
           data-uid="${esc(c.id)}" data-name="${c.id ? esc(c.full_name) : ''}">
        <span class="search-select-name">${esc(c.full_name)}</span>
        ${c.department ? `<span class="search-select-sub">${esc(c.department)}</span>` : ''}
      </div>`).join('');
    if (choices.length === 1) html += `<div class="search-select-hint">کاربری یافت نشد</div>`;
    mgr.menu.innerHTML = html;
    const act = mgr.menu.querySelector('.search-select-option.is-active');
    if (act) act.scrollIntoView({ block: 'nearest' });
  }

  function onManagerKeydown(e) {
    const choices = managerChoices();
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      openManagerMenu();
      mgr.activeIdx = Math.min(mgr.activeIdx + 1, choices.length - 1);
      renderManagerMenu();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      mgr.activeIdx = Math.max(mgr.activeIdx - 1, 0);
      renderManagerMenu();
    } else if (e.key === 'Enter') {
      if (mgr.open && mgr.activeIdx >= 0) {
        e.preventDefault();
        const c = choices[mgr.activeIdx];
        pickManager(c.id, c.id ? c.full_name : '');
      }
    } else if (e.key === 'Escape') {
      if (mgr.open) { e.preventDefault(); closeManagerMenu(); }
    }
  }

  function pickManager(uid, name) {
    mgr.hidden.value = uid || '';
    mgr.input.value = uid ? (name || '') : '';
    closeManagerMenu();
  }

  /** مقدار اولیه‌ی انتخاب مدیر را تنظیم می‌کند (بدون درخواست شبکه). */
  function setManagerSelection(id, name) {
    initManagerSelect();
    if (!mgr.hidden) return;
    mgr.hidden.value = id || '';
    mgr.input.value = id ? (name || '') : '';
    mgr.results = [];
    mgr.activeIdx = -1;
    clearTimeout(mgr.debounce);
    closeManagerMenu();
  }

  async function openCreateDept(parentId) {
    document.getElementById('deptModalTitle').textContent =
      parentId ? 'زیرواحد جدید' : 'واحد سازمانی جدید';
    document.getElementById('d-id').value = '';
    document.getElementById('d-name').value = '';
    document.getElementById('d-desc').value = '';
    document.getElementById('d-order').value = String(deptChildren(parentId || null).length);
    populateParentDeptSelect(parentId || '', '');
    setManagerSelection('', '');
    openModal('modal-dept');
    document.getElementById('d-name').focus();
  }

  async function openEditDept(id) {
    const d = state.depts.find(x => x.id === id);
    if (!d) return;
    document.getElementById('deptModalTitle').textContent = 'ویرایش واحد سازمانی';
    document.getElementById('d-id').value = d.id;
    document.getElementById('d-name').value = d.name || '';
    document.getElementById('d-desc').value = d.description || '';
    document.getElementById('d-order').value = d.order_index ?? 0;
    populateParentDeptSelect(d.parent_id, d.id);
    setManagerSelection(d.manager_id || '', d.manager_name || '');
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
      manager_id: document.getElementById('d-manager')?.value || null,
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

  // ─── Positions: Excel قالب / خروجی / Import ────────────────────────
  async function downloadPositionTemplate() {
    try {
      await api.download('/positions/template', 'talentick-positions-template.xlsx');
      toastSuccess('فایل Excel دانلود شد');
    } catch (e) { toastError(e.message); }
  }

  async function exportPositionsExcel() {
    try {
      const deptFilter = document.getElementById('posDeptFilter')?.value || '';
      const p = new URLSearchParams({ org_id: state.orgId });
      if (deptFilter) p.set('dept_id', deptFilter);
      await api.download(`/positions/export?${p}`, 'talentick-positions-export.xlsx');
      toastSuccess('فایل Excel دانلود شد');
    } catch (e) { toastError(e.message); }
  }

  function onPositionImportFileChange(inputEl) {
    const file = inputEl.files?.[0];
    setUploadName('pi-file-name', file ? file.name : '', !!file);
  }

  function openPositionImport() {
    document.getElementById('pi-file').value = '';
    setUploadName('pi-file-name', '');
    openModal('modal-position-import');
  }

  async function submitPositionImport() {
    const fileInput = document.getElementById('pi-file');
    const file = fileInput.files?.[0];
    if (!file) { toastError('لطفاً یک فایل Excel انتخاب کنید'); return; }

    const btn = document.getElementById('btn-import-positions');
    setLoading(btn, true);
    try {
      const p = new URLSearchParams({ org_id: state.orgId });
      const result = await api.upload(`/positions/import?${p}`, file);
      closeModal('modal-position-import');
      showPositionImportResult(result);
      await loadPositions();
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function showPositionImportResult(result) {
    document.getElementById('piResultStats').innerHTML = [
      ['کل ردیف‌ها', result.total_rows, 'var(--gray-700)'],
      ['ساخته‌شده', result.created, 'var(--success)'],
      ['به‌روزرسانی‌شده', result.updated, 'var(--primary)'],
      ['رد‌شده / خطا', result.skipped + (result.errors?.length || 0), 'var(--danger)'],
    ].map(([label, value, color]) => `
      <div class="stat-card"><div class="stat-card-info"><div class="stat-card-label">${label}</div><div class="stat-card-value" style="color:${color};">${numFa(value)}</div></div></div>
    `).join('');

    const errorsWrap = document.getElementById('piResultErrorsWrap');
    const errorsList = document.getElementById('piResultErrorsList');
    if (result.errors?.length) {
      errorsWrap.classList.remove('hidden');
      errorsList.innerHTML = result.errors.map(er => `
        <div style="font-size:12.5px;color:var(--danger);background:#FEF2F2;border-radius:var(--radius-sm);padding:8px 10px;">
          سطر ${numFa(er.row)}${er.name ? ' (' + esc(er.name) + ')' : ''}: ${esc(er.message)}
        </div>`).join('');
    } else {
      errorsWrap.classList.add('hidden');
    }

    openModal('modal-position-import-result');
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
  function setUploadName(id, name, hasFile = !!name) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = name || 'فایلی انتخاب نشده';
    el.classList.toggle('has-file', hasFile);
  }

  // ─── Delegated Row Actions — به‌جای onclick اینلاین با نام کاربر ──────
  document.getElementById('deptsTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-dept"]');
    if (btn) removeDept(btn.dataset.id, btn.dataset.title);
  });
  document.getElementById('positionsTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-position"]');
    if (btn) removePosition(btn.dataset.id, btn.dataset.title);
  });

  // ─── نمای درختی — کلیک روی chevron / دکمه‌های عملیات ─────────────
  document.getElementById('deptsTree')?.addEventListener('click', (e) => {
    const t = e.target.closest('[data-toggle],[data-people],[data-add],[data-edit],[data-del]');
    if (!t) return;
    if (t.dataset.toggle) {
      const id = t.dataset.toggle;
      state.collapsed.has(id) ? state.collapsed.delete(id) : state.collapsed.add(id);
      renderDeptTree();
    } else if (t.dataset.people) {
      togglePeople(t.dataset.people);
    } else if (t.dataset.add) {
      openCreateDept(t.dataset.add);
    } else if (t.dataset.edit) {
      openEditDept(t.dataset.edit);
    } else if (t.dataset.del) {
      removeDept(t.dataset.del, t.dataset.name);
    }
  });

  return {
    openFor, loadOwn,
    setStructTab, toggleAllTree, toggleAllPeople,
    openCreateDept, openEditDept, saveDept, removeDept,
    openCreatePosition, openEditPosition, savePosition, removePosition,
    loadPositions,
    downloadPositionTemplate, exportPositionsExcel, openPositionImport,
    onPositionImportFileChange, submitPositionImport,
  };
})();
