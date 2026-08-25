// Talentick — صفحه‌ی «پروفایل من» — آپلود/حذف عکس پروفایل کاربر لاگین‌شده.

Auth.requireAuth([], { allowGatedPassword: true });

const MAX_AVATAR_MB = 5;

const avatarEl = document.getElementById('pfAvatar');
const spinnerEl = document.getElementById('pfSpinner');
const fileInput = document.getElementById('pfFileInput');
const removeBtn = document.getElementById('pfRemoveBtn');
const actionsDefault = document.getElementById('pfActionsDefault');
const actionsConfirm = document.getElementById('pfActionsConfirm');
const confirmYesBtn = document.getElementById('pfConfirmYes');
const confirmNoBtn = document.getElementById('pfConfirmNo');
const alertEl = document.getElementById('alertError');
const alertText = document.getElementById('alertText');

document.getElementById('backLink').addEventListener('click', (e) => {
  e.preventDefault();
  Auth.redirectByRole();
});

let currentAvatarUrl = null;

function renderProfileAvatar(url, fullName) {
  currentAvatarUrl = url || null;
  renderAvatar(avatarEl, url, fullName);
  removeBtn.disabled = !url;
}

function showError(msg) {
  alertText.textContent = msg;
  alertEl.classList.add('show');
}
function clearError() {
  alertEl.classList.remove('show');
}
function setBusy(busy) {
  spinnerEl.classList.toggle('show', busy);
  fileInput.disabled = busy;
  removeBtn.disabled = busy || !currentAvatarUrl;
}

async function load() {
  const cached = Auth.getUser();
  if (cached) {
    document.getElementById('pfFullName').textContent = cached.full_name || '—';
    renderProfileAvatar(cached.avatar_url, cached.full_name);
  }
  try {
    const me = await api.get('/auth/me');
    Auth.updateCachedUser({ avatar_url: me.avatar_url, full_name: me.full_name });
    document.getElementById('pfFullName').textContent = me.full_name || '—';
    document.getElementById('pfPhone').textContent = me.phone || '—';
    renderProfileAvatar(me.avatar_url, me.full_name);
  } catch (e) {
    showError(e.message || 'خطا در بارگذاری پروفایل');
  }
}

fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  clearError();

  if (!file.type.startsWith('image/')) {
    showError('فایل انتخاب‌شده باید تصویر باشد');
    fileInput.value = '';
    return;
  }
  if (file.size > MAX_AVATAR_MB * 1024 * 1024) {
    showError(`حجم تصویر نباید بیش از ${MAX_AVATAR_MB} مگابایت باشد`);
    fileInput.value = '';
    return;
  }

  setBusy(true);
  try {
    const me = await api.upload('/auth/me/avatar', file);
    Auth.updateCachedUser({ avatar_url: me.avatar_url });
    renderProfileAvatar(me.avatar_url, me.full_name);
    toastSuccess('عکس پروفایل با موفقیت به‌روزرسانی شد');
  } catch (e) {
    showError(e.message || 'خطا در آپلود عکس پروفایل');
  } finally {
    setBusy(false);
    fileInput.value = '';
  }
});

removeBtn.addEventListener('click', () => {
  if (!currentAvatarUrl) return;
  actionsDefault.classList.add('hidden');
  actionsConfirm.classList.remove('hidden');
});

confirmNoBtn.addEventListener('click', () => {
  actionsConfirm.classList.add('hidden');
  actionsDefault.classList.remove('hidden');
});

confirmYesBtn.addEventListener('click', async () => {
  actionsConfirm.classList.add('hidden');
  actionsDefault.classList.remove('hidden');
  setBusy(true);
  try {
    const me = await api.delete('/auth/me/avatar');
    Auth.updateCachedUser({ avatar_url: me.avatar_url });
    renderProfileAvatar(me.avatar_url, me.full_name);
    toastSuccess('عکس پروفایل حذف شد');
  } catch (e) {
    showError(e.message || 'خطا در حذف عکس پروفایل');
  } finally {
    setBusy(false);
  }
});

load();
