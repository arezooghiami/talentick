// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «دید کلی» (داشبورد)
// ════════════════════════════════════════════════════════════════════

const DashboardPage = (() => {
  let chart = null;

  async function load() {
    if (App.isSuperAdmin) {
      await loadSuperAdminDashboard();
    } else {
      await loadOrgDashboard();
    }
  }

  // ─── super_admin: آمار کامل پلتفرم + نمودار + کاربران برتر + تیکت‌ها ──
  async function loadSuperAdminDashboard() {
    document.getElementById('dash-super').classList.remove('hidden');
    document.getElementById('dash-org').classList.add('hidden');
    try {
      const d = await api.get('/dashboard/super-admin');
      setText('statActiveUsers', numFa(d.stats.active_users));
      setText('statCourses', numFa(d.stats.content?.courses ?? 0));
      setText('statPodcasts', numFa(d.stats.content?.podcasts ?? 0));
      setText('statBooks', numFa(d.stats.content?.books ?? 0));
      setText('statCompletedDocs', numFa(d.stats.completion?.completed_docs ?? 0));
      setText('statCompletedCourses', numFa(d.stats.completion?.completed_courses ?? 0));
      setText('statCompletedQuizzes', numFa(d.stats.completion?.completed_quizzes ?? 0));
      setText('statReward', numFa(d.stats.total_reward_points ?? 0));
      drawChart(d.user_growth);
      renderTopUsers(d.top_users);
      renderTickets(d.recent_tickets);
    } catch (e) {
      toastError('خطا در بارگذاری داشبورد: ' + e.message);
    }
  }

  function drawChart(data) {
    const ctx = document.getElementById('userGrowthChart').getContext('2d');
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(p => p.label),
        datasets: [{
          data: data.map(p => p.count), borderColor: '#6C4CF1', borderWidth: 2.5,
          tension: 0.4, pointRadius: 4, pointBackgroundColor: '#6C4CF1',
          pointBorderColor: '#fff', pointBorderWidth: 2, fill: true,
          backgroundColor: (c) => {
            const g = c.chart.ctx.createLinearGradient(0, 0, 0, 200);
            g.addColorStop(0, 'rgba(108,99,255,.16)'); g.addColorStop(1, 'rgba(108,99,255,0)'); return g;
          },
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { rtl: true, callbacks: { label: c => ` ${numFa(c.parsed.y)} کاربر` } } },
        scales: {
          x: { grid: { color: 'rgba(0,0,0,.04)' }, ticks: { font: { family: 'Vazirmatn', size: 11 }, color: '#9CA3AF' } },
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,.04)' }, ticks: { font: { family: 'Vazirmatn', size: 11 }, color: '#9CA3AF', precision: 0 } },
        },
      },
    });
  }

  function renderTopUsers(users) {
    const el = document.getElementById('topUsersList');
    if (!users.length) {
      el.innerHTML = '<p style="text-align:center;color:var(--gray-400);font-size:13px;padding:20px 0;">هنوز کاربری ثبت نشده</p>';
      return;
    }
    el.innerHTML = users.map(u => `
      <div class="user-list-item">
        <div class="user-avatar">${initials(u.full_name)}</div>
        <div style="min-width:0;flex:1;">
          <div class="user-name">${esc(u.full_name)}</div>
          <div class="user-meta">${esc(u.org_name)} · ${roleLabel(u.role)}</div>
        </div>
        ${u.quiz_score > 0 ? `<div class="user-score">${numFa(u.quiz_score)}</div>` : ''}
      </div>`).join('');
  }

  function renderTickets(tickets) {
    const el = document.getElementById('ticketsRow');
    if (!tickets.length) { el.innerHTML = ''; return; }
    el.innerHTML = tickets.map(t => `
      <div class="ticket-card">
        <div class="ticket-user">${esc(t.user_name)}</div>
        <div class="ticket-status">${esc(t.status)}</div>
        <div class="ticket-stars">${[1, 2, 3, 4, 5].map(i => `<span class="star${i > t.rating ? ' empty' : ''}">★</span>`).join('')}</div>
      </div>`).join('');
  }

  // ─── org_admin / manager: آمار سازمان خودشان ──────────────────────
  async function loadOrgDashboard() {
    document.getElementById('dash-super').classList.add('hidden');
    document.getElementById('dash-org').classList.remove('hidden');
    try {
      // تا زمانی‌که endpoint آماری مخصوص داشبورد سازمان ساخته شود،
      // آمار از روی لیست کاربران سازمان (org-scoped) محاسبه می‌شود.
      const d = await api.get('/users/?per_page=100');
      const items = d.items || [];
      setText('orgStatTotal', numFa(d.total ?? items.length));
      setText('orgStatActive', numFa(items.filter(u => u.is_active).length));
      setText('orgStatInactive', numFa(items.filter(u => !u.is_active).length));
      setText('orgStatManagers', numFa(items.filter(u => u.role === 'org_admin' || u.role === 'manager').length));
    } catch (e) {
      toastError('خطا در بارگذاری داشبورد: ' + e.message);
    }
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  return { load };
})();