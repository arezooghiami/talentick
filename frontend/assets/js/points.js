// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «باشگاه امتیازات» (کارمند)
// ════════════════════════════════════════════════════════════════════
// کیف‌پول + تاریخچه‌ی تراکنش‌ها + فروشگاه جایزه + درخواست‌های تبدیل من.

const MyPointsPage = (() => {
  const state = { tab: 'history', historyPage: 1, catalogPage: 1, catalogSearch: '', redemptionsPage: 1 };
  let searchDebounce;

  async function load() {
    await Promise.all([loadWallet(), loadHistory(1)]);
  }

  function switchTab(tab) {
    state.tab = tab;
    document.querySelectorAll('#ptTabs .org-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.ptTab === tab));
    document.querySelectorAll('.org-tab-panel').forEach(p => p.classList.toggle('active', p.id === `pt-tab-${tab}`));
    if (tab === 'catalog' && !state.catalogLoaded) { state.catalogLoaded = true; loadCatalog(1); }
    if (tab === 'redemptions' && !state.redemptionsLoaded) { state.redemptionsLoaded = true; loadRedemptions(1); }
  }

  // ─── کیف پول ────────────────────────────────────────────────────────

  async function loadWallet() {
    try {
      const w = await api.get('/me/points/wallet');
      document.getElementById('ptTotal').textContent = numFa(w.current_balance);
      document.getElementById('ptWalletStats').innerHTML = [
        ['کسب‌شده', w.total_earned],
        ['مصرف‌شده', w.total_spent],
        ['در انتظار تایید', w.pending_points],
        ['جوایز دریافتی', w.redeemed_points],
      ].map(([label, val]) => `
        <div class="wallet-stat-card">
          <div class="wallet-stat-value">${numFa(val)}</div>
          <div class="wallet-stat-label">${label}</div>
        </div>`).join('');
    } catch {
      document.getElementById('ptTotal').textContent = '—';
    }
  }

  // ─── تاریخچه‌ی تراکنش‌ها ────────────────────────────────────────────

  async function loadHistory(page) {
    state.historyPage = page;
    const list = document.getElementById('ptHistory');
    list.innerHTML = '<div class="emp-skeleton" style="height:60px;"></div><div class="emp-skeleton" style="height:60px;"></div><div class="emp-skeleton" style="height:60px;"></div>';
    try {
      const res = await api.get(`/me/points/history?page=${page}&page_size=20`);
      if (!res.items.length) {
        list.innerHTML = `<div class="emp-empty"><div class="icon">🏆</div><h3>هنوز تراکنشی ثبت نشده</h3><p style="color:var(--gray-400);font-size:13px;margin-top:6px;">با تکمیل محتوا، قبولی در آزمون یا پیشرفت در آنبوردینگ شروع کنید</p></div>`;
        renderPagination('ptPagination', res.page, res.total_pages, loadHistory);
        return;
      }
      list.innerHTML = res.items.map(renderEntry).join('');
      renderPagination('ptPagination', res.page, res.total_pages, loadHistory);
    } catch (e) {
      list.innerHTML = `<div class="emp-empty"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
    }
  }

  function renderEntry(e) {
    const negative = e.points < 0;
    return `
      <div class="item-card" style="cursor:default;">
        <div class="item-card-icon">${negative ? '🎁' : '🏆'}</div>
        <div class="item-card-info">
          <div class="item-card-title">${esc(e.event_label)}</div>
          <div class="item-card-meta">${e.reference_title ? esc(e.reference_title) + ' • ' : ''}${e.transaction_number} • ${fmtDate(e.created_at)}</div>
        </div>
        <span class="points-history-points ${negative ? 'negative' : ''}">${negative ? '' : '+'}${numFa(e.points)}</span>
      </div>`;
  }

  // ─── فروشگاه جایزه ──────────────────────────────────────────────────

  function debouncedCatalogSearch() {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.catalogSearch = document.getElementById('ptCatalogSearch').value.trim();
      loadCatalog(1);
    }, 350);
  }

  async function loadCatalog(page) {
    state.catalogPage = page;
    const grid = document.getElementById('ptCatalogGrid');
    grid.innerHTML = '<div class="emp-skeleton" style="height:220px;"></div><div class="emp-skeleton" style="height:220px;"></div>';
    try {
      const qs = new URLSearchParams({ page, page_size: 12 });
      if (state.catalogSearch) qs.set('search', state.catalogSearch);
      const res = await api.get(`/me/rewards?${qs}`);
      if (!res.items.length) {
        grid.innerHTML = `<div class="emp-empty" style="grid-column:1/-1;"><div class="icon">🎁</div><h3>در حال حاضر جایزه‌ای موجود نیست</h3></div>`;
        document.getElementById('ptCatalogPagination').innerHTML = '';
        return;
      }
      grid.innerHTML = res.items.map(renderRewardCard).join('');
      renderPagination('ptCatalogPagination', res.page, res.total_pages, loadCatalog);
    } catch (e) {
      grid.innerHTML = `<div class="emp-empty" style="grid-column:1/-1;"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
    }
  }

  function renderRewardCard(r) {
    return `
      <div class="content-card">
        <div class="content-card-thumb reward-card-thumb type-book">
          <span class="reward-card-cost">🏆 ${numFa(r.cost_points)} امتیاز</span>
          ${r.image_url ? `<img src="${esc(r.image_url)}" alt="">` : '🎁'}
        </div>
        <div class="content-card-body">
          <div class="content-card-title">${esc(r.title)}</div>
          <div class="content-card-meta">${esc(r.category_label)}${r.inventory_remaining != null ? ' • ' + numFa(r.inventory_remaining) + ' باقی‌مانده' : ''}</div>
          <div class="reward-card-actions">
            <button class="btn btn-primary" data-role="redeem" data-id="${r.id}" data-title="${esc(r.title)}" data-cost="${r.cost_points}">درخواست تبدیل</button>
          </div>
        </div>
      </div>`;
  }

 async function requestRedeem(rewardId, title, cost) {
  function faToEn(str) {
  return str.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
}

const balance = parseInt(
  faToEn(document.getElementById('ptTotal').textContent.trim()),
  10
) || 0;

  console.log('Balance:', balance);
  console.log('Cost:', cost);

  if (balance < cost) {
    toastError('موجودی امتیاز شما برای این جایزه کافی نیست');
    return;
  }

  if (!confirm(`آیا مطمئن هستید که می‌خواهید «${title}» را با ${cost} امتیاز درخواست کنید؟`)) {
    return;
  }

  try {
    await api.post('/me/redemptions', {
      reward_id: rewardId,
      quantity: 1,
      submit: true
    });

    toastSuccess('درخواست شما ثبت و برای بررسی ارسال شد');

    await Promise.all([
      loadWallet(),
      loadCatalog(state.catalogPage)
    ]);

    state.redemptionsLoaded = false;

  } catch (e) {
    console.error('Redeem Error:', e);
    console.error('Response:', e.response?.data);

    toastError(
      e.response?.data?.detail ||
      e.message ||
      'خطا در ثبت درخواست'
    );
  }
}

  // ─── درخواست‌های تبدیل من ───────────────────────────────────────────

  async function loadRedemptions(page) {
    state.redemptionsPage = page;
    state.redemptionsLoaded = true;
    const list = document.getElementById('ptRedemptions');
    list.innerHTML = '<div class="emp-skeleton" style="height:70px;"></div><div class="emp-skeleton" style="height:70px;"></div>';
    try {
      const res = await api.get(`/me/redemptions?page=${page}&page_size=20`);
      if (!res.items.length) {
        list.innerHTML = `<div class="emp-empty"><div class="icon">📦</div><h3>هنوز درخواستی ثبت نکرده‌اید</h3></div>`;
        document.getElementById('ptRedemptionsPagination').innerHTML = '';
        return;
      }
      list.innerHTML = res.items.map(renderRedemption).join('');
      renderPagination('ptRedemptionsPagination', res.page, res.total_pages, loadRedemptions);
    } catch (e) {
      list.innerHTML = `<div class="emp-empty"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
    }
  }

  function renderRedemption(r) {
    const cancellable = ['draft', 'submitted', 'under_review'].includes(r.status);
    return `
      <div class="item-card" style="cursor:default;">
        <div class="item-card-icon">🎁</div>
        <div class="item-card-info">
          <div class="item-card-title">${esc(r.reward_title || '—')}</div>
          <div class="item-card-meta">${numFa(r.cost_points_snapshot)} امتیاز • ${fmtDate(r.created_at)}${r.admin_note ? ' • ' + esc(r.admin_note) : ''}</div>
        </div>
        <span class="redemption-status-pill redemption-status-${r.status}">${esc(r.status_label)}</span>
        ${cancellable ? `<button class="btn-action" style="background:#FEF2F2;color:#DC2626;margin-inline-start:8px;" data-role="cancel-redemption" data-id="${r.id}">لغو</button>` : ''}
      </div>`;
  }

  async function cancelRedemption(id) {
    if (!confirm('آیا مطمئن هستید که می‌خواهید این درخواست را لغو کنید؟')) return;
    try {
      await api.patch(`/me/redemptions/${id}/cancel`);
      toastSuccess('درخواست لغو شد');
      await Promise.all([loadWallet(), loadRedemptions(state.redemptionsPage)]);
    } catch (e) {
      toastError(e.message);
    }
  }

  document.getElementById('ptCatalogGrid')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="redeem"]');
    if (btn) requestRedeem(btn.dataset.id, btn.dataset.title, parseInt(btn.dataset.cost, 10));
  });

  document.getElementById('ptRedemptions')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="cancel-redemption"]');
    if (btn) cancelRedemption(btn.dataset.id);
  });

  return { load, switchTab, debouncedCatalogSearch };
})();
