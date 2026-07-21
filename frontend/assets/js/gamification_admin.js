// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «گیمیفیکیشن» (Rule Engine + Priority Engine) — super_admin
// ════════════════════════════════════════════════════════════════════
// ۱) انواع Event و مقدار پیش‌فرض سراسری (point_rules) — Event Driven،
//    می‌توان نوع Event جدید بدون نیاز به تغییر کد اضافه کرد.
// ۲) استثناهای امتیازدهی (point_policy_rules) — Priority Engine ۴سطحی:
//    User > Position > Department > Organization، با امکان ترکیب
//    هم‌زمان چند شرط. override اختصاصی هر موجودیت (آزمون/محتوا/...) از
//    طریق فرم خود همان موجودیت تنظیم می‌شود، نه اینجا.

const GamificationPage = (() => {
  const state = { rules: [], policyRules: [], orgs: [] };

  async function load() {
    await Promise.all([loadRules(), loadOrgs()]);
    await loadPolicyRules();
  }

  // ─── Rules (انواع Event + مقدار پیش‌فرض) ───────────────────────────

  async function loadRules() {
    const tbody = document.getElementById('gmRulesTableBody');
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      state.rules = await api.get('/points/rules');
      renderRulesTable();
      renderEventTypeOptions();
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function renderRulesTable() {
    document.getElementById('gmRulesTableBody').innerHTML = state.rules.map(r => `
      <tr>
        <td style="font-family:monospace;font-size:12px;color:var(--gray-500);">${esc(r.event_type)}</td>
        <td style="font-weight:500;">${esc(r.event_label)}</td>
        <td><input type="number" class="form-control" style="width:110px;" min="0" max="100000" value="${r.points}" data-role="rule-points" data-id="${r.id}"></td>
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
    const sel = document.getElementById('prEventType');
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

  function openCreateRule() {
    document.getElementById('rl-event-type').value = '';
    document.getElementById('rl-label').value = '';
    document.getElementById('rl-points').value = '0';
    openModal('modal-rule');
  }

  async function saveNewRule() {
    const eventType = document.getElementById('rl-event-type').value.trim();
    const label = document.getElementById('rl-label').value.trim();
    const points = parseInt(document.getElementById('rl-points').value, 10) || 0;
    if (!/^[a-z][a-z0-9_]*$/.test(eventType)) { toastError('شناسه‌ی Event باید با حرف کوچک لاتین شروع شود و فقط شامل حروف/عدد/آندرلاین باشد'); return; }
    if (!label) { toastError('برچسب فارسی را وارد کنید'); return; }

    const btn = document.getElementById('btn-save-rule');
    setLoading(btn, true);
    try {
      await api.post('/points/rules', { event_type: eventType, event_label: label, points });
      toastSuccess('نوع Event جدید ساخته شد');
      closeModal('modal-rule');
      await loadRules();
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  // ─── Policy Rules (Priority Engine) ────────────────────────────────

  const TIER_LABEL_FA = { user: 'کاربر خاص', position: 'سمت خاص', department: 'واحد خاص', organization: 'سازمان خاص' };

  async function loadPolicyRules() {
    const tbody = document.getElementById('prTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      state.policyRules = await api.get('/points/policy-rules');
      renderPolicyRulesTable();
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function conditionSummary(r) {
    const parts = [];
    if (r.org_name) parts.push(`سازمان: ${esc(r.org_name)}`);
    if (r.dept_name) parts.push(`واحد: ${esc(r.dept_name)}`);
    if (r.position_name) parts.push(`سمت: ${esc(r.position_name)}`);
    if (r.user_name) parts.push(`کاربر: ${esc(r.user_name)}`);
    return parts.join(' + ') || '—';
  }

  function renderPolicyRulesTable() {
    const tbody = document.getElementById('prTableBody');
    if (!state.policyRules.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--gray-400);">هیچ استثنایی ثبت نشده</td></tr>`;
      return;
    }
    tbody.innerHTML = state.policyRules.map(r => `
      <tr>
        <td style="font-weight:500;">${esc(r.event_label)}</td>
        <td>${TIER_LABEL_FA[r.tier] || esc(r.tier)}</td>
        <td style="font-size:12.5px;color:var(--gray-600);">${conditionSummary(r)}</td>
        <td>${numFa(r.points)}</td>
        <td>${statusBadge(r.is_active)}</td>
        <td><button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-policy-rule" data-id="${r.id}">حذف</button></td>
      </tr>`).join('');
  }

  async function loadOrgs() {
    const orgSelects = ['prOrg', 'rw-org', 'rwOrgFilter', 'rdOrgFilter'].map(id => document.getElementById(id)).filter(Boolean);
    if (!orgSelects.length) return;
    try {
      const cached = OrgsPage.getCache();
      state.orgs = cached && cached.length ? cached : await api.get('/orgs/');
      const prOrg = document.getElementById('prOrg');
      if (prOrg) prOrg.innerHTML = `<option value="">— بدون شرط —</option>` + state.orgs.map(o => `<option value="${esc(o.id)}">${esc(o.name)}</option>`).join('');
    } catch { /* اختیاری */ }
  }

  async function onOrgChange() {
    const orgId = document.getElementById('prOrg').value;
    const deptSel = document.getElementById('prDept');
    const posSel = document.getElementById('prPosition');
    const userSel = document.getElementById('prUser');
    if (!orgId) {
      deptSel.innerHTML = `<option value="">— بدون شرط —</option>`;
      posSel.innerHTML = `<option value="">— بدون شرط —</option>`;
      userSel.innerHTML = `<option value="">— بدون شرط —</option>`;
      return;
    }
    deptSel.innerHTML = `<option value="">در حال بارگذاری...</option>`;
    posSel.innerHTML = `<option value="">در حال بارگذاری...</option>`;
    userSel.innerHTML = `<option value="">در حال بارگذاری...</option>`;
    try {
      const [depts, positions, usersRes] = await Promise.all([
        api.get(`/departments/?org_id=${orgId}`),
        api.get(`/positions/?org_id=${orgId}`),
        api.get(`/users/?org_id=${orgId}&per_page=100`),
      ]);
      deptSel.innerHTML = `<option value="">— بدون شرط —</option>` + depts.map(d => `<option value="${esc(d.id)}">${esc(d.name)}</option>`).join('');
      posSel.innerHTML = `<option value="">— بدون شرط —</option>` + positions.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
      userSel.innerHTML = `<option value="">— بدون شرط —</option>` + (usersRes.items || []).map(u => `<option value="${esc(u.id)}">${esc(u.full_name)}</option>`).join('');
    } catch (e) {
      toastError('خطا در بارگذاری واحد/سمت/کاربر: ' + e.message);
    }
  }

  function onDeptChange() { /* واحد مستقل انتخاب می‌شود — سمت/کاربر همچنان بر اساس کل سازمان لیست شده‌اند */ }

  async function addPolicyRule() {
    const eventType = document.getElementById('prEventType').value;
    const points = parseInt(document.getElementById('prPoints').value, 10);
    const orgId = document.getElementById('prOrg').value || null;
    const deptId = document.getElementById('prDept').value || null;
    const positionId = document.getElementById('prPosition').value || null;
    const userId = document.getElementById('prUser').value || null;
    const priority = parseInt(document.getElementById('prPriority').value, 10) || 0;

    if (isNaN(points) || points < 0) { toastError('مقدار امتیاز نامعتبر است'); return; }
    if (!orgId && !deptId && !positionId && !userId) { toastError('حداقل یکی از سازمان/واحد/سمت/کاربر را انتخاب کنید'); return; }

    const btn = document.getElementById('btn-prAdd');
    setLoading(btn, true);
    try {
      await api.post('/points/policy-rules', {
        event_type: eventType, points, priority,
        org_id: orgId, dept_id: deptId, position_id: positionId, user_id: userId,
      });
      toastSuccess('استثنا ذخیره شد');
      document.getElementById('prPoints').value = '';
      await loadPolicyRules();
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  function deletePolicyRule(id) {
    confirmAction(
      'آیا مطمئن هستید که می‌خواهید این استثنا را حذف کنید؟ پس از حذف، امتیاز طبق سطح بعدیِ Priority Engine (یا مقدار پیش‌فرض) محاسبه می‌شود.',
      async () => {
        await api.delete(`/points/policy-rules/${id}`);
        toastSuccess('استثنا حذف شد');
        await loadPolicyRules();
      }
    );
  }

  document.getElementById('gmRulesTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="save-rule"]');
    if (btn) saveRule(btn.dataset.id);
  });

  document.getElementById('prTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-policy-rule"]');
    if (btn) deletePolicyRule(btn.dataset.id);
  });

  return { load, openCreateRule, saveNewRule, addPolicyRule, onOrgChange, onDeptChange };
})();
