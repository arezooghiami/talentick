// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «گیمیفیکیشن» (مقدار امتیاز هر نوع اتفاق) — super_admin
// ════════════════════════════════════════════════════════════════════
// سراسری — روی همه‌ی سازمان‌ها یکسان اعمال می‌شود. فقط ۵ نوع اتفاق ثابت
// (از قبل seed شده) قابل ویرایش‌اند — نمی‌شود نوع جدید ساخت (نیاز به
// کد جدید در backend دارد، نه فقط تنظیمات).
//
// Override اختصاصی هر موجودیت (آزمون/محتوا/آیتم/مرحله/برنامه) از طریق
// فرم خود همان موجودیت تنظیم می‌شود، نه اینجا. اینجا فقط دو چیز است:
// ۱) مقدار پیش‌فرض سراسری هر نوع اتفاق (rules)
// ۲) override گروهی برای یک نقش یا واحد سازمانی (group overrides)

const GamificationPage = (() => {
  const state = { rules: [], overrides: [], orgs: [], deptsByOrg: {} };

  async function load() {
    await Promise.all([loadRules(), loadOverrides(), loadOrgs()]);
  }

  async function loadRules() {
    const tbody = document.getElementById('gmRulesTableBody');
    tbody.innerHTML = `<tr><td colspan="4" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      state.rules = await api.get('/points/rules');
      renderTable();
      renderEventTypeOptions();
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function renderTable() {
    document.getElementById('gmRulesTableBody').innerHTML = state.rules.map(r => `
      <tr>
        <td style="font-weight:500;">${esc(r.event_label)}</td>
        <td><input type="number" class="form-control" style="width:110px;" min="0" max="1000" value="${r.points}" data-role="rule-points" data-id="${r.id}"></td>
        <td>
          <label style="display:inline-flex;align-items:center;gap:8px;cursor:pointer;">
            <input type="checkbox" data-role="rule-active" data-id="${r.id}" ${r.is_active ? 'checked' : ''}>
            ${statusBadge(r.is_active)}
          </label>
        </td>
        <td><button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" data-role="save-rule" data-id="${r.id}">ذخیره</button></td>
      </tr>`).join('');
  }

  function renderEventTypeOptions() {
    const sel = document.getElementById('gmOvEventType');
    if (!sel) return;
    sel.innerHTML = state.rules.map(r => `<option value="${esc(r.event_type)}">${esc(r.event_label)}</option>`).join('');
  }

  async function saveRule(id) {
    const pointsInput = document.querySelector(`[data-role="rule-points"][data-id="${id}"]`);
    const activeInput = document.querySelector(`[data-role="rule-active"][data-id="${id}"]`);
    const points = parseInt(pointsInput.value, 10);
    if (isNaN(points) || points < 0) { toastError('مقدار امتیاز نامعتبر است'); return; }
    try {
      await api.patch(`/points/rules/${id}`, { points, is_active: activeInput.checked });
      toastSuccess('ذخیره شد');
      await loadRules();
    } catch (e) { toastError(e.message); }
  }

  // ─── Override های گروهی (نقش / واحد سازمانی) ──────────────────────────

  async function loadOverrides() {
    const tbody = document.getElementById('gmOverridesTableBody');
    tbody.innerHTML = `<tr><td colspan="4" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      state.overrides = await api.get('/points/group-overrides');
      renderOverridesTable();
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function renderOverridesTable() {
    const tbody = document.getElementById('gmOverridesTableBody');
    if (!state.overrides.length) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--gray-400);">هیچ override گروهی ثبت نشده</td></tr>`;
      return;
    }
    tbody.innerHTML = state.overrides.map(o => `
      <tr>
        <td style="font-weight:500;">${esc(o.event_label)}</td>
        <td>${o.target_type === 'role' ? 'نقش' : 'واحد'}: ${esc(o.target_label || o.target_value)}</td>
        <td>${numFa(o.points)}</td>
        <td><button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-override" data-id="${o.id}">حذف</button></td>
      </tr>`).join('');
  }

  async function loadOrgs() {
    const sel = document.getElementById('gmOvOrg');
    if (!sel) return;
    try {
      const cached = OrgsPage.getCache();
      state.orgs = cached && cached.length ? cached : await api.get('/orgs/');
      sel.innerHTML = `<option value="">— انتخاب سازمان —</option>` + state.orgs.map(o => `<option value="${esc(o.id)}">${esc(o.name)}</option>`).join('');
    } catch (e) { /* سازمان‌ها بعداً هم قابل بارگذاری‌اند */ }
  }

  async function loadDeptsForOrg(orgId) {
    const sel = document.getElementById('gmOvDept');
    if (!orgId) { sel.innerHTML = `<option value="">— ابتدا سازمان را انتخاب کنید —</option>`; return; }
    sel.innerHTML = `<option value="">در حال بارگذاری...</option>`;
    try {
      const depts = state.deptsByOrg[orgId] || (state.deptsByOrg[orgId] = await api.get(`/departments/?org_id=${orgId}`));
      sel.innerHTML = depts.length
        ? depts.map(d => `<option value="${esc(d.id)}">${esc(d.name)}</option>`).join('')
        : `<option value="">— این سازمان واحدی ندارد —</option>`;
    } catch (e) {
      sel.innerHTML = `<option value="">خطا در بارگذاری واحدها</option>`;
    }
  }

  function onTargetTypeChange() {
    const isDept = document.getElementById('gmOvTargetType').value === 'department';
    document.getElementById('gmOvRoleWrap').classList.toggle('hidden', isDept);
    document.getElementById('gmOvDeptWrap').classList.toggle('hidden', !isDept);
  }

  async function addGroupOverride() {
    const eventType = document.getElementById('gmOvEventType').value;
    const targetType = document.getElementById('gmOvTargetType').value;
    const points = parseInt(document.getElementById('gmOvPoints').value, 10);
    if (isNaN(points) || points < 0) { toastError('مقدار امتیاز نامعتبر است'); return; }

    let targetValue;
    if (targetType === 'role') {
      targetValue = document.getElementById('gmOvRole').value;
    } else {
      targetValue = document.getElementById('gmOvDept').value;
      if (!targetValue) { toastError('ابتدا سازمان و واحد سازمانی را انتخاب کنید'); return; }
    }

    const btn = document.getElementById('btn-gmOvAdd');
    setLoading(btn, true);
    try {
      await api.post('/points/group-overrides', { event_type: eventType, target_type: targetType, target_value: targetValue, points });
      toastSuccess('override ذخیره شد');
      document.getElementById('gmOvPoints').value = '';
      await loadOverrides();
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  function removeOverride(id) {
    confirmAction(
      'آیا مطمئن هستید که می‌خواهید این override را حذف کنید؟ پس از حذف، امتیاز این گروه به مقدار پیش‌فرض (یا سایر override های فعال) بازمی‌گردد.',
      async () => {
        await api.delete(`/points/group-overrides/${id}`);
        toastSuccess('override حذف شد');
        await loadOverrides();
      }
    );
  }

  document.getElementById('gmRulesTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="save-rule"]');
    if (btn) saveRule(btn.dataset.id);
  });

  document.getElementById('gmOverridesTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-override"]');
    if (btn) removeOverride(btn.dataset.id);
  });

  document.getElementById('gmOvTargetType')?.addEventListener('change', onTargetTypeChange);
  document.getElementById('gmOvOrg')?.addEventListener('change', (e) => loadDeptsForOrg(e.target.value));

  return { load, addGroupOverride };
})();
