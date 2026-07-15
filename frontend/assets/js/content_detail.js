// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «جزئیات محتوا» (Content Detail + Item Viewer)
// ════════════════════════════════════════════════════════════════════
// آیتم‌ها بر اساس نوع نمایش داده می‌شوند؛ چون ردیابی دقیق «چقدر دیده شده»
// برای متن/PDF/تصویر در بک‌اند وجود ندارد (progress_pct کاملاً client-
// reported است)، برای این انواع دکمه‌ی صریح «علامت‌گذاری به‌عنوان
// مطالعه‌شده» استفاده می‌شود؛ ویدیو با رویداد ended خودکار تکمیل می‌شود؛
// لینک/فایل با کلیک روی «باز کردن» تکمیل می‌شوند (تنها تعامل قابل‌سنجش).

const ContentDetailPage = (() => {
  const state = { contentId: null, detail: null, openItemId: null };

  async function load() {
    const params = new URLSearchParams(location.search);
    state.contentId = params.get('id');
    if (!state.contentId) {
      showFatalError('شناسه محتوا مشخص نیست');
      return;
    }
    try {
      const detail = await api.get(`/me/contents/${state.contentId}`);
      state.detail = detail;
      if (detail.my_status === 'not_started') {
        try { await api.post(`/me/contents/${state.contentId}/start`); } catch { /* غیرحیاتی */ }
      }
      render();
    } catch (e) {
      showFatalError(e.message || 'محتوا یافت نشد یا دسترسی ندارید');
    }
  }

  function showFatalError(msg) {
    document.getElementById('cdRoot').innerHTML = `<div class="emp-empty"><div class="icon">⚠️</div><h3>${esc(msg)}</h3><a class="btn btn-secondary" href="/content/list.html" style="margin-top:14px;display:inline-flex;">بازگشت به محتوای من</a></div>`;
  }

  function render() {
    const d = state.detail;
    document.title = `${d.title} — Talentick`;

    document.getElementById('cdCover').innerHTML = d.thumbnail_url
      ? `<img src="${esc(d.thumbnail_url)}" alt="">`
      : (TYPE_ICON[d.type] || '📄');
    document.getElementById('cdTitle').textContent = d.title;
    document.getElementById('cdType').textContent = TYPE_LABEL_FA[d.type] || d.type;
    document.getElementById('cdMetaExtra').textContent = [
      d.instructor_name || d.author,
      d.total_duration_min ? `${numFa(d.total_duration_min)} دقیقه` : null,
      d.level ? LEVEL_FA[d.level] : null,
    ].filter(Boolean).join(' • ');
    document.getElementById('cdDesc').textContent = d.description || '';
    document.getElementById('cdDesc').classList.toggle('hidden', !d.description);

    const pct = d.my_progress_pct || 0;
    document.getElementById('cdProgressFill').style.width = pct + '%';
    document.getElementById('cdProgressFill').classList.toggle('done', pct >= 100);
    document.getElementById('cdProgressLabel').textContent = `${numFa(pct)}٪ تکمیل‌شده — ${numFa(d.items.filter(i => i.my_status === 'completed').length)} از ${numFa(d.items.length)} آیتم`;

    renderItems();
  }

  function renderItems() {
    const wrap = document.getElementById('cdItems');
    const items = state.detail.items || [];
    if (!items.length) {
      wrap.innerHTML = `<div class="emp-empty"><div class="icon">📭</div><h3>این محتوا هنوز آیتمی ندارد</h3></div>`;
      return;
    }
    wrap.innerHTML = items.map((it, idx) => {
      const checkCls = it.is_locked ? 'locked' : (it.my_status === 'completed' ? 'done' : (it.my_status === 'in_progress' ? 'progress' : ''));
      const checkContent = it.is_locked ? '🔒' : (it.my_status === 'completed' ? '✓' : numFa(idx + 1));
      const actionLabel = it.is_locked ? 'قفل' : (it.my_status === 'completed' ? 'مرور' : (it.my_status === 'in_progress' ? 'ادامه' : 'شروع'));
      return `
        <div class="item-card ${it.is_locked ? 'locked' : ''}" onclick="ContentDetailPage.openItem('${it.id}')">
          <div class="item-card-check ${checkCls}">${checkContent}</div>
          <div class="item-card-icon">${ITEM_TYPE_ICON_FA[it.type] || '📄'}</div>
          <div class="item-card-info">
            <div class="item-card-title">${esc(it.title)}</div>
            <div class="item-card-meta">${ITEM_TYPE_LABEL_FA[it.type] || it.type}${it.duration_min ? ' • ' + numFa(it.duration_min) + ' دقیقه' : ''}${it.is_locked ? ' • ابتدا آیتم‌های قبلی را تکمیل کنید' : ''}</div>
          </div>
          <div class="item-card-action">
            <button class="btn btn-outline btn-sm" style="padding:7px 14px;font-size:12px;" onclick="event.stopPropagation();ContentDetailPage.openItem('${it.id}')">${actionLabel}</button>
          </div>
        </div>`;
    }).join('');
  }

  // ─── Item Viewer ────────────────────────────────────────────────
  function openItem(itemId) {
    const it = state.detail.items.find(x => x.id === itemId);
    if (!it) return;

    if (it.is_locked) {
      toastError('این آیتم قفل است — ابتدا آیتم‌های قبلی را به‌ترتیب تکمیل کنید');
      return;
    }

    // آیتم آزمون: مستقیم به صفحه‌ی آزمون هدایت می‌شویم (خارج از این ویوئر)
    if (it.type === 'quiz_ref') {
      if (!it.quiz_id) { toastError('این آیتم به هیچ آزمونی متصل نیست'); return; }
      window.location.href = `/quiz/index.html?id=${it.quiz_id}&content_id=${state.contentId}&item_id=${it.id}`;
      return;
    }

    state.openItemId = itemId;
    document.getElementById('viewerTitle').textContent = it.title;
    const body = document.getElementById('viewerBody');
    const footer = document.getElementById('viewerFooter');
    body.innerHTML = '';
    footer.innerHTML = '';

    if (it.type === 'text') {
      body.innerHTML = `<div class="viewer-text-body">${esc(it.body || '')}</div>`;
      footer.innerHTML = markCompleteBtnHtml(it);
    } else if (it.type === 'video') {
      body.innerHTML = `<video controls id="viewerVideo" src="${esc(it.media_url || '')}"></video>`;
      document.getElementById('viewerVideo').addEventListener('ended', () => markComplete(it.id, true));
      footer.innerHTML = markCompleteBtnHtml(it);
    } else if (it.type === 'image') {
      body.innerHTML = `<img src="${esc(it.media_url || '')}" alt="${esc(it.title)}">`;
      footer.innerHTML = markCompleteBtnHtml(it);
    } else if (it.type === 'pdf') {
      body.innerHTML = `<iframe src="${esc(it.media_url || '')}"></iframe>`;
      footer.innerHTML = markCompleteBtnHtml(it);
    } else if (it.type === 'link') {
      body.innerHTML = `<div style="text-align:center;padding:30px 10px;"><div style="font-size:40px;margin-bottom:14px;">🔗</div><p style="color:var(--gray-500);font-size:13.5px;margin-bottom:18px;">این آیتم یک لینک خارجی است — با کلیک روی دکمه‌ی زیر در تب جدید باز می‌شود.</p></div>`;
      footer.innerHTML = `
        <a class="btn btn-primary" href="${esc(it.media_url || '#')}" target="_blank" rel="noopener" onclick="ContentDetailPage.markComplete('${it.id}', true)">باز کردن لینک ↗</a>
        <button class="btn btn-secondary" onclick="ContentDetailPage.closeViewer()">بستن</button>`;
    } else if (it.type === 'file') {
      body.innerHTML = `<div style="text-align:center;padding:30px 10px;"><div style="font-size:40px;margin-bottom:14px;">📎</div><p style="color:var(--gray-500);font-size:13.5px;">فایل ضمیمه‌ی این آیتم را دانلود کنید.</p></div>`;
      footer.innerHTML = `
        <a class="btn btn-primary" href="${esc(it.media_url || '#')}" target="_blank" rel="noopener" onclick="ContentDetailPage.markComplete('${it.id}', true)">دانلود فایل ↓</a>
        <button class="btn btn-secondary" onclick="ContentDetailPage.closeViewer()">بستن</button>`;
    }

    document.getElementById('itemViewer').classList.remove('hidden');
  }

  function markCompleteBtnHtml(it) {
    if (it.my_status === 'completed') {
      return `<span style="color:var(--success);font-weight:700;font-size:13px;">✓ تکمیل‌شده</span><button class="btn btn-secondary" onclick="ContentDetailPage.closeViewer()">بستن</button>`;
    }
    return `
      <button class="btn btn-primary" onclick="ContentDetailPage.markComplete('${it.id}')">علامت‌گذاری به‌عنوان تکمیل‌شده</button>
      <button class="btn btn-secondary" onclick="ContentDetailPage.closeViewer()">بستن</button>`;
  }

  async function markComplete(itemId, silent = false) {
    try {
      const res = await api.post(`/me/contents/${state.contentId}/items/${itemId}/progress`, { progress_pct: 100 });
      // به‌روزرسانی state محلی بدون رفرش کامل صفحه
      const it = state.detail.items.find(x => x.id === itemId);
      if (it) { it.my_status = res.item.status; it.my_progress_pct = res.item.progress_pct; }
      state.detail.my_progress_pct = res.content.progress_pct;
      state.detail.my_status = res.content.status;
      render();
      if (!silent) toastSuccess('این آیتم به‌عنوان تکمیل‌شده ثبت شد');
      if (state.openItemId === itemId) closeViewer();
    } catch (e) {
      toastError(e.message || 'خطا در ثبت پیشرفت');
    }
  }

  function closeViewer() {
    document.getElementById('itemViewer').classList.add('hidden');
    const video = document.getElementById('viewerVideo');
    if (video) video.pause();
    state.openItemId = null;
  }

  const LEVEL_FA = { beginner: 'مقدماتی', intermediate: 'متوسط', advanced: 'پیشرفته' };

  return { load, openItem, markComplete, closeViewer };
})();
