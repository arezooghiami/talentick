// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «گزارش‌ها» (Reports)
// ════════════════════════════════════════════════════════════════════
// org_admin/super_admin: آمار مشارکت + گزارش محتوا/کاربران (+ سازمان‌ها
// فقط برای super_admin). دسترسی این بخش در بک‌اند OrgAdmin+ است —
// manager به این صفحه دسترسی ندارد (نوار کناری هم بر همین اساس فیلتر می‌شود).

const ReportsPage = (() => {
  const state = { contentRows: [], userRows: [], orgRows: [] };

  async function load() {
    await Promise.all([loadStats(), loadContentReport(), loadUserReport()]);
    if (App.isSuperAdmin) await loadOrgReport();
  }

  async function loadStats() {
    try {
      const d = await api.get('/reports/dashboard');
      setText('repTotalContents', numFa(d.total_contents));
      setText('repEligibleUsers', numFa(d.total_eligible_users));
      setText('repCompletionRate', numFa(d.completion_rate) + '٪');
      setText('repAvgProgress', numFa(d.avg_progress_pct) + '٪');
    } catch (e) {
      toastError('خطا در بارگذاری آمار: ' + e.message);
    }
  }

  async function loadContentReport() {
    const tbody = document.getElementById('repContentTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const rows = await api.get('/reports/contents');
      state.contentRows = rows || [];
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--gray-400);">هنوز محتوای منتشرشده‌ای وجود ندارد</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td style="font-weight:600;">${esc(r.title)}</td>
          <td>${TYPE_LABELS?.[r.type] || r.type}</td>
          <td>${numFa(r.eligible_count)}</td>
          <td>${numFa(r.viewed_count)}</td>
          <td>${numFa(r.completed_count)}</td>
          <td>
            <div style="display:flex;align-items:center;gap:8px;">
              <div style="flex:1;background:var(--gray-100);border-radius:99px;height:6px;min-width:60px;overflow:hidden;">
                <div style="width:${numClamp(r.avg_progress_pct)}%;background:var(--primary);height:100%;"></div>
              </div>
              <span style="font-size:12px;color:var(--gray-500);">${numFa(r.avg_progress_pct)}٪</span>
              <button class="btn-icon" title="جزئیات" onclick="ReportsPage.openDetail('${r.content_id}')">🔍</button>
            </div>
          </td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  async function loadUserReport() {
    const tbody = document.getElementById('repUsersTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const rows = await api.get('/reports/users');
      state.userRows = rows || [];
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--gray-400);">کاربری یافت نشد</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td><div style="display:flex;align-items:center;gap:8px;"><div class="user-avatar">${initials(r.full_name)}</div><span style="font-weight:500;">${esc(r.full_name)}</span></div></td>
          <td style="color:var(--gray-500);">${r.department ? esc(r.department) : '—'}</td>
          <td>${numFa(r.eligible_count)}</td>
          <td>${numFa(r.started_count)}</td>
          <td>${numFa(r.completed_count)}</td>
          <td style="color:var(--gray-500);">${r.last_activity_at ? fmtDate(r.last_activity_at) : 'بدون فعالیت'}</td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  async function loadOrgReport() {
    const tbody = document.getElementById('repOrgsTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const rows = await api.get('/reports/organizations');
      state.orgRows = rows || [];
      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--gray-400);">سازمانی یافت نشد</td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td style="font-weight:600;">${esc(r.org_name)}</td>
          <td>${numFa(r.contents_count)}</td>
          <td>${numFa(r.users_count)}</td>
          <td>${numFa(r.completed_count)}</td>
          <td>${numFa(r.avg_progress_pct)}٪</td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  // ─── Content Drill-down Modal ───────────────────────────────────
  async function openDetail(contentId) {
    const row = state.contentRows.find(r => r.content_id === contentId);
    document.getElementById('reportDetailTitle').textContent = row ? `گزارش تفصیلی — ${row.title}` : 'گزارش تفصیلی';
    openModal('modal-report-detail');
    const tbody = document.getElementById('repDetailTableBody');
    tbody.innerHTML = `<tr><td colspan="4" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const detail = await api.get(`/reports/contents/${contentId}`);
      if (!detail.users.length) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--gray-400);">هیچ کاربر مجازی برای این محتوا یافت نشد</td></tr>`;
        return;
      }
      const STATUS_FA = { not_started: 'شروع‌نشده', in_progress: 'در حال انجام', completed: 'تکمیل‌شده' };
      tbody.innerHTML = detail.users.map(u => `
        <tr>
          <td><div style="font-weight:500;">${esc(u.full_name)}</div><div style="font-size:11px;color:var(--gray-400);direction:ltr;text-align:right;">${esc(u.email)}</div></td>
          <td style="color:var(--gray-500);">${u.department ? esc(u.department) : '—'}</td>
          <td>${STATUS_FA[u.status] || u.status}</td>
          <td>${numFa(u.progress_pct)}٪</td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function showTab(tabId, btnEl) {
    document.querySelectorAll('#view-reports .tab-btn').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
    document.querySelectorAll('#view-reports .tab-content').forEach(tc => tc.classList.toggle('active', tc.id === tabId));
  }

  function numClamp(n) { return Math.max(0, Math.min(100, n || 0)); }
  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  return { load, openDetail, showTab };
})();
