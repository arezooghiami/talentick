// ════════════════════════════════════════════════════════════════════
// Talentick — فراموشی رمز عبور
// ════════════════════════════════════════════════════════════════════
// نکته: بک‌اند فعلی endpoint عمومیِ «ارسال کد تایید با شماره موبایل» ندارد
// (طبق دستورکار این مرحله، بک‌اند دست‌نخورده می‌ماند). این صفحه از نظر UI/UX
// کامل است و آماده‌ی اتصال به API واقعی در آینده — فعلاً حالت موفقیت را
// به‌صورت نمایشی نشان می‌دهد.

document.getElementById('fpScene').innerHTML = TalentickArt.phoneOtp();

const fpForm = document.getElementById('fpForm');
const fpPhone = document.getElementById('fpPhone');
const btnSend = document.getElementById('btnSendCode');
const fpError = document.getElementById('fpError');
const fpErrorText = document.getElementById('fpErrorText');
const fpSuccess = document.getElementById('fpSuccess');

const PHONE_RE = /^0?9\d{9}$/;

fpForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  fpError.classList.remove('show');
  fpSuccess.classList.remove('show');
  fpPhone.classList.remove('error');

  const phone = fpPhone.value.trim();
  if (!PHONE_RE.test(phone)) {
    fpErrorText.textContent = 'شماره موبایل معتبر وارد کنید (مثال: 09xxxxxxxxx)';
    fpError.classList.add('show');
    fpPhone.classList.add('error');
    return;
  }

  btnSend.disabled = true;
  btnSend.classList.add('loading');
  await new Promise(r => setTimeout(r, 700));
  btnSend.disabled = false;
  btnSend.classList.remove('loading');

  fpSuccess.classList.add('show');
  btnSend.querySelector('.ds-btn-text').textContent = 'ارسال مجدد کد';
});
