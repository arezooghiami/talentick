// ════════════════════════════════════════════════════════════════════
// Talentick — داشبورد کارمند (خانه)
// ════════════════════════════════════════════════════════════════════
// وابسته به config.js/auth.js/api.js/utils.js/content_shared.js/illustrations.js.

const DashboardHome = (() => {
  const CATEGORY_META = {
    course:  { label: 'دوره‌ها',   color: 'linear-gradient(135deg,#334155,#0F172A)', icon: iconMonitor() },
    article: { label: 'مقاله‌ها',  color: 'linear-gradient(135deg,#FFD666,#F5B400)', icon: iconArticle() },
    podcast: { label: 'پادکست‌ها', color: 'linear-gradient(135deg,#5EEAD4,#0D9488)', icon: iconMic() },
    book:    { label: 'کتاب‌ها',   color: 'linear-gradient(135deg,#A855F7,#6C4CF1)', icon: iconBook() },
  };

  async function load() {
    document.getElementById('dashLogo').innerHTML = TalentickArt.logo('dark');
    wireChrome();
    renderBanner([]);

    const user = Auth.getUser();
    setText('empUserName', user?.full_name || '');
    const avatarEl = document.getElementById('empUserAvatar');
    if (avatarEl) avatarEl.textContent = initials(user?.full_name || '');

    loadPointsAndLevel();
    loadOrg();
    loadLeaderboard();

    const inProgressWrap = document.getElementById('inProgressList');
    const notStartedWrap = document.getElementById('notStartedList');
    inProgressWrap.innerHTML = skeletons(3);
    notStartedWrap.innerHTML = skeletons(4);

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
      loadPointsOnly();

      renderCategories(items);
      renderBanner(items, inProgress[0]);

      if (!items.length) {
        toggle('spotlightSection', false);
        toggle('inProgressSection', false);
        toggle('completedSection', false);
        notStartedWrap.innerHTML = emptyState('document', 'هنوز محتوایی برای شما ثبت نشده — با مدیر سازمان خود در تماس باشید');
        return;
      }

      const spotlight = inProgress[0];
      toggle('spotlightSection', !!spotlight);
      if (spotlight) document.getElementById('spotlightCard').innerHTML = renderCourseCard(spotlight, { wide: true });

      const restInProgress = inProgress.filter(c => c.id !== spotlight?.id);
      toggle('inProgressSection', restInProgress.length > 0);
      renderGrid(inProgressWrap, restInProgress);

      const popular = notStarted.length ? notStarted : items;
      renderGrid(notStartedWrap, popular, 'به‌زودی دوره‌های تازه برای شما اضافه می‌شود');

      toggle('completedSection', completed.length > 0);
      renderGrid(document.getElementById('completedList'), completed);
    } catch (e) {
      toggle('spotlightSection', false);
      toggle('inProgressSection', false);
      toggle('completedSection', false);
      inProgressWrap.innerHTML = '';
      notStartedWrap.innerHTML = emptyState('chart-panel', 'در حال حاضر امکان بارگذاری محتوا نیست — کمی بعد دوباره امتحان کنید');
      renderCategories([]);
    }

    loadOnboardingPrograms();
  }

  // ─── Chrome: hamburger / overlay / dropdown / soon-links ───────────
  function wireChrome() {
    const sidebar = document.getElementById('dashSidebar');
    const overlay = document.getElementById('dashOverlay');
    const hamburger = document.getElementById('dashHamburger');
    const openSidebar = () => { sidebar.classList.add('open'); overlay.classList.add('show'); };
    const closeSidebar = () => { sidebar.classList.remove('open'); overlay.classList.remove('show'); };
    hamburger?.addEventListener('click', openSidebar);
    overlay?.addEventListener('click', closeSidebar);
    sidebar?.querySelectorAll('a[href]:not([data-soon])').forEach(a => a.addEventListener('click', closeSidebar));

    document.querySelectorAll('[data-soon]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        toastInfo('این بخش به‌زودی فعال می‌شود');
      });
    });

    const searchInput = document.getElementById('dashSearchInput');
    searchInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && searchInput.value.trim()) {
        window.location.href = '/content/list.html?q=' + encodeURIComponent(searchInput.value.trim());
      }
    });
  }

  // ─── Points / Level (sidebar widget) ────────────────────────────────
  async function loadPointsAndLevel() {
    try {
      const res = await api.get('/me/points/summary');
      applyPoints(res);
    } catch {
      setText('sideLevelNext', 'در دسترس نیست');
    }
  }
  async function loadPointsOnly() {
    try { applyPoints(await api.get('/me/points/summary')); } catch { /* غیرحیاتی */ }
  }
  function applyPoints(res) {
    const total = res.total_points || 0;
    setText('homeStatPoints', numFa(total));
    // سطح ساده بر مبنای هر ۱۰۰۰ امتیاز یک سطح — تا زمانی که فیلد level رسمی از بک‌اند اضافه شود.
    const level = Math.max(1, Math.floor(total / 1000) + 1);
    const inLevel = total % 1000;
    const toNext = 1000 - inLevel;
    setText('sideLevelNum', numFa(level));
    setText('sidePointsNum', numFa(total));
    setText('dashUserLevel', `سطح ${numFa(level)}`);
    setText('sideLevelNext', `تا سطح بعدی ${numFa(toNext)} امتیاز دیگر`);
    const fill = document.getElementById('sideLevelFill');
    if (fill) fill.style.width = Math.round((inLevel / 1000) * 100) + '%';
  }

  async function loadOrg() {
    try {
      const org = await api.get('/me/org');
      window.__dashOrgName = org.name || 'سازمان شما';
    } catch { window.__dashOrgName = 'سازمان شما'; }
  }

  async function loadOnboardingPrograms() {
    try {
      const items = await api.get('/me/onboarding');
      const active = (items || []).filter(e => !e.completed_at);
      toggle('onboardingSection', active.length > 0);
      if (!active.length) return;
      document.getElementById('onboardingList').innerHTML = active.map(renderOnboardingCard).join('');
    } catch { toggle('onboardingSection', false); }
  }

  function renderOnboardingCard(e) {
    const pct = e.progress_pct || 0;
    return `
      <a class="dash-course-card" href="/onboarding/detail.html?id=${e.enrollment_id}">
        <div class="dash-course-thumb" style="background:var(--gradient-brand);">🚀
          <div class="dash-course-progress-bar"><div class="dash-course-progress-fill" style="width:${pct}%"></div></div>
        </div>
        <div class="dash-course-body">
          <div class="dash-course-title">${esc(e.program_name)}</div>
          <div class="dash-course-meta">
            <span class="dash-course-rating">${numFa(pct)}٪ پیش رفته</span>
            <span class="dash-course-students">${numFa(e.steps_completed)}/${numFa(e.steps_total)} مرحله</span>
          </div>
        </div>
      </a>`;
  }

  // ─── Leaderboard ─────────────────────────────────────────────────
  // بک‌اند فعلی endpoint عمومی رتبه‌بندی همکاران برای نقش کارمند ندارد (این
  // مرحله فقط Frontend است). به‌جای داده‌ی جعلی برای همکاران واقعی، حالت
  // «به‌زودی» با همان زبان طراحی نمایش داده می‌شود تا وقتی API متصل شود.
  async function loadLeaderboard() {
    const wrap = document.getElementById('dashLeaderboard');
    wrap.innerHTML = skeletons(5, 108);
    try {
      const items = await api.get('/me/org/leaderboard');
      if (!items || !items.length) throw new Error('empty');
      wrap.innerHTML = items.slice(0, 10).map(renderLeaderboardItem).join('');
    } catch {
      wrap.innerHTML = `<div style="width:100%;">${emptyState('trophy', 'رتبه‌بندی همکاران به‌زودی فعال می‌شود')}</div>`;
    }
  }

  function renderLeaderboardItem(u, i) {
    const rankCls = i === 0 ? 'r1' : i === 1 ? 'r2' : i === 2 ? 'r3' : 'rn';
    return `
      <div class="dash-lb-item">
        <div class="dash-lb-avatar-wrap">
          <span class="ds-avatar dash-lb-avatar">${esc(initials(u.full_name))}</span>
          <span class="dash-lb-rank ${rankCls}">${numFa(i + 1)}</span>
        </div>
        <div class="dash-lb-name">${esc(u.full_name)}</div>
        <div class="dash-lb-points">${numFa(u.total_points)} امتیاز</div>
      </div>`;
  }

  // ─── Categories (فضاهای آموزشی) — واقعی، از نوع محتوای کاربر ────────
  function renderCategories(items) {
    const wrap = document.getElementById('dashCategories');
    const counts = {};
    items.forEach(c => { counts[c.type] = (counts[c.type] || 0) + 1; });
    const types = Object.keys(CATEGORY_META).filter(t => counts[t]);
    if (!types.length) {
      wrap.innerHTML = emptyState('folder', 'به محض تخصیص محتوا، فضاهای آموزشی شما اینجا نمایش داده می‌شود');
      return;
    }
    wrap.innerHTML = types.map(t => {
      const meta = CATEGORY_META[t];
      return `
        <a class="dash-cat-card" href="/content/list.html">
          <span class="dash-cat-icon" style="background:${meta.color}">${meta.icon}</span>
          <span class="dash-cat-title">${meta.label}</span>
          <span class="dash-cat-count">${numFa(counts[t])} مورد</span>
        </a>`;
    }).join('');
  }

  // ─── Course cards (دوره‌های محبوب / ادامه بده) ──────────────────────
  function renderGrid(container, items, emptyMsg) {
    if (!items.length) {
      container.innerHTML = emptyMsg ? emptyState('rocket', emptyMsg) : '';
      return;
    }
    container.innerHTML = items.map(c => renderCourseCard(c)).join('');
  }

  function renderCourseCard(c, opts = {}) {
    const pct = c.my_progress_pct || 0;
    const meta = CATEGORY_META[c.type] || CATEGORY_META.course;
    const durationLabel = c.total_duration_min ? fmtDuration(c.total_duration_min) : (TYPE_LABEL_FA[c.type] || c.type);
    return `
      <a class="dash-course-card" href="/content/detail.html?id=${c.id}" style="${opts.wide ? 'flex-direction:row;' : ''}">
        <div class="dash-course-thumb" style="background:${meta.color};${opts.wide ? 'width:150px;flex-shrink:0;height:auto;' : ''}">
          ${c.thumbnail_url ? `<img src="${esc(c.thumbnail_url)}" alt="">` : meta.icon}
          ${pct > 0 ? `<div class="dash-course-progress-bar"><div class="dash-course-progress-fill" style="width:${pct}%"></div></div>` : ''}
        </div>
        <div class="dash-course-body">
          <div class="dash-course-title">${esc(c.title)}</div>
          <div class="dash-course-meta">
            <span class="dash-course-rating">${pct > 0 ? numFa(pct) + '٪ پیش رفته' : (TYPE_LABEL_FA[c.type] || c.type)}</span>
            <span class="dash-course-students">${durationLabel}</span>
          </div>
        </div>
      </a>`;
  }

  // ─── Banner carousel ─────────────────────────────────────────────
  let bannerIndex = 0;
  let bannerTimer = null;
  function renderBanner(items, spotlight) {
    const track = document.getElementById('dashBannerTrack');
    const dots = document.getElementById('bannerDots');
    const user = Auth.getUser();
    const org = window.__dashOrgName || 'سازمان شما';
    const first = firstName(user?.full_name);

    const slides = [
      {
        eyebrow: spotlight ? 'ادامه‌ی مسیر یادگیری' : 'خوش آمدید',
        title: spotlight ? `ادامه بده، ${esc(first)}!` : `${greetingByHour()}${first ? '، ' + esc(first) : ''} 👋`,
        desc: spotlight ? `«${esc(spotlight.title)}» را ${numFa(spotlight.my_progress_pct || 0)}٪ پیش رفته‌اید — همین حالا ادامه دهید.` : `مسیر یادگیری و آشنایی با ${esc(org)} از همین‌جا شروع می‌شود.`,
        cta: spotlight ? 'ادامه یادگیری' : 'مشاهده دوره‌ها',
        href: spotlight ? `/content/detail.html?id=${spotlight.id}` : '/content/list.html',
        art: '<img src="/assets/img/characters/woman-waving.png" alt="" />',
      },
      {
        eyebrow: 'به‌زودی',
        title: 'چالش‌های تلنتیک می‌آید!',
        desc: 'در چالش‌های آموزشی شرکت کنید، امتیاز کسب کنید و در جدول برترین‌ها بدرخشید.',
        cta: 'اطلاعات بیشتر',
        href: '/points/index.html',
        art: '<img src="/assets/img/characters/woman-holding-certificate.png" alt="" />',
      },
    ];

    track.innerHTML = slides.map(s => `
      <div class="dash-banner-slide">
        <div class="dash-banner-copy">
          <span class="dash-banner-eyebrow">${s.eyebrow}</span>
          <h3>${s.title}</h3>
          <p>${s.desc}</p>
          <a href="${s.href}" class="ds-btn ds-btn-gold ds-btn-sm">${s.cta}</a>
        </div>
        <div class="dash-banner-art">${s.art}</div>
      </div>`).join('');

    dots.innerHTML = slides.map((_, i) => `<span class="ds-dot${i === 0 ? ' active' : ''}"></span>`).join('');

    const goTo = (i) => {
      bannerIndex = (i + slides.length) % slides.length;
      track.style.transform = `translateX(${-bannerIndex * 100}%)`;
      dots.querySelectorAll('.ds-dot').forEach((d, idx) => d.classList.toggle('active', idx === bannerIndex));
    };
    document.getElementById('bannerPrev').onclick = () => goTo(bannerIndex - 1);
    document.getElementById('bannerNext').onclick = () => goTo(bannerIndex + 1);
    goTo(0);

    clearInterval(bannerTimer);
    bannerTimer = setInterval(() => goTo(bannerIndex + 1), 6000);
  }

  // ─── Helpers ─────────────────────────────────────────────────────
  function toggle(id, show) { const el = document.getElementById(id); if (el) el.hidden = !show; }
  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
  function skeletons(n, h = 200) { return Array.from({ length: n }).map(() => `<div class="dash-skeleton" style="height:${h}px;"></div>`).join(''); }
  function emptyState(icon, text) { return `<div class="dash-empty"><img src="/assets/img/icons/${icon}.png" alt="" /><span>${esc(text)}</span></div>`; }
  function greetingByHour() {
    const h = new Date().getHours();
    if (h < 12) return 'صبح بخیر';
    if (h < 17) return 'ظهر بخیر';
    if (h < 20) return 'عصر بخیر';
    return 'شب بخیر';
  }
  function firstName(full) { return (full || '').split(' ')[0]; }

  function iconMonitor() { return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="13" rx="2"/><path stroke-linecap="round" d="M8 21h8M12 17v4"/></svg>`; }
  function iconArticle() { return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M6 2h9l3 3v17H6z"/><path stroke-linecap="round" d="M9 12h6M9 16h6M9 8h3"/></svg>`; }
  function iconMic() { return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="2" width="6" height="12" rx="3"/><path stroke-linecap="round" d="M5 10a7 7 0 0014 0M12 19v3"/></svg>`; }
  function iconBook() { return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 006.5 22H20V4a2 2 0 00-2-2H6.5A2.5 2.5 0 004 4.5v15z"/></svg>`; }

  return { load };
})();
