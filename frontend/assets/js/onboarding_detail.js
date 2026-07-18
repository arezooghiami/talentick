// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «جزئیات برنامه‌ی آشنایی من» (Onboarding Journey Detail)
// ════════════════════════════════════════════════════════════════════
// تکمیل هر مرحله همیشه یک اقدام صریح کارمند است (حتی برای مرحله‌ی نوع
// content/quiz) چون سیستم آنبوردینگ مستقل از ردیابی پیشرفت محتوا/آزمون است.

const OnboardingDetailPage = (() => {
  const state = { enrollmentId: null, detail: null, openStepId: null };

  const STEP_TYPE_ICON = { content: '📚', quiz: '📝', document_upload: '📎', custom: '✅' };
  const STEP_TYPE_LABEL = { content: 'محتوای آموزشی', quiz: 'آزمون', document_upload: 'بارگذاری مدرک', custom: 'وظیفه' };

  async function load() {
    const params = new URLSearchParams(location.search);
    state.enrollmentId = params.get('id');
    if (!state.enrollmentId) {
      showFatalError('شناسه‌ی ثبت‌نام مشخص نیست');
      return;
    }
    try {
      const detail = await api.get(`/me/onboarding/${state.enrollmentId}`);
      state.detail = detail;
      render();
    } catch (e) {
      showFatalError(e.message || 'این برنامه یافت نشد یا دسترسی ندارید');
    }
    wireDelegatedEvents();
  }

  function showFatalError(msg) {
    document.getElementById('obRoot').innerHTML = `<div class="emp-empty"><div class="icon">⚠️</div><h3>${esc(msg)}</h3><a class="btn btn-secondary" href="/onboarding/index.html" style="margin-top:14px;display:inline-flex;">بازگشت به خانه</a></div>`;
  }

  function render() {
    const d = state.detail;
    document.title = `${d.program_name} — Talentick`;

    document.getElementById('obTitle').textContent = d.program_name;
    const metaParts = [];
    if (d.deadline_at) metaParts.push('مهلت تکمیل: ' + fmtDate(d.deadline_at));
    if (d.completed_at) metaParts.push('✓ تکمیل‌شده در ' + fmtDate(d.completed_at));
    document.getElementById('obMetaExtra').textContent = metaParts.join(' • ');
    document.getElementById('obDesc').textContent = d.program_description || '';
    document.getElementById('obDesc').classList.toggle('hidden', !d.program_description);

    const pct = d.progress_pct || 0;
    document.getElementById('obProgressFill').style.width = pct + '%';
    document.getElementById('obProgressFill').classList.toggle('done', pct >= 100);
    document.getElementById('obProgressLabel').textContent =
      `${numFa(pct)}٪ تکمیل‌شده — ${numFa(d.steps_completed)} از ${numFa(d.steps_total)} مرحله`;

    renderSteps();
  }

  function renderSteps() {
    const wrap = document.getElementById('obItems');
    const steps = (state.detail.steps || []).slice().sort((a, b) => a.order_index - b.order_index);
    if (!steps.length) {
      wrap.innerHTML = `<div class="emp-empty"><div class="icon">📭</div><h3>این برنامه هنوز مرحله‌ای ندارد</h3></div>`;
      return;
    }
    wrap.innerHTML = steps.map((s, idx) => {
      const checkCls = s.status === 'completed' ? 'done' : (s.status === 'in_progress' || s.status === 'skipped' ? 'progress' : '');
      const checkContent = s.status === 'completed' ? '✓' : (s.status === 'skipped' ? '–' : numFa(idx + 1));
      const actionLabel = s.status === 'completed' ? 'مشاهده' : 'باز کردن';
      return `
        <div class="item-card" data-role="open-step" data-id="${esc(s.step_id)}">
          <div class="item-card-check ${checkCls}">${checkContent}</div>
          <div class="item-card-icon">${STEP_TYPE_ICON[s.type] || '📄'}</div>
          <div class="item-card-info">
            <div class="item-card-title">${esc(s.title)}${s.is_required ? '' : ' <span style="color:var(--gray-400);font-weight:500;">(اختیاری)</span>'}</div>
            <div class="item-card-meta">${esc(STEP_TYPE_LABEL[s.type] || s.type)}${statusSuffix(s.status)}</div>
          </div>
          <div class="item-card-action">
            <button class="btn btn-outline btn-sm" style="padding:7px 14px;font-size:12px;" data-role="open-step-btn" data-id="${esc(s.step_id)}">${actionLabel}</button>
          </div>
        </div>`;
    }).join('');
  }

  function statusSuffix(status) {
    if (status === 'completed') return ' • ✓ تکمیل‌شده';
    if (status === 'skipped') return ' • رد شده';
    if (status === 'in_progress') return ' • در حال انجام';
    return '';
  }

  // ─── Step Viewer ────────────────────────────────────────────────
  function openStep(stepId) {
    const s = state.detail.steps.find(x => x.step_id === stepId);
    if (!s) return;

    state.openStepId = stepId;
    document.getElementById('obViewerTitle').textContent = s.title;
    const body = document.getElementById('obViewerBody');
    const footer = document.getElementById('obViewerFooter');

    const descHtml = s.description ? `<p class="viewer-text-body" style="margin-bottom:16px;">${esc(s.description)}</p>` : '';

    if (s.type === 'content' && s.content_id) {
      body.innerHTML = `${descHtml}<div style="text-align:center;padding:20px 10px;"><div style="font-size:38px;margin-bottom:12px;">📚</div><p style="color:var(--gray-500);font-size:13.5px;">${esc(s.content_title || 'محتوای مرتبط')}</p></div>`;
      footer.innerHTML = `<a class="btn btn-secondary" href="/content/detail.html?id=${encodeURIComponent(s.content_id)}" target="_blank" rel="noopener">مشاهده محتوا ↗</a>${completeSkipBtnsHtml(s)}`;
    } else if (s.type === 'quiz' && s.quiz_id) {
      body.innerHTML = `${descHtml}<div style="text-align:center;padding:20px 10px;"><div style="font-size:38px;margin-bottom:12px;">📝</div><p style="color:var(--gray-500);font-size:13.5px;">${esc(s.quiz_title || 'آزمون مرتبط')}</p></div>`;
      footer.innerHTML = `<a class="btn btn-secondary" href="/quiz/index.html?id=${encodeURIComponent(s.quiz_id)}" target="_blank" rel="noopener">شرکت در آزمون ↗</a>${completeSkipBtnsHtml(s)}`;
    } else if (s.type === 'document_upload') {
      body.innerHTML = `${descHtml}<div style="text-align:center;padding:20px 10px;"><div style="font-size:38px;margin-bottom:12px;">📎</div><p style="color:var(--gray-500);font-size:13.5px;">مدرک موردنیاز را طبق راهنمای بالا برای مدیر یا واحد منابع انسانی ارسال کنید و سپس این مرحله را تکمیل‌شده علامت بزنید.</p></div>`;
      footer.innerHTML = completeSkipBtnsHtml(s);
    } else {
      body.innerHTML = descHtml || `<p class="viewer-text-body">برای تکمیل، این وظیفه را در دنیای واقعی انجام دهید و سپس اینجا علامت بزنید.</p>`;
      footer.innerHTML = completeSkipBtnsHtml(s);
    }

    document.getElementById('obViewer').classList.remove('hidden');
  }

  function completeSkipBtnsHtml(s) {
    if (s.status === 'completed') {
      return `<span style="color:var(--success);font-weight:700;font-size:13px;">✓ تکمیل‌شده</span><button class="btn btn-secondary" data-role="close-viewer">بستن</button>`;
    }
    const skipBtn = (!s.is_required && s.status !== 'skipped')
      ? `<button class="btn btn-outline" data-role="skip-step" data-id="${esc(s.step_id)}">رد کردن</button>` : '';
    return `
      <button class="btn btn-primary" data-role="complete-step" data-id="${esc(s.step_id)}">علامت‌گذاری به‌عنوان تکمیل‌شده</button>
      ${skipBtn}
      <button class="btn btn-secondary" data-role="close-viewer">بستن</button>`;
  }

  async function completeStep(stepId) {
    try {
      const detail = await api.post(`/me/onboarding/steps/${stepId}/complete`, {});
      state.detail = detail;
      render();
      toastSuccess('این مرحله به‌عنوان تکمیل‌شده ثبت شد');
      if (state.openStepId === stepId) closeViewer();
    } catch (e) {
      toastError(e.message || 'خطا در ثبت پیشرفت');
    }
  }

  async function skipStep(stepId) {
    try {
      const detail = await api.post(`/me/onboarding/steps/${stepId}/skip`, {});
      state.detail = detail;
      render();
      toastInfo('این مرحله رد شد');
      if (state.openStepId === stepId) closeViewer();
    } catch (e) {
      toastError(e.message || 'خطا در ثبت وضعیت');
    }
  }

  function closeViewer() {
    document.getElementById('obViewer').classList.add('hidden');
    state.openStepId = null;
  }

  function wireDelegatedEvents() {
    const items = document.getElementById('obItems');
    if (items) {
      items.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-role="open-step"], [data-role="open-step-btn"]');
        if (btn) openStep(btn.dataset.id);
      });
    }
    const viewer = document.getElementById('obViewer');
    if (viewer) {
      viewer.addEventListener('click', (e) => {
        const closeBtn = e.target.closest('[data-role="close-viewer"]');
        if (closeBtn) { closeViewer(); return; }
        const completeBtn = e.target.closest('[data-role="complete-step"]');
        if (completeBtn) { completeStep(completeBtn.dataset.id); return; }
        const skipBtn = e.target.closest('[data-role="skip-step"]');
        if (skipBtn) { skipStep(skipBtn.dataset.id); return; }
        if (e.target === viewer) closeViewer();
      });
    }
  }

  return { load };
})();
