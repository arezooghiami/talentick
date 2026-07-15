// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «شرکت در آزمون» (Quiz Taking)
// ════════════════════════════════════════════════════════════════════
// جریان: intro → question-by-question → submit → result.
// اگر با content_id/item_id باز شده باشد (از یک آیتم quiz_ref در محتوا)،
// بعد از ثبت موفق، پیشرفت آن آیتم هم به‌صورت خودکار تکمیل‌شده ثبت می‌شود.

const QuizTakePage = (() => {
  const state = {
    quizId: null, contentId: null, itemId: null,
    quiz: null, questions: [], answers: {}, current: 0,
    startedAt: null, timerInterval: null,
  };

  async function load() {
    const params = new URLSearchParams(location.search);
    state.quizId = params.get('id');
    state.contentId = params.get('content_id');
    state.itemId = params.get('item_id');
    if (!state.quizId) { showFatal('شناسه آزمون مشخص نیست'); return; }

    try {
      const quiz = await api.get(`/me/quizzes/${state.quizId}`);
      state.quiz = quiz;
      state.questions = quiz.questions || [];
      renderIntro();
    } catch (e) {
      showFatal(e.message || 'آزمون یافت نشد یا دسترسی ندارید');
    }
  }

  function showFatal(msg) {
    document.getElementById('quizRoot').innerHTML = `<div class="emp-empty"><div class="icon">⚠️</div><h3>${esc(msg)}</h3><a class="btn btn-secondary" href="/onboarding/index.html" style="margin-top:14px;display:inline-flex;">بازگشت به خانه</a></div>`;
  }

  // ─── Intro Screen ───────────────────────────────────────────────
  function renderIntro() {
    const q = state.quiz;
    setView('intro');
    document.getElementById('introTitle').textContent = q.title;
    document.getElementById('introDesc').textContent = q.description || 'برای شروع، روی دکمه‌ی زیر بزنید.';
    document.getElementById('introQuestionCount').textContent = numFa(state.questions.length);
    document.getElementById('introPassScore').textContent = numFa(q.pass_score) + '٪';
    document.getElementById('introTimeLimit').textContent = q.time_limit_min ? numFa(q.time_limit_min) + ' دقیقه' : 'نامحدود';
    document.getElementById('introAttempts').textContent = q.max_attempts
      ? `${numFa(q.attempts_used)} از ${numFa(q.max_attempts)}`
      : `${numFa(q.attempts_used)} (نامحدود)`;

    const btn = document.getElementById('btnStartQuiz');
    if (!q.can_attempt) {
      btn.disabled = true;
      btn.textContent = q.max_attempts && q.attempts_used >= q.max_attempts
        ? 'تعداد دفعات مجاز شما به پایان رسیده است'
        : 'این آزمون در حال حاضر غیرفعال است';
    } else if (!state.questions.length) {
      btn.disabled = true;
      btn.textContent = 'این آزمون هنوز سوالی ندارد';
    } else {
      btn.disabled = false;
      btn.textContent = 'شروع آزمون';
    }

    loadHistory();
  }

  async function loadHistory() {
    const wrap = document.getElementById('introHistory');
    try {
      const attempts = await api.get(`/me/quizzes/${state.quizId}/attempts`);
      if (!attempts.length) { wrap.innerHTML = ''; return; }
      wrap.innerHTML = `
        <div style="margin-top:26px;text-align:right;">
          <div style="font-size:12.5px;font-weight:700;color:var(--gray-600);margin-bottom:10px;">تلاش‌های قبلی شما</div>
          ${attempts.slice(0, 5).map(a => `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);font-size:12.5px;">
              <span style="color:var(--gray-500);">${fmtDate(a.completed_at)}</span>
              <span>${numFa(Math.round(a.percentage))}٪</span>
              <span class="${a.passed ? 'status-chip completed' : 'status-chip not_started'}">${a.passed ? 'قبول' : 'مردود'}</span>
            </div>`).join('')}
        </div>`;
    } catch { wrap.innerHTML = ''; }
  }

  // ─── Question Flow ──────────────────────────────────────────────
  function start() {
    state.startedAt = new Date();
    state.answers = {};
    state.current = 0;
    setView('quiz');
    startTimer();
    renderQuestion();
  }

  function startTimer() {
    clearInterval(state.timerInterval);
    const badge = document.getElementById('quizTimer');
    if (!state.quiz.time_limit_min) { badge.classList.add('hidden'); return; }
    badge.classList.remove('hidden');
    const deadline = state.startedAt.getTime() + state.quiz.time_limit_min * 60000;
    state.timerInterval = setInterval(() => {
      const remain = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
      const m = Math.floor(remain / 60), s = remain % 60;
      badge.textContent = `⏱ ${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
      badge.style.color = remain < 60 ? 'var(--danger)' : '';
      if (remain <= 0) {
        clearInterval(state.timerInterval);
        toastError('زمان آزمون به پایان رسید — در حال ثبت پاسخ‌های شما...');
        submit();
      }
    }, 1000);
  }

  function renderQuestion() {
    const q = state.questions[state.current];
    document.getElementById('quizProgressBar').innerHTML = state.questions.map((_, i) =>
      `<div class="seg ${i <= state.current ? 'done' : ''}"></div>`).join('');
    document.getElementById('quizQuestionIdx').textContent = `سوال ${numFa(state.current + 1)} از ${numFa(state.questions.length)}`;
    document.getElementById('quizQuestionBody').textContent = q.body;

    const answerWrap = document.getElementById('quizAnswerArea');
    const existing = state.answers[q.id];

    if (q.type === 'short_text') {
      answerWrap.innerHTML = `<textarea class="quiz-textarea" id="quizTextAnswer" placeholder="پاسخ خود را بنویسید...">${esc(existing?.text_answer || '')}</textarea>`;
      document.getElementById('quizTextAnswer').addEventListener('input', (e) => {
        state.answers[q.id] = { selected_option_ids: [], text_answer: e.target.value };
        updateDots();
      });
    } else {
      const isMulti = q.type === 'multi_choice';
      const selected = new Set(existing?.selected_option_ids || []);
      answerWrap.innerHTML = q.options.map(o => `
        <div class="quiz-option ${isMulti ? 'multi' : ''} ${selected.has(o.id) ? 'selected' : ''}" onclick="QuizTakePage.selectOption('${q.id}','${o.id}',${isMulti})">
          <span class="opt-mark">${selected.has(o.id) ? '✓' : ''}</span>
          <span class="opt-text">${esc(o.body)}</span>
        </div>`).join('');
    }

    document.getElementById('btnPrevQuestion').disabled = state.current === 0;
    const isLast = state.current === state.questions.length - 1;
    document.getElementById('btnNextQuestion').classList.toggle('hidden', isLast);
    document.getElementById('btnFinishQuiz').classList.toggle('hidden', !isLast);

    renderDots();
  }

  function renderDots() {
    document.getElementById('quizDots').innerHTML = state.questions.map((qq, i) => {
      const answered = !!state.answers[qq.id] && (state.answers[qq.id].selected_option_ids?.length || state.answers[qq.id].text_answer);
      const cls = i === state.current ? 'current' : (answered ? 'answered' : '');
      return `<button type="button" class="quiz-dot ${cls}" onclick="QuizTakePage.gotoQuestion(${i})">${numFa(i + 1)}</button>`;
    }).join('');
  }

  function updateDots() { renderDots(); }

  function selectOption(questionId, optionId, isMulti) {
    const cur = state.answers[questionId] || { selected_option_ids: [], text_answer: null };
    let ids = new Set(cur.selected_option_ids || []);
    if (isMulti) {
      ids.has(optionId) ? ids.delete(optionId) : ids.add(optionId);
    } else {
      ids = new Set([optionId]);
    }
    state.answers[questionId] = { selected_option_ids: Array.from(ids), text_answer: null };
    renderQuestion();
  }

  function gotoQuestion(idx) {
    if (idx < 0 || idx >= state.questions.length) return;
    state.current = idx;
    renderQuestion();
  }
  function next() { gotoQuestion(state.current + 1); }
  function prev() { gotoQuestion(state.current - 1); }

  // ─── Submit ──────────────────────────────────────────────────────
  async function submit() {
    clearInterval(state.timerInterval);
    const btn = document.getElementById('btnFinishQuiz');
    setLoading(btn, true);
    try {
      const result = await api.post(`/me/quizzes/${state.quizId}/attempts`, {
        started_at: state.startedAt.toISOString(),
        answers: state.answers,
      });
      if (state.contentId && state.itemId) {
        try {
          await api.post(`/me/contents/${state.contentId}/items/${state.itemId}/progress`, { progress_pct: 100 });
        } catch { /* غیرحیاتی — نتیجه‌ی آزمون مهم‌تر است */ }
      }
      renderResult(result);
    } catch (e) {
      toastError(e.message || 'خطا در ثبت پاسخ‌ها');
      setLoading(btn, false);
    }
  }

  // ─── Result Screen ──────────────────────────────────────────────
  function renderResult(result) {
    setView('result');
    const pct = Math.round(result.percentage);
    const color = result.passed ? '#10B981' : '#EF4444';
    const circumference = 2 * Math.PI * 60;
    const offset = circumference - (pct / 100) * circumference;

    document.getElementById('resultRing').innerHTML = `
      <svg width="140" height="140">
        <circle cx="70" cy="70" r="60" stroke="#E5E7EB" stroke-width="10" fill="none"></circle>
        <circle cx="70" cy="70" r="60" stroke="${color}" stroke-width="10" fill="none"
          stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round"></circle>
      </svg>
      <span class="quiz-result-pct">${numFa(pct)}٪</span>`;

    const verdictEl = document.getElementById('resultVerdict');
    verdictEl.textContent = result.passed ? '🎉 قبول شدید' : 'موفق نشدید';
    verdictEl.className = 'quiz-result-verdict ' + (result.passed ? 'pass' : 'fail');
    document.getElementById('resultSub').textContent = `نمره‌ی قبولی این آزمون ${numFa(state.quiz.pass_score)}٪ است`;
    document.getElementById('resultScore').textContent = `${numFa(result.score)} از ${numFa(result.max_score)}`;
    document.getElementById('resultDuration').textContent = result.duration_sec != null ? fmtDuration(result.duration_sec) : '—';

    document.getElementById('resultBackToContent').classList.toggle('hidden', !(state.contentId));
    document.getElementById('resultRetry').classList.toggle('hidden', !canRetry());

    document.getElementById('resultAnswers').innerHTML = result.answers.map((a, i) => {
      const cls = a.is_correct === true ? 'correct' : (a.is_correct === false ? 'wrong' : '');
      let optsHtml = '';
      if (a.question_type !== 'short_text') {
        optsHtml = (state.questions[i]?.options || []).map(o => {
          const isCorrectOpt = a.correct_option_ids.includes(o.id);
          const wasSelected = a.selected_option_ids.includes(o.id);
          let cls2 = '';
          if (isCorrectOpt) cls2 = 'correct-opt';
          else if (wasSelected) cls2 = 'selected-wrong';
          return `<div class="quiz-answer-opt ${cls2}">${wasSelected ? '● ' : '○ '}${esc(o.body)}</div>`;
        }).join('');
      } else {
        optsHtml = `<div class="quiz-answer-opt">پاسخ شما: ${esc(a.text_answer || '—')}</div><div class="quiz-answer-opt" style="color:var(--gray-400);">(این نوع سوال نیاز به نمره‌دهی دستی دارد)</div>`;
      }
      return `
        <div class="quiz-answer-item ${cls}">
          <div class="quiz-answer-q">${numFa(i + 1)}. ${esc(a.question_body)}</div>
          ${optsHtml}
          ${a.explanation ? `<div class="quiz-answer-explain">💡 ${esc(a.explanation)}</div>` : ''}
        </div>`;
    }).join('');
  }

  function canRetry() {
    const q = state.quiz;
    return q.max_attempts == null || (q.attempts_used + 1) < q.max_attempts;
  }

  async function retry() {
    await load();
  }

  function fmtDuration(sec) {
    const m = Math.floor(sec / 60), s = sec % 60;
    return m > 0 ? `${numFa(m)} دقیقه و ${numFa(s)} ثانیه` : `${numFa(s)} ثانیه`;
  }

  function setView(name) {
    ['intro', 'quiz', 'result'].forEach(v => document.getElementById('view-' + v).classList.toggle('hidden', v !== name));
  }

  return { load, start, selectOption, gotoQuestion, next, prev, submit, retry };
})();
