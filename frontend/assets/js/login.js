// ════════════════════════════════════════════════════════════════════
// Talentick — صفحه‌ی ورود
// ════════════════════════════════════════════════════════════════════

document.getElementById('authLogo').innerHTML = TalentickArt.logo('light');
document.getElementById('authHeroScene').innerHTML = TalentickArt.crowdScene();

if (Auth.isLoggedIn()) {
  Auth.redirectByRole();
}

const form        = document.getElementById('loginForm');
const emailEl     = document.getElementById('email');
const passEl      = document.getElementById('password');
const btnLogin    = document.getElementById('btnLogin');
const alertEl     = document.getElementById('alertError');
const alertText   = document.getElementById('alertText');
const rememberEl  = document.getElementById('rememberMe');

const REMEMBER_KEY = 'talentick_remember_id';
const savedId = localStorage.getItem(REMEMBER_KEY);
if (savedId) { emailEl.value = savedId; rememberEl.checked = true; }

document.getElementById('togglePassword').addEventListener('click', () => {
  passEl.type = passEl.type === 'password' ? 'text' : 'password';
});

document.getElementById('signupHint').addEventListener('click', (e) => {
  e.preventDefault();
  toastInfo('برای دریافت حساب کاربری با مدیر سازمان خود تماس بگیرید');
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  _clearError();

  const email = emailEl.value.trim();
  const password = passEl.value;
  if (!email || !password) {
    _showError('شماره موبایل/ایمیل و رمز عبور را وارد کنید');
    return;
  }

  _setLoading(true);
  try {
    const data = await _loginRequest(email, password);
    if (rememberEl.checked) localStorage.setItem(REMEMBER_KEY, email);
    else localStorage.removeItem(REMEMBER_KEY);
    Auth.setSession(data);
    Auth.redirectByRole();
  } catch (err) {
    _showError(err.message || 'خطا در ارتباط با سرور');
    emailEl.classList.add('error');
    passEl.classList.add('error');
  } finally {
    _setLoading(false);
  }
});

/** POST /api/auth/login — OAuth2 Password Flow (form-urlencoded، نه JSON). */
async function _loginRequest(email, password) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const res = await fetch(`${CONFIG.API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  });
  const body = await res.json().catch(() => null);

  if (!res.ok) {
    if (res.status === 429) throw new Error(body?.detail || 'تعداد تلاش‌های ورود بیش از حد مجاز — کمی صبر کنید');
    throw new Error(body?.detail || 'شماره موبایل/ایمیل یا رمز عبور اشتباه است');
  }
  return body;
}

function _setLoading(loading) {
  btnLogin.disabled = loading;
  btnLogin.classList.toggle('loading', loading);
}
function _showError(msg) {
  alertText.textContent = msg;
  alertEl.classList.add('show');
}
function _clearError() {
  alertEl.classList.remove('show');
  emailEl.classList.remove('error');
  passEl.classList.remove('error');
}
