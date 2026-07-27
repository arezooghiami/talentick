// ════════════════════════════════════════════════════════════════════
// Talentick — Welcome / Onboarding Slider (۳ اسلاید، Swipe + دکمه)
// ════════════════════════════════════════════════════════════════════

(function () {
  // Welcome حالا مرحله‌ی اجباری بعد از لاگین است (نه یک intro قبل از لاگین) —
  // کاربر باید لاگین کرده باشد تا این صفحه را ببیند.
  if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) {
    window.location.href = '/login.html';
    return;
  }
  const currentUser = Auth.getUser();
  if (currentUser?.must_change_password) {
    window.location.href = '/change-password.html';
    return;
  }
  if (currentUser && currentUser.role !== 'employee') {
    // نقش‌های ادمین از فلوی Welcome کارمندان عبور نمی‌کنند.
    Auth.redirectByRole();
    return;
  }

  function goToDashboard(e) {
    if (e) e.preventDefault();
    Auth.markWelcomeSeenThisSession();
    window.location.href = '/dashboard.html';
  }
  document.getElementById('wlSkip')?.addEventListener('click', goToDashboard);

  const SLIDES = 3;
  const track = document.getElementById('wlTrack');
  let index = 0;
  let startX = 0;
  let deltaX = 0;
  let dragging = false;

  // ─── رندر دات‌های هر اسلاید ──────────────────────────────────────────
  for (let i = 0; i < SLIDES; i++) {
    document.getElementById(`wlDots${i}`).innerHTML = renderDots(i);
  }

  function renderDots(active) {
    return Array.from({ length: SLIDES }, (_, i) =>
      `<span class="ds-dot${i === active ? ' active' : ''}"></span>`
    ).join('');
  }

  function goTo(i) {
    index = Math.max(0, Math.min(SLIDES - 1, i));
    track.style.transform = `translate3d(${-index * (100 / SLIDES)}%, 0, 0)`;
  }

  document.querySelectorAll('[data-next]').forEach(btn => {
    btn.addEventListener('click', () => goTo(index + 1));
  });
  document.querySelectorAll('[data-start]').forEach(btn => {
    btn.addEventListener('click', goToDashboard);
  });

  // ─── Swipe (Touch + Mouse) ──────────────────────────────────────────
  const viewport = document.getElementById('wlViewport');

  function dragStart(x) { dragging = true; startX = x; deltaX = 0; track.classList.add('dragging'); }
  function dragMove(x) {
    if (!dragging) return;
    deltaX = x - startX;
    const base = -index * (100 / SLIDES);
    const pct = (deltaX / viewport.clientWidth) * (100 / SLIDES);
    track.style.transform = `translate3d(${base + pct}%, 0, 0)`;
  }
  function dragEnd() {
    if (!dragging) return;
    dragging = false;
    track.classList.remove('dragging');
    const threshold = viewport.clientWidth * 0.18;
    // کشیدن به چپ → اسلاید بعدی، کشیدن به راست → اسلاید قبلی (چیدمان فیزیکی LTR)
    if (deltaX < -threshold) goTo(index + 1);
    else if (deltaX > threshold) goTo(index - 1);
    else goTo(index);
  }

  viewport.addEventListener('touchstart', (e) => dragStart(e.touches[0].clientX), { passive: true });
  viewport.addEventListener('touchmove', (e) => dragMove(e.touches[0].clientX), { passive: true });
  viewport.addEventListener('touchend', dragEnd);

  viewport.addEventListener('mousedown', (e) => { e.preventDefault(); dragStart(e.clientX); });
  window.addEventListener('mousemove', (e) => dragMove(e.clientX));
  window.addEventListener('mouseup', dragEnd);

  window.addEventListener('resize', () => goTo(index));
  goTo(0);
})();
