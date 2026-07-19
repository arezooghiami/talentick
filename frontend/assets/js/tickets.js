// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «تیکت‌های من» (کارمند)
// ════════════════════════════════════════════════════════════════════
// ثبت تیکت جدید (درخواست/بازخورد/سؤال) + گفتگوی رفت‌وبرگشتی با ادمین +
// بستن با امتیاز رضایت (۱ تا ۵) یا بازکردن دوباره در صورت نارضایتی.

const MyTicketsPage = (() => {
  const STATUS_LABEL = { open: 'باز', answered: 'پاسخ داده‌شده', closed: 'بسته‌شده' };
  const STATUS_CLASS = { open: 'ticket-status-open', answered: 'ticket-status-answered', closed: 'ticket-status-closed' };

  const state = {
    page: 1, status: '', items: [],
    currentTicketId: null, currentTicketData: null,
    categoriesLoaded: false, contentsLoaded: false,
  };

  // ─── لیست ─────────────────────────────────────────────────────────

  async function load(page = state.page) {
    state.page = page;
    const list = document.getElementById('tkList');
    list.innerHTML = '<div class="emp-skeleton" style="height:66px;"></div><div class="emp-skeleton" style="height:66px;"></div>';
    const p = new URLSearchParams({ page, page_size: 20 });
    if (state.status) p.set('status', state.status);
    try {
      const res = await api.get(`/me/tickets?${p}`);
      state.items = res.items || [];
      setText('tkCount', `${numFa(res.total)} تیکت`);
      if (!state.items.length) {
        list.innerHTML = `<div class="emp-empty"><div class="icon">🎫</div><h3>تیکتی ثبت نکرده‌اید</h3><p style="color:var(--gray-400);font-size:13px;margin-top:6px;">با دکمه‌ی «تیکت جدید» درخواست، بازخورد یا سؤال خود را ثبت کنید</p></div>`;
        renderPagination('tkPagination', res.page, res.total_pages, load);
        return;
      }
      renderList();
      renderPagination('tkPagination', res.page, res.total_pages, load);
    } catch (e) {
      list.innerHTML = `<div class="emp-empty"><div class="icon">⚠️</div><h3>خطا در بارگذاری: ${esc(e.message)}</h3></div>`;
    }
  }

  function renderList() {
    document.getElementById('tkList').innerHTML = state.items.map(t => `
      <div class="item-card" data-role="open-ticket" data-id="${t.id}">
        <div class="item-card-icon">🎫</div>
        <div class="item-card-info">
          <div class="item-card-title">${esc(t.subject)}</div>
          <div class="item-card-meta">${t.category_name ? esc(t.category_name) + ' • ' : ''}${numFa(t.message_count)} پیام • ${fmtDate(t.updated_at)}</div>
        </div>
        <span class="ticket-status-pill ${STATUS_CLASS[t.status] || ''}">${STATUS_LABEL[t.status] || t.status}</span>
      </div>`).join('');
  }

  function setStatus(status, btn) {
    state.status = status;
    document.querySelectorAll('#tkStatusPills .emp-filter-pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    load(1);
  }

  // ─── ثبت تیکت جدید ────────────────────────────────────────────────

  async function openCreate() {
    document.getElementById('tkc-subject').value = '';
    document.getElementById('tkc-body').value = '';
    await Promise.all([loadCategoriesForSelect(), loadContentsForSelect()]);
    openModal('tkCreateModal');
  }

  async function loadCategoriesForSelect() {
    if (state.categoriesLoaded) return;
    try {
      const cats = await api.get('/ticket-categories?active_only=true');
      document.getElementById('tkc-category').innerHTML = '<option value="">— بدون دسته‌بندی —</option>' +
        cats.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
      state.categoriesLoaded = true;
    } catch { /* غیرحیاتی */ }
  }

  async function loadContentsForSelect() {
    if (state.contentsLoaded) return;
    try {
      const res = await api.get('/me/contents?page=1&page_size=100');
      const items = res.items || [];
      document.getElementById('tkc-content').innerHTML = '<option value="">— هیچ‌کدام —</option>' +
        items.map(c => `<option value="${c.id}">${esc(c.title)}</option>`).join('');
      state.contentsLoaded = true;
    } catch { /* غیرحیاتی */ }
  }

  async function submitCreate() {
    const subject = document.getElementById('tkc-subject').value.trim();
    const body = document.getElementById('tkc-body').value.trim();
    if (!subject) { toastError('موضوع تیکت اجباری است'); return; }
    if (!body) { toastError('توضیحات تیکت اجباری است'); return; }
    const payload = {
      subject, body,
      category_id: document.getElementById('tkc-category').value || null,
      related_content_id: document.getElementById('tkc-content').value || null,
    };
    const btn = document.getElementById('btn-tkc-submit');
    setLoading(btn, true);
    try {
      await api.post('/me/tickets', payload);
      toastSuccess('تیکت با موفقیت ثبت شد');
      closeModal('tkCreateModal');
      await load(1);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  // ─── جزئیات + ترد گفتگو ───────────────────────────────────────────

  async function openDetail(ticketId) {
    state.currentTicketId = ticketId;
    document.getElementById('tk-reply-body').value = '';
    document.getElementById('tkDetailSubject').textContent = 'در حال بارگذاری...';
    document.getElementById('tkThread').innerHTML = '';
    document.getElementById('tkRateWrap').classList.add('hidden');
    openModal('tkDetailModal');
    try {
      const t = await api.get(`/me/tickets/${ticketId}`);
      state.currentTicketData = t;
      renderDetail(t);
    } catch (e) {
      toastError(e.message);
      closeModal('tkDetailModal');
    }
  }

  function renderDetail(t) {
    document.getElementById('tkDetailSubject').textContent = t.subject;
    const metaParts = [
      `<span class="ticket-status-pill ${STATUS_CLASS[t.status] || ''}">${STATUS_LABEL[t.status] || t.status}</span>`,
    ];
    if (t.category_name) metaParts.push(`<span>دسته‌بندی: <b>${esc(t.category_name)}</b></span>`);
    if (t.related_content_title) metaParts.push(`<span>محتوای مرتبط: <b>${esc(t.related_content_title)}</b></span>`);
    if (t.satisfaction_rating) {
      metaParts.push(`<span>امتیاز شما: <span class="ticket-rating-stars">${[1, 2, 3, 4, 5].map(i => `<span class="${i > t.satisfaction_rating ? 'empty' : ''}">★</span>`).join('')}</span></span>`);
    }
    document.getElementById('tkDetailMeta').innerHTML = metaParts.join('');

    document.getElementById('tkThread').innerHTML = (t.messages || []).map(m => {
      const isMine = m.sender_id === t.created_by;
      return `
        <div class="ticket-msg ${isMine ? 'creator' : 'staff'}">
          <div class="ticket-msg-head"><span>${isMine ? 'شما' : esc(m.sender_name || 'مدیر سازمان')}</span><span>${fmtDate(m.created_at)}</span></div>
          <div class="ticket-msg-body">${esc(m.body)}</div>
        </div>`;
    }).join('');
    const thread = document.getElementById('tkThread');
    thread.scrollTop = thread.scrollHeight;

    const isClosed = t.status === 'closed';
    document.getElementById('tkReplyWrap').classList.toggle('hidden', isClosed);
    document.getElementById('btn-tk-send').classList.toggle('hidden', isClosed);
    document.getElementById('btn-tk-close').classList.toggle('hidden', isClosed);
    document.getElementById('btn-tk-reopen').classList.toggle('hidden', !isClosed);
    document.getElementById('tkRateWrap').classList.add('hidden');
  }

  async function sendReply() {
    const body = document.getElementById('tk-reply-body').value.trim();
    if (!body) { toastError('متن پیام نمی‌تواند خالی باشد'); return; }
    const btn = document.getElementById('btn-tk-send');
    setLoading(btn, true);
    try {
      await api.post(`/me/tickets/${state.currentTicketId}/messages`, { body });
      document.getElementById('tk-reply-body').value = '';
      const t = await api.get(`/me/tickets/${state.currentTicketId}`);
      state.currentTicketData = t;
      renderDetail(t);
      await load(state.page);
    } catch (e) { toastError(e.message); }
    finally { setLoading(btn, false); }
  }

  function showRatingPicker() {
    const wrap = document.getElementById('tkRateWrap');
    const stars = document.getElementById('tkRatingStars');
    stars.innerHTML = [1, 2, 3, 4, 5].map(i => `<span class="star" data-role="pick-rating" data-rating="${i}">★</span>`).join('');
    wrap.classList.remove('hidden');
    document.getElementById('btn-tk-close').classList.add('hidden');
    document.getElementById('btn-tk-send').classList.add('hidden');
  }

  async function closeWithRating(rating) {
    try {
      await api.post(`/me/tickets/${state.currentTicketId}/close`, { satisfaction_rating: rating });
      toastSuccess('تیکت با موفقیت بسته شد');
      const t = await api.get(`/me/tickets/${state.currentTicketId}`);
      state.currentTicketData = t;
      renderDetail(t);
      await load(state.page);
    } catch (e) { toastError(e.message); }
  }

  async function reopen() {
    try {
      await api.post(`/me/tickets/${state.currentTicketId}/reopen`);
      toastInfo('تیکت دوباره باز شد');
      const t = await api.get(`/me/tickets/${state.currentTicketId}`);
      state.currentTicketData = t;
      renderDetail(t);
      await load(state.page);
    } catch (e) { toastError(e.message); }
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  // ─── Delegated Row/Star Actions ────────────────────────────────────
  document.getElementById('tkList')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="open-ticket"]');
    if (btn) openDetail(btn.dataset.id);
  });
  document.getElementById('tkRatingStars')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-role="pick-rating"]');
    if (btn) closeWithRating(parseInt(btn.dataset.rating, 10));
  });

  return {
    load, setStatus, openCreate, submitCreate,
    openDetail, sendReply, showRatingPicker, reopen,
  };
})();
