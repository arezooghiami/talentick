// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «مدیریت آزمون» (Quiz Admin)
// ════════════════════════════════════════════════════════════════════
// org_admin/super_admin: CRUD کامل آزمون + سوال/گزینه + گزارش تلاش‌ها.
// همیشه محدود به سازمان خودشان (بک‌اند enforce می‌کند).

const QUESTION_TYPE_LABELS = {
  single_choice: 'تک‌گزینه‌ای',
  single_image_choice: 'تک‌گزینه‌ای تصویری',
  multi_choice: 'چندگزینه‌ای',
  true_false: 'درست / غلط',
  short_text: 'تشریحی (نمره‌دهی دستی)',
};

const QuizAdminPage = (() => {
  const state = {
    page: 1, pages: 1, search: '', isActive: '', items: [],
    activeQuiz: null, activeQuestions: [],
    attemptsQuizId: null, attemptsPage: 1, attemptsPages: 1,
  };
  let searchTimer = null;

  // ─── List ───────────────────────────────────────────────────────
  async function load(page = state.page) {
    state.page = page;
    state.isActive = document.getElementById('quizStatusFilter')?.value ?? '';
    const tbody = document.getElementById('quizTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    const p = new URLSearchParams({ page, page_size: 10 });
    if (state.search) p.set('search', state.search);
    if (state.isActive !== '') p.set('is_active', state.isActive);
    try {
      const res = await api.get(`/quizzes/?${p}`);
      state.items = res.items || [];
      setText('quizTotalLabel', `${numFa(res.total)} آزمون یافت شد`);
      renderTable();
      renderPagination('quizPagination', res.page, res.total_pages, load);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function searchDebounced() {
    state.search = document.getElementById('quizSearch').value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load(1), 400);
  }

  function renderTable() {
    const tbody = document.getElementById('quizTableBody');
    if (!state.items.length) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon">📝</div>هنوز آزمونی ثبت نشده</div></td></tr>`;
      return;
    }
    const canEdit = App.isSuperAdmin || App.isOrgAdmin;
    tbody.innerHTML = state.items.map(q => `
      <tr>
        <td style="font-weight:600;">${esc(q.title)}${q.is_onboarding ? ' <span class="badge badge-admin">ورودی</span>' : ''}</td>
        <td>${numFa(q.question_count)} سوال</td>
        <td>${numFa(q.pass_score)}٪</td>
        <td style="color:var(--gray-500);">${q.max_attempts ? numFa(q.max_attempts) + ' بار' : 'نامحدود'}</td>
        <td>${statusBadge(q.is_active)}</td>
        <td>
          <div style="display:flex;gap:4px;flex-wrap:wrap;">
            <button class="btn-action" style="background:var(--primary-light);color:var(--primary);" onclick="QuizAdminPage.openQuestionsModal('${q.id}')">سوالات</button>
            <button class="btn-action" style="background:#EFF6FF;color:#2563EB;" onclick="QuizAdminPage.openAttemptsModal('${q.id}')">شرکت‌کنندگان</button>
            ${canEdit ? `<button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="QuizAdminPage.openEdit('${q.id}')">ویرایش</button>` : ''}
            ${canEdit ? `<button class="btn-action" style="background:#FEF2F2;color:#DC2626;" data-role="delete-quiz" data-id="${q.id}" data-title="${esc(q.title)}">حذف</button>` : ''}
          </div>
        </td>
      </tr>`).join('');
  }

  // ─── Create / Edit Quiz ─────────────────────────────────────────
  function openCreate() {
    document.getElementById('quizModalTitle').textContent = 'آزمون جدید';
    document.getElementById('qz-id').value = '';
    document.getElementById('qz-title').value = '';
    document.getElementById('qz-desc').value = '';
    document.getElementById('qz-pass-score').value = '70';
    document.getElementById('qz-time-limit').value = '';
    document.getElementById('qz-max-attempts').value = '';
    document.getElementById('qz-points').value = '';
    document.getElementById('qz-shuffle-q').checked = false;
    document.getElementById('qz-shuffle-o').checked = false;
    document.getElementById('qz-onboarding').checked = false;
    document.getElementById('qz-active-wrap').classList.add('hidden');
    openModal('modal-quiz');
  }

  function openEdit(id) {
    const q = state.items.find(x => x.id === id);
    if (!q) return;
    document.getElementById('quizModalTitle').textContent = 'ویرایش آزمون';
    document.getElementById('qz-id').value = q.id;
    document.getElementById('qz-title').value = q.title || '';
    document.getElementById('qz-desc').value = q.description || '';
    document.getElementById('qz-pass-score').value = q.pass_score;
    document.getElementById('qz-time-limit').value = q.time_limit_min ?? '';
    document.getElementById('qz-max-attempts').value = q.max_attempts ?? '';
    document.getElementById('qz-points').value = q.points_override ?? '';
    document.getElementById('qz-shuffle-q').checked = !!q.shuffle_questions;
    document.getElementById('qz-shuffle-o').checked = !!q.shuffle_options;
    document.getElementById('qz-onboarding').checked = !!q.is_onboarding;
    document.getElementById('qz-active').checked = !!q.is_active;
    document.getElementById('qz-active-wrap').classList.remove('hidden');
    openModal('modal-quiz');
  }

  async function save() {
    const id = document.getElementById('qz-id').value;
    const title = document.getElementById('qz-title').value.trim();
    if (!title) { toastError('عنوان آزمون اجباری است'); return; }
    const passScore = parseInt(document.getElementById('qz-pass-score').value, 10);
    if (isNaN(passScore) || passScore < 0 || passScore > 100) { toastError('نمره قبولی باید بین ۰ تا ۱۰۰ باشد'); return; }

    const timeLimitRaw = document.getElementById('qz-time-limit').value;
    const maxAttemptsRaw = document.getElementById('qz-max-attempts').value;
    const pointsRaw = document.getElementById('qz-points').value;

    const payload = {
      title,
      description: document.getElementById('qz-desc').value.trim() || null,
      pass_score: passScore,
      time_limit_min: timeLimitRaw ? parseInt(timeLimitRaw, 10) : null,
      max_attempts: maxAttemptsRaw ? parseInt(maxAttemptsRaw, 10) : null,
      points_override: pointsRaw !== '' ? parseInt(pointsRaw, 10) : null,
      shuffle_questions: document.getElementById('qz-shuffle-q').checked,
      shuffle_options: document.getElementById('qz-shuffle-o').checked,
      is_onboarding: document.getElementById('qz-onboarding').checked,
    };
    if (id) payload.is_active = document.getElementById('qz-active').checked;

    const btn = document.getElementById('btn-save-quiz');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/quizzes/${id}`, payload); toastSuccess('آزمون با موفقیت ویرایش شد'); }
      else { await api.post('/quizzes/', payload); toastSuccess('آزمون با موفقیت ایجاد شد'); }
      closeModal('modal-quiz');
      await load(id ? state.page : 1);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function remove(id, title) {
    confirmAction(`آیا مطمئن هستید که می‌خواهید آزمون "${title}" را حذف کنید؟ تمام سوالات و تلاش‌های ثبت‌شده روی آن نیز حذف می‌شوند.`, async () => {
      await api.delete(`/quizzes/${id}`);
      toastSuccess('آزمون با موفقیت حذف شد');
      await load(1);
    });
  }

  // ─── Questions Modal ────────────────────────────────────────────
  async function openQuestionsModal(quizId) {
    const q = state.items.find(x => x.id === quizId);
    state.activeQuiz = quizId;
    document.getElementById('questionsModalTitle').textContent = q ? `سوالات «${q.title}»` : 'سوالات آزمون';
    openModal('modal-quiz-questions');
    await loadQuestions();
  }

  async function loadQuestions() {
    const wrap = document.getElementById('questionsList');
    wrap.innerHTML = `<div class="loading-row" style="padding:20px;text-align:center;">در حال بارگذاری...</div>`;
    try {
      const detail = await api.get(`/quizzes/${state.activeQuiz}`);
      state.activeQuestions = detail.questions || [];
      renderQuestions();
    } catch (e) {
      wrap.innerHTML = `<div style="color:var(--danger);text-align:center;padding:20px;">خطا در بارگذاری: ${esc(e.message)}</div>`;
    }
  }

  function renderQuestions() {
    const wrap = document.getElementById('questionsList');
    if (!state.activeQuestions.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-icon">❓</div>هنوز سوالی اضافه نشده</div>`;
      return;
    }
    wrap.innerHTML = state.activeQuestions.map((qs, idx) => `
      <div class="item-row" style="align-items:flex-start;">
        <div class="item-row-order">${numFa(idx + 1)}</div>
        <div class="item-row-icon">${qs.type === 'short_text' ? '✍️' : qs.type === 'single_image_choice' ? '🖼️' : '☑️'}</div>
        <div class="item-row-info">
          <div class="item-row-title">${esc(qs.body)}</div>
          <div class="item-row-meta">${QUESTION_TYPE_LABELS[qs.type] || qs.type} • ${numFa(qs.score)} امتیاز${qs.options?.length ? ' • ' + numFa(qs.options.length) + ' گزینه' : ''}</div>
        </div>
        <div class="item-row-actions">
          <button class="btn-icon" title="ویرایش" onclick="QuizAdminPage.openEditQuestion('${qs.id}')">✎</button>
          <button class="btn-icon" title="حذف" onclick="QuizAdminPage.removeQuestion('${qs.id}')">🗑</button>
        </div>
      </div>`).join('');
  }

  // ─── Question Create/Edit ───────────────────────────────────────
  function openCreateQuestion() {
    document.getElementById('questionModalTitle').textContent = 'سوال جدید';
    document.getElementById('q-id').value = '';
    document.getElementById('q-body').value = '';
    document.getElementById('q-type').value = 'single_choice';
    document.getElementById('q-score').value = '1';
    document.getElementById('q-explanation').value = '';
    setOptionsMode('single_choice');
    renderOptionsBuilder([{ body: '', is_correct: false }, { body: '', is_correct: false }]);
    openModal('modal-question');
  }

  function isImageType(type) { return type === 'single_image_choice'; }

  // مسیر آپلود تصویر گزینه — org_id آزمون فعال را می‌فرستد (برای آزمون Public
  // خالی می‌ماند و بک‌اند برای super_admin آن را None در نظر می‌گیرد).
  function quizUploadPath() {
    const q = state.items.find(x => x.id === state.activeQuiz);
    const orgId = q && q.org_id;
    return '/quizzes/upload' + (orgId ? `?org_id=${encodeURIComponent(orgId)}` : '');
  }

  function openEditQuestion(id) {
    const qs = state.activeQuestions.find(x => x.id === id);
    if (!qs) return;
    document.getElementById('questionModalTitle').textContent = 'ویرایش سوال';
    document.getElementById('q-id').value = qs.id;
    document.getElementById('q-body').value = qs.body || '';
    document.getElementById('q-type').value = qs.type;
    document.getElementById('q-score').value = qs.score ?? 1;
    document.getElementById('q-explanation').value = qs.explanation || '';
    setOptionsMode(qs.type);
    renderOptionsBuilder((qs.options || []).map(o => ({ body: o.body, is_correct: o.is_correct, image_url: o.image_url })));
    openModal('modal-question');
  }

  function onQuestionTypeChange() {
    const type = document.getElementById('q-type').value;
    const list = document.getElementById('q-options-list');
    const wasImage = list.dataset.imageMode === '1';
    setOptionsMode(type);
    if (type === 'true_false') {
      renderOptionsBuilder([{ body: 'درست', is_correct: true }, { body: 'غلط', is_correct: false }]);
    } else if (type !== 'short_text') {
      // هنگام جابه‌جایی بین حالت تصویری و متنی، ردیف‌ها را از نو می‌سازیم تا
      // متن/تصویرِ حالت قبل باقی نماند.
      const rows = list.querySelectorAll('.option-row').length;
      if (rows < 2 || wasImage !== isImageType(type)) {
        renderOptionsBuilder([{ body: '', is_correct: false }, { body: '', is_correct: false }]);
      }
    }
  }

  function setOptionsMode(type) {
    const wrap = document.getElementById('q-options-wrap');
    const list = document.getElementById('q-options-list');
    const addBtn = document.getElementById('btn-add-option');
    if (type === 'short_text') {
      wrap.classList.add('hidden');
      return;
    }
    wrap.classList.remove('hidden');
    list.dataset.mode = type === 'multi_choice' ? 'checkbox' : 'radio';
    list.dataset.imageMode = isImageType(type) ? '1' : '';
    addBtn.classList.toggle('hidden', type === 'true_false');
    document.getElementById('q-options-hint').textContent = isImageType(type)
      ? 'برای هر گزینه یک تصویر آپلود کنید (متن زیر تصویر اختیاری است) و دقیقاً یک گزینه را به‌عنوان پاسخ صحیح علامت بزنید'
      : type === 'multi_choice'
        ? 'حداقل یک گزینه را به‌عنوان پاسخ صحیح علامت بزنید (می‌توانید چند گزینه انتخاب کنید)'
        : 'دقیقاً یک گزینه را به‌عنوان پاسخ صحیح علامت بزنید';
  }

  function renderOptionsBuilder(options) {
    const list = document.getElementById('q-options-list');
    const imageMode = list.dataset.imageMode === '1';
    list.innerHTML = options.map((o) => optionRowHtml(o, imageMode)).join('');
    if (imageMode) hydrateAuthedImages(list);
  }

  function optionRowHtml(opt, imageMode) {
    const body = opt.body || '';
    const isCorrect = !!opt.is_correct;
    const imageUrl = opt.image_url || '';
    if (imageMode) {
      const thumb = imageUrl
        ? `<img data-src="${esc(imageUrl)}" alt="" class="q-opt-thumb-img" style="width:100%;height:100%;object-fit:cover;">`
        : `<span style="color:var(--gray-400);font-size:11px;">بدون تصویر</span>`;
      return `
        <div class="option-row" style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;padding:10px;border:1px solid var(--border);border-radius:8px;">
          <input type="checkbox" class="q-opt-correct" ${isCorrect ? 'checked' : ''} onchange="QuizAdminPage.onOptionCorrectChange(this)" style="width:17px;height:17px;flex-shrink:0;margin-top:32px;" title="پاسخ صحیح">
          <div style="display:flex;flex-direction:column;gap:6px;flex:1;">
            <div class="q-opt-thumb" style="width:110px;height:80px;border-radius:6px;overflow:hidden;background:var(--gray-100);display:flex;align-items:center;justify-content:center;">${thumb}</div>
            <input type="hidden" class="q-opt-image" value="${esc(imageUrl)}">
            <label class="btn btn-secondary btn-sm" style="align-self:flex-start;cursor:pointer;">
              ${imageUrl ? 'تغییر تصویر' : 'آپلود تصویر'}
              <input type="file" accept="image/*" style="display:none;" onchange="QuizAdminPage.uploadOptionImage(this)">
            </label>
            <input type="text" class="form-control q-opt-body" value="${esc(body)}" placeholder="متن زیر تصویر (اختیاری)" style="max-width:320px;">
          </div>
          <button type="button" class="btn-icon" onclick="QuizAdminPage.removeOption(this)" title="حذف گزینه">✕</button>
        </div>`;
    }
    return `
      <div class="option-row" style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <input type="checkbox" class="q-opt-correct" ${isCorrect ? 'checked' : ''} onchange="QuizAdminPage.onOptionCorrectChange(this)" style="width:17px;height:17px;flex-shrink:0;">
        <input type="text" class="form-control q-opt-body" value="${esc(body)}" placeholder="متن گزینه" style="flex:1;">
        <button type="button" class="btn-icon" onclick="QuizAdminPage.removeOption(this)" title="حذف گزینه">✕</button>
      </div>`;
  }

  async function uploadOptionImage(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { toastError('فقط فایل تصویری مجاز است'); input.value = ''; return; }
    const row = input.closest('.option-row');
    const label = input.closest('label');
    const prevLabel = label ? label.childNodes[0].textContent : '';
    if (label) label.childNodes[0].textContent = 'در حال آپلود... ';
    try {
      const res = await api.upload(quizUploadPath(), file);
      row.querySelector('.q-opt-image').value = res.url;
      const thumb = row.querySelector('.q-opt-thumb');
      thumb.innerHTML = `<img data-src="${esc(res.url)}" alt="" style="width:100%;height:100%;object-fit:cover;">`;
      await hydrateAuthedImages(thumb);
      if (label) label.childNodes[0].textContent = 'تغییر تصویر ';
      toastSuccess('تصویر گزینه آپلود شد');
    } catch (e) {
      toastError(e.message || 'خطا در آپلود تصویر');
      if (label) label.childNodes[0].textContent = prevLabel;
    } finally {
      input.value = '';
    }
  }

  function onOptionCorrectChange(checkbox) {
    const list = document.getElementById('q-options-list');
    if (list.dataset.mode === 'radio' && checkbox.checked) {
      list.querySelectorAll('.q-opt-correct').forEach(cb => { if (cb !== checkbox) cb.checked = false; });
    }
  }

  function addOption() {
    const list = document.getElementById('q-options-list');
    list.insertAdjacentHTML('beforeend', optionRowHtml({ body: '', is_correct: false }, list.dataset.imageMode === '1'));
  }

  function removeOption(btn) {
    const list = document.getElementById('q-options-list');
    if (list.querySelectorAll('.option-row').length <= 2) {
      toastError('حداقل ۲ گزینه لازم است');
      return;
    }
    btn.closest('.option-row').remove();
  }

  function collectOptions() {
    return Array.from(document.querySelectorAll('#q-options-list .option-row')).map((row, idx) => {
      const imageEl = row.querySelector('.q-opt-image');
      return {
        body: row.querySelector('.q-opt-body').value.trim(),
        is_correct: row.querySelector('.q-opt-correct').checked,
        image_url: imageEl ? (imageEl.value || null) : null,
        order_index: idx,
      };
    });
  }

  async function saveQuestion() {
    const id = document.getElementById('q-id').value;
    const body = document.getElementById('q-body').value.trim();
    if (!body) { toastError('متن سوال اجباری است'); return; }
    const type = document.getElementById('q-type').value;
    const score = parseInt(document.getElementById('q-score').value, 10) || 0;
    const explanation = document.getElementById('q-explanation').value.trim() || null;

    let options = [];
    if (type !== 'short_text') {
      options = collectOptions();
      if (options.length < 2) { toastError('حداقل ۲ گزینه لازم است'); return; }
      const correctCount = options.filter(o => o.is_correct).length;
      if (isImageType(type)) {
        if (options.some(o => !o.image_url)) { toastError('برای همه‌ی گزینه‌ها تصویر آپلود کنید'); return; }
        if (correctCount !== 1) { toastError('دقیقاً یک گزینه‌ی صحیح انتخاب کنید'); return; }
      } else {
        if (options.some(o => !o.body)) { toastError('متن همه‌ی گزینه‌ها را وارد کنید'); return; }
        if ((type === 'single_choice' || type === 'true_false') && correctCount !== 1) {
          toastError('دقیقاً یک گزینه‌ی صحیح انتخاب کنید'); return;
        }
        if (type === 'multi_choice' && correctCount < 1) {
          toastError('حداقل یک گزینه‌ی صحیح انتخاب کنید'); return;
        }
      }
    }

    const payload = { body, type, score, explanation, options };
    if (!id) payload.order_index = state.activeQuestions.length;

    const btn = document.getElementById('btn-save-question');
    setLoading(btn, true);
    try {
      if (id) { await api.patch(`/quizzes/questions/${id}`, payload); toastSuccess('سوال با موفقیت ویرایش شد'); }
      else { await api.post(`/quizzes/${state.activeQuiz}/questions`, payload); toastSuccess('سوال با موفقیت اضافه شد'); }
      closeModal('modal-question');
      await loadQuestions();
      await load(state.page);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function removeQuestion(id) {
    confirmAction('آیا مطمئن هستید که می‌خواهید این سوال را حذف کنید؟', async () => {
      await api.delete(`/quizzes/questions/${id}`);
      toastSuccess('سوال با موفقیت حذف شد');
      await loadQuestions();
      await load(state.page);
    });
  }

  // ─── Attempts Report Modal ──────────────────────────────────────
  async function openAttemptsModal(quizId) {
    const q = state.items.find(x => x.id === quizId);
    state.attemptsQuizId = quizId;
    state.attemptsPage = 1;
    document.getElementById('attemptsModalTitle').textContent = q ? `شرکت‌کنندگان «${q.title}»` : 'شرکت‌کنندگان';
    openModal('modal-quiz-attempts');
    await loadAttempts();
  }

  async function loadAttempts(page = state.attemptsPage) {
    state.attemptsPage = page;
    const tbody = document.getElementById('attemptsTableBody');
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const res = await api.get(`/quizzes/${state.attemptsQuizId}/attempts?page=${page}&page_size=10`);
      if (!res.items.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--gray-400);">هنوز کسی در این آزمون شرکت نکرده</td></tr>`;
        document.getElementById('attemptsPagination').innerHTML = '';
        return;
      }
      tbody.innerHTML = res.items.map(a => `
        <tr>
          <td><div style="font-weight:500;">${esc(a.user_full_name)}</div><div style="font-size:11px;color:var(--gray-400);direction:ltr;text-align:right;">${esc(a.user_email)}</div></td>
          <td>${numFa(a.score)} / ${numFa(a.max_score)}</td>
          <td>${numFa(Math.round(a.percentage))}٪</td>
          <td>${a.passed ? '<span class="badge badge-active">قبول</span>' : '<span class="badge badge-inactive">مردود</span>'}</td>
          <td style="color:var(--gray-500);">${fmtDate(a.completed_at)}</td>
        </tr>`).join('');
      renderPagination('attemptsPagination', res.page, res.total_pages, loadAttempts);
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row Actions — به‌جای onclick اینلاین با عنوان آزمون ────
  document.getElementById('quizTableBody')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="delete-quiz"]');
    if (btn) remove(btn.dataset.id, btn.dataset.title);
  });

  return {
    load, searchDebounced, openCreate, openEdit, save, remove,
    openQuestionsModal, loadQuestions,
    openCreateQuestion, openEditQuestion, onQuestionTypeChange,
    onOptionCorrectChange, addOption, removeOption, uploadOptionImage, saveQuestion, removeQuestion,
    openAttemptsModal, loadAttempts,
  };
})();
