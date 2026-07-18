// ════════════════════════════════════════════════════════════════════
// Talentick — Command Palette (Ctrl/Cmd+K) برای پرتال کارمند
// ════════════════════════════════════════════════════════════════════
// ناوبری سریع بین صفحات واقعی پرتال. هیچ مقصدی که هنوز پیاده نشده
// (مثل «دستیار هوشمند» یا «رویدادها») در این لیست نیست.

const CommandPalette = (() => {
  const items = [
    { label: 'خانه', icon: '🏠', href: '/onboarding/index.html', group: 'اصلی' },
    { label: 'محتوای من', icon: '📚', href: '/content/list.html', group: 'اصلی' },
    { label: 'سازمان من', icon: '🏢', href: '/organization/index.html', group: 'اصلی' },
    { label: 'چارت سازمانی', icon: '🌳', href: '/organization/index.html?tab=chart', group: 'سازمان' },
    { label: 'کتابخانه اسناد', icon: '📁', href: '/organization/index.html?tab=docs', group: 'سازمان' },
    { label: 'تغییر رمز عبور', icon: '🔒', href: '/change-password.html', group: 'حساب کاربری' },
    { label: 'خروج از حساب', icon: '🚪', action: () => Auth.logout(), group: 'حساب کاربری' },
  ];

  let els = null;
  let active = 0;
  let filtered = items;

  function ensureDom() {
    if (els) return els;
    const overlay = document.createElement('div');
    overlay.className = 'cmdk-overlay hidden';
    overlay.innerHTML = `
      <div class="cmdk-box">
        <div class="cmdk-input-row">
          <span class="ic">🔍</span>
          <input type="text" id="cmdkInput" placeholder="جست‌وجو یا رفتن به هر صفحه..." autocomplete="off" />
          <kbd>ESC</kbd>
        </div>
        <div class="cmdk-list" id="cmdkList"></div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

    const input = overlay.querySelector('#cmdkInput');
    input.addEventListener('input', () => { filter(input.value); });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
      else if (e.key === 'Enter') { e.preventDefault(); go(filtered[active]); }
      else if (e.key === 'Escape') { close(); }
    });

    els = { overlay, input, list: overlay.querySelector('#cmdkList') };
    return els;
  }

  function filter(query) {
    const q = (query || '').trim();
    filtered = q ? items.filter(i => i.label.includes(q)) : items;
    active = 0;
    render();
  }

  function render() {
    const { list } = ensureDom();
    if (!filtered.length) {
      list.innerHTML = `<div class="cmdk-empty">نتیجه‌ای یافت نشد</div>`;
      return;
    }
    list.innerHTML = filtered.map((item, i) => `
      <button type="button" class="cmdk-item${i === active ? ' active' : ''}" data-idx="${i}">
        <span class="ic">${item.icon}</span>
        <span>${item.label}</span>
        <span class="grp">${item.group}</span>
      </button>`).join('');
    list.querySelectorAll('.cmdk-item').forEach(btn => {
      btn.addEventListener('mouseenter', () => setActive(parseInt(btn.dataset.idx, 10)));
      btn.addEventListener('click', () => go(filtered[parseInt(btn.dataset.idx, 10)]));
    });
  }

  function setActive(i) {
    if (!filtered.length) return;
    active = Math.max(0, Math.min(filtered.length - 1, i));
    render();
  }

  function go(item) {
    if (!item) return;
    close();
    if (item.action) item.action();
    else window.location.href = item.href;
  }

  function open() {
    const { overlay, input } = ensureDom();
    overlay.classList.remove('hidden');
    input.value = '';
    filter('');
    setTimeout(() => input.focus(), 10);
  }

  function close() {
    if (!els) return;
    els.overlay.classList.add('hidden');
  }

  function toggle() {
    const { overlay } = ensureDom();
    if (overlay.classList.contains('hidden')) open();
    else close();
  }

  function init() {
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        toggle();
      }
    });
    const trigger = document.getElementById('cmdkTrigger');
    if (trigger) trigger.addEventListener('click', open);
  }

  return { init, open, close };
})();

document.addEventListener('DOMContentLoaded', () => CommandPalette.init());
