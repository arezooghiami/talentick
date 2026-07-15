// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی خانه‌ی کارمند (خوش‌آمدگویی + خلاصه‌ی پیشرفت)
// ════════════════════════════════════════════════════════════════════
// وابسته به content_shared.js (ثابت‌ها + renderContentCard).

const HomePage = (() => {
  async function load() {
    const user = Auth.getUser();
    setText('homeGreeting', greetingByHour() + (user?.full_name ? '، ' + firstName(user.full_name) : ''));

    try {
      const me = await api.get('/auth/me');
      setText('homeOrgName', me.org_name || '—');
    } catch { /* غیرحیاتی */ }

    const wrap = document.getElementById('homeInProgress');
    const allWrap = document.getElementById('homeRecent');
    wrap.innerHTML = empSkeletonCards(3);
    allWrap.innerHTML = empSkeletonCards(4);

    try {
      const res = await api.get('/me/contents?page=1&page_size=100');
      const items = res.items || [];
      const inProgress = items.filter(c => c.my_status === 'in_progress');
      const completed = items.filter(c => c.my_status === 'completed');
      const notStarted = items.filter(c => c.my_status === 'not_started');

      setText('homeStatTotal', numFa(items.length));
      setText('homeStatInProgress', numFa(inProgress.length));
      setText('homeStatCompleted', numFa(completed.length));

      renderCards(wrap, inProgress.slice(0, 3), 'هنوز چیزی را شروع نکرده‌اید — از «محتوای من» شروع کنید');
      const recent = [...inProgress, ...notStarted, ...completed].slice(0, 4);
      renderCards(allWrap, recent, 'هنوز محتوایی برای شما ثبت نشده');

      document.getElementById('homeInProgressSection').classList.toggle('hidden', inProgress.length === 0);
    } catch (e) {
      wrap.innerHTML = `<div class="emp-empty" style="grid-column:1/-1;"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
      allWrap.innerHTML = '';
    }
  }

  function renderCards(container, items, emptyMsg) {
    if (!items.length) {
      container.innerHTML = `<div class="emp-empty" style="grid-column:1/-1;padding:36px 20px;"><div class="icon">📭</div><h3>${esc(emptyMsg)}</h3></div>`;
      return;
    }
    container.innerHTML = items.map(renderContentCard).join('');
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
