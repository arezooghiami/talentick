// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «سازمان‌ها» (فقط super_admin)
// ════════════════════════════════════════════════════════════════════

const OrgsPage = (() => {
  const state = { items: [] };

  async function load() {
    const tbody = document.getElementById('orgsTableBody');
    tbody.innerHTML = `<tr><td colspan="6" class="loading-row">در حال بارگذاری...</td></tr>`;
    try {
      const d = await api.get('/orgs/');
      const items = Array.isArray(d) ? d : (d.items || []);
      state.items = items;
      setText('orgsTotalLabel', `مجموع ${numFa(items.length)} سازمان`);

      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--gray-400);">سازمانی ثبت نشده</td></tr>`;
        return;
      }
      tbody.innerHTML = items.map((o, i) => `
        <tr>
          <td style="color:var(--gray-400);">${numFa(i + 1)}</td>
          <td style="font-weight:500;">${esc(o.name)}</td>
          <td style="direction:ltr;text-align:right;color:var(--gray-500);font-size:12px;">${esc(o.slug || '—')}</td>
          <td>${statusBadge(o.is_active !== false)}</td>
          <td style="color:var(--gray-500);">${fmtDate(o.created_at)}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="btn-action" style="background:var(--primary-light);color:var(--primary);" onclick="StructurePage.openFor('${o.id}','${esc(o.name)}')">ساختار سازمانی</button>
              <button class="btn-action" style="background:var(--primary-light);color:var(--primary);" onclick="DocumentsPage.openFor('${o.id}','${esc(o.name)}')">کتابخانه اسناد</button>
              <button class="btn-action" style="background:var(--gray-100);color:var(--gray-700);" onclick="OrgsPage.openEdit('${o.id}')">ویرایش</button>
              <button class="btn-action" style="background:#FEF2F2;color:#DC2626;" onclick="OrgsPage.remove('${o.id}','${esc(o.name)}')">حذف</button>
            </div>
          </td>
        </tr>`).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--danger);">خطا در بارگذاری: ${esc(e.message)}</td></tr>`;
    }
  }

  function openCreate() {
    document.getElementById('orgModalTitle').textContent = 'سازمان جدید';
    document.getElementById('o-id').value = '';
    ['o-name', 'o-slug', 'o-name-en', 'o-website', 'o-desc'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('o-slug').disabled = false;
    document.getElementById('o-slug-hint').classList.remove('hidden');
    openModal('modal-org');
  }

  function openEdit(id) {
    const o = state.items.find(x => x.id === id);
    if (!o) return;
    document.getElementById('orgModalTitle').textContent = 'ویرایش سازمان';
    document.getElementById('o-id').value = o.id;
    document.getElementById('o-name').value = o.name || '';
    document.getElementById('o-slug').value = o.slug || '';
    document.getElementById('o-slug').disabled = true; // slug بعد از ساخت قابل تغییر نیست
    document.getElementById('o-slug-hint').classList.add('hidden');
    document.getElementById('o-name-en').value = o.name_en || '';
    document.getElementById('o-website').value = o.website || '';
    document.getElementById('o-desc').value = o.description || '';
    openModal('modal-org');
  }

  async function save() {
    const id = document.getElementById('o-id').value;
    const name = document.getElementById('o-name').value.trim();
    const slug = document.getElementById('o-slug').value.trim();

    if (!name) { toastError('نام سازمان اجباری است'); return; }
    if (!id) {
      if (!slug) { toastError('Slug اجباری است'); return; }
      if (!/^[a-z0-9-]+$/.test(slug)) { toastError('Slug فقط حروف لاتین کوچک، اعداد و خط تیره'); return; }
    }

    const payload = {
      name,
      name_en: document.getElementById('o-name-en').value.trim() || null,
      website: document.getElementById('o-website').value.trim() || null,
      description: document.getElementById('o-desc').value.trim() || null,
    };
    if (!id) payload.slug = slug;

    const btn = document.getElementById('btn-save-org');
    setLoading(btn, true);
    try {
      if (id) {
        await api.patch(`/orgs/${id}`, payload);
        toastSuccess('سازمان با موفقیت ویرایش شد');
      } else {
        await api.post('/orgs/', payload);
        toastSuccess('سازمان با موفقیت ایجاد شد');
      }
      closeModal('modal-org');
      await load();
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  function remove(id, name) {
    confirmAction(
      `آیا مطمئن هستید که می‌خواهید سازمان "${name}" را حذف کنید؟ تمام کاربران این سازمان نیز حذف می‌شوند. این عمل قابل بازگشت نیست.`,
      async () => {
        await api.delete(`/orgs/${id}`);
        toastSuccess('سازمان با موفقیت حذف شد');
        await load();
      }
    );
  }

  function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }

  return { load, openCreate, openEdit, save, remove, getCache: () => state.items };
})();