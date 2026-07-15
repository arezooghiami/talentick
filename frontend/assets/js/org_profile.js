// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی «سازمان من» (فقط org_admin)
// ════════════════════════════════════════════════════════════════════
// ویرایش پروفایل سازمانِ خودِ org_admin — از /orgs/me استفاده می‌کند.
// این endpoint برای super_admin هم باز است ولی منوی «سازمان من» فقط
// برای org_admin نمایش داده می‌شود (super_admin از صفحه‌ی «شرکت‌ها»
// با دسترسی کامل به همه‌ی سازمان‌ها کار می‌کند).

const OrgProfilePage = (() => {
  async function load() {
    try {
      const org = await api.get('/orgs/me');
      document.getElementById('op-name').value = org.name || '';
      document.getElementById('op-name-en').value = org.name_en || '';
      document.getElementById('op-website').value = org.website || '';
      document.getElementById('op-phone').value = org.phone || '';
      document.getElementById('op-address').value = org.address || '';
      document.getElementById('op-desc').value = org.description || '';
      document.getElementById('op-mission').value = org.mission || '';
      document.getElementById('op-vision').value = org.vision || '';
      document.getElementById('op-values').value = org.values || '';
      document.getElementById('op-history').value = org.history || '';
    } catch (e) {
      toastError(e.message);
    }
  }

  async function save() {
    const btn = document.getElementById('btn-save-org-profile');
    setLoading(btn, true);
    try {
      await api.patch('/orgs/me', {
        name: document.getElementById('op-name').value.trim(),
        name_en: document.getElementById('op-name-en').value.trim() || null,
        website: document.getElementById('op-website').value.trim() || null,
        phone: document.getElementById('op-phone').value.trim() || null,
        address: document.getElementById('op-address').value.trim() || null,
        description: document.getElementById('op-desc').value.trim() || null,
        mission: document.getElementById('op-mission').value.trim() || null,
        vision: document.getElementById('op-vision').value.trim() || null,
        values: document.getElementById('op-values').value.trim() || null,
        history: document.getElementById('op-history').value.trim() || null,
      });
      toastSuccess('پروفایل سازمان به‌روزرسانی شد');
    } catch (e) {
      toastError(e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  return { load, save };
})();
