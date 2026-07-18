// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی خانه‌ی کارمند (خوش‌آمدگویی + خلاصه‌ی پیشرفت)
// ════════════════════════════════════════════════════════════════════
// وابسته به content_shared.js (ثابت‌ها + renderContentCard + fmtDuration).

const HomePage = (() => {
  async function load() {
    const user = Auth.getUser();
    setText('homeGreeting', greetingByHour() + (user?.full_name ? '، ' + firstName(user.full_name) : ''));

    loadOrgWidget();

    const inProgressWrap = document.getElementById('homeInProgress');
    const notStartedWrap = document.getElementById('homeNotStarted');
    inProgressWrap.innerHTML = empSkeletonCards(3);
    notStartedWrap.innerHTML = empSkeletonCards(4);

    try {
      const res = await api.get('/me/contents?page=1&page_size=100');
      const items = res.items || [];
      const byRecency = (a, b) => new Date(b.my_last_viewed_at || 0) - new Date(a.my_last_viewed_at || 0);

      const inProgress = items.filter(c => c.my_status === 'in_progress').sort(byRecency);
      const completed = items.filter(c => c.my_status === 'completed').sort(byRecency);
      const notStarted = items.filter(c => c.my_status === 'not_started');

      setText('homeStatTotal', numFa(items.length));
      setText('homeStatInProgress', numFa(inProgress.length));
      setText('homeStatCompleted', numFa(completed.length));

      const pct = items.length ? Math.round((completed.length / items.length) * 100) : 0;
      const ring = document.getElementById('homeCompletionRing');
      if (ring) ring.style.setProperty('--pct', pct);
      setText('homeCompletionPct', numFa(pct) + '٪');

      if (!items.length) {
        toggle('homeSpotlightSection', false);
        toggle('homeInProgressSection', false);
        toggle('homeCompletedSection', false);
        toggle('homeNotStartedSection', true);
        renderCards(notStartedWrap, [], 'هنوز محتوایی برای شما ثبت نشده — با مدیر سازمان خود در تماس باشید');
        return;
      }

      // ادامه بده = آخرین محتوای «در حال یادگیری» که بازدید شده (یا اولین در نبود تاریخچه)
      const spotlight = inProgress[0];
      toggle('homeSpotlightSection', !!spotlight);
      if (spotlight) {
        document.getElementById('homeSpotlight').innerHTML = renderSpotlightCard(spotlight);
        const qaContinue = document.getElementById('qaContinue');
        if (qaContinue) qaContinue.href = `/content/detail.html?id=${spotlight.id}`;
      }

      const restInProgress = inProgress.filter(c => c.id !== spotlight?.id);
      toggle('homeInProgressSection', restInProgress.length > 0);
      renderCards(inProgressWrap, restInProgress, '');

      toggle('homeNotStartedSection', true);
      renderCards(notStartedWrap, notStarted, 'همه‌ی محتواهای خود را شروع کرده‌اید 🎉');

      toggle('homeCompletedSection', completed.length > 0);
      renderCards(document.getElementById('homeCompleted'), completed, '');
    } catch (e) {
      inProgressWrap.innerHTML = `<div class="emp-empty" style="grid-column:1/-1;"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
      notStartedWrap.innerHTML = '';
      toggle('homeSpotlightSection', false);
      toggle('homeInProgressSection', true);
      toggle('homeCompletedSection', false);
    }
  }

  async function loadOrgWidget() {
    try {
      const org = await api.get('/me/org');
      setText('homeOrgName', org.name || '—');
      if (!org.description && !org.logo_url) return;
      setText('homeOrgCardName', org.name || '—');
      setText('homeOrgCardDesc', org.description || '');
      const logoEl = document.getElementById('homeOrgLogo');
      if (org.logo_url && logoEl) logoEl.innerHTML = `<img src="${esc(org.logo_url)}" alt="">`;
      toggle('homeOrgCard', true);
    } catch { /* غیرحیاتی */ }
  }

  function renderSpotlightCard(c) {
    const pct = c.my_progress_pct || 0;
    const meta = [TYPE_LABEL_FA[c.type] || c.type, c.total_duration_min ? fmtDuration(c.total_duration_min) : null].filter(Boolean).join(' · ');
    return `
      <a class="home-spotlight" href="/content/detail.html?id=${c.id}">
        <div class="home-spotlight-thumb">
          ${c.thumbnail_url ? `<img src="${esc(c.thumbnail_url)}" alt="">` : (TYPE_ICON[c.type] || '📄')}
          <span class="home-spotlight-play">▶</span>
        </div>
        <div class="home-spotlight-body">
          <span class="home-spotlight-cat">${esc(meta)}</span>
          <h3>${esc(c.title)}</h3>
          <p>${numFa(pct)}٪ پیش رفته‌اید — ${numFa(c.total_items_count)} آیتم</p>
          <div class="progress-track"><div class="progress-fill" style="width:${pct}%;"></div></div>
        </div>
        <span class="home-spotlight-cta">ادامه یادگیری ‹</span>
      </a>`;
  }

  function renderCards(container, items, emptyMsg) {
    if (!items.length) {
      container.innerHTML = emptyMsg
        ? `<div class="emp-empty" style="grid-column:1/-1;padding:36px 20px;"><div class="icon">📭</div><h3>${esc(emptyMsg)}</h3></div>`
        : '';
      return;
    }
    container.innerHTML = items.map(renderContentCard).join('');
  }

  function toggle(id, show) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('hidden', !show);
  }

  function greetingByHour() {
    const h = new Date().getHours();
    if (h < 12) return 'صبح بخیر';
    if (h < 17) return 'ظهر بخیر';
    if (h < 20) return 'عصر بخیر';
    return 'شب بخیر';
  }
  function firstName(full) { return (full || '').split(' ')[0]; }
  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  return { load };
})();
