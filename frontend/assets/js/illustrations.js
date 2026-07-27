// ════════════════════════════════════════════════════════════════════
// Talentick — Illustration Library (SVG)
// ════════════════════════════════════════════════════════════════════
// کاراکترها و illustrationهای اختصاصی برند — سبک flat-gradient دوستانه،
// هماهنگ با پالت بنفش Talentick. یک منبع واحد برای همه‌ی صفحات
// (Welcome، Login، Forget Password، Dashboard) تا Design Language
// یکسان بماند.

const TalentickArt = (() => {
  const DEFS = `
    <defs>
      <linearGradient id="tk-skin" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#FFD8B8"/><stop offset="1" stop-color="#F4B98A"/>
      </linearGradient>
      <linearGradient id="tk-hoodie" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#8B5CF6"/><stop offset="1" stop-color="#5636D6"/>
      </linearGradient>
      <linearGradient id="tk-hoodie-2" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#A855F7"/><stop offset="1" stop-color="#6C4CF1"/>
      </linearGradient>
      <linearGradient id="tk-hair" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#3B2A22"/><stop offset="1" stop-color="#1F150F"/>
      </linearGradient>
      <linearGradient id="tk-device" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#F5F3FF"/><stop offset="1" stop-color="#E4DDFB"/>
      </linearGradient>
      <linearGradient id="tk-gold" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#FFDE7A"/><stop offset="1" stop-color="#F5B400"/>
      </linearGradient>
      <radialGradient id="tk-glow" cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stop-color="#fff" stop-opacity=".28"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
      </radialGradient>
      <filter id="tk-shadow" x="-40%" y="-20%" width="180%" height="160%">
        <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#2E1065" flood-opacity=".22"/>
      </filter>
    </defs>`;

  /** یک نشان شناور دایره‌ای با آیکون داخلش — برای صحنه‌های شخصیت */
  function chip(cx, cy, r, fill, icon) {
    return `
      <g filter="url(#tk-shadow)">
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}"/>
      </g>
      <g transform="translate(${cx - r * 0.5}, ${cy - r * 0.5})" fill="#fff">${icon}</g>`;
  }

  const ICONS = {
    play: `<path d="M2 1.5 L11 6 L2 10.5 Z"/>`,
    book: `<rect x="0" y="0" width="11" height="11" rx="1.6"/>`,
    trophy: `<path d="M2 0h7v3a3.5 3.5 0 0 1-7 0V0z"/><path d="M4 6.5h3v2H4z"/><path d="M2.5 8.5h6v1.5h-6z"/><path d="M0 1h2v2a2 2 0 0 1-2-2z"/><path d="M11 1H9v2a2 2 0 0 0 2-2z"/>`,
    rocket: `<path d="M5.5 0C7 1 8 3 8 5.5c0 1-.3 2-.8 2.8L5.5 11 4.3 8.3C3.8 7.5 3.5 6.5 3.5 5.5 3.5 3 4.5 1 5.5 0z"/><circle cx="5.5" cy="5" r="1.1" fill="#6C4CF1"/>`,
    chart: `<path d="M0 9h1.6V5.5H0V9zm3.2 0h1.6V2H3.2v7zm3.2 0H8V6.8H6.4V9zm3.2 0h1.6V0H9.6v9z"/>`,
    chat: `<path d="M0 1a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4l-3 3V7H1a1 1 0 0 1-1-1V1z"/>`,
    star: `<path d="M5.5 0l1.4 3.4L10.6 4l-2.6 2.4L8.6 10 5.5 8 2.4 10l.6-3.6L.4 4l3.7-.6z"/>`,
    laptop: `<path d="M0 9V1.5A.5.5 0 01.5 1h10a.5.5 0 01.5.5V9M0 9h11l.8 1.4a.4.4 0 01-.35.6H.55a.4.4 0 01-.35-.6L0 9z"/>`,
    tablet: `<rect x="1.5" y="0" width="8" height="11" rx="1.4"/>`,
  };

  /** بست کاراکتر (سر + شانه) — بدون بازو، برای جلوگیری از خطای اتصال اندام */
  function bust(bodyGrad, headCy = 148) {
    return `
      <path d="M92 322 C88 246 110 202 160 198 C210 202 232 246 228 322 Z" fill="${bodyGrad}"/>
      <path d="M136 206 h48 l9 24 h-66 z" fill="#4C2F9E" opacity=".6"/>
      <circle cx="160" cy="${headCy - 2}" r="44" fill="url(#tk-hair)"/>
      <circle cx="160" cy="${headCy}" r="40" fill="url(#tk-skin)"/>
      <circle cx="145" cy="${headCy + 4}" r="4.2" fill="#2A1B12"/>
      <circle cx="177" cy="${headCy + 4}" r="4.2" fill="#2A1B12"/>
      <path d="M150 ${headCy + 18} Q160 ${headCy + 26} 170 ${headCy + 18}" stroke="#B9754A" stroke-width="3.2" stroke-linecap="round" fill="none"/>`;
  }

  /** نشان فعالیت — گوشه‌ی پایین شخصیت، نمایانگر لپ‌تاپ/تبلت/موشک بدون نیاز به ترسیم دست */
  function activityBadge(cx, cy, r, fill, icon) {
    return `
      <g filter="url(#tk-shadow)"><circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#fff" stroke-width="4"/></g>
      <g transform="translate(${cx - r * 0.42}, ${cy - r * 0.42}) scale(${r * 0.076})" fill="#fff">${icon}</g>`;
  }

  /** اسلاید ۱ — دانش‌آموز و لپ‌تاپ (یادگیری آسان و جذاب) */
  function characterLaptop() {
    return `<svg viewBox="0 0 320 340" fill="none" xmlns="http://www.w3.org/2000/svg" class="tk-illustration">
      ${DEFS}
      <circle cx="160" cy="160" r="132" fill="url(#tk-glow)"/>
      <ellipse cx="160" cy="322" rx="108" ry="16" fill="#000" opacity=".12"/>
      ${chip(48, 76, 25, 'url(#tk-gold)', ICONS.play)}
      ${chip(266, 66, 23, 'url(#tk-hoodie-2)', ICONS.book)}
      <g filter="url(#tk-shadow)">${bust('url(#tk-hoodie)')}</g>
      ${activityBadge(238, 258, 44, '#2E1065', ICONS.laptop)}
    </svg>`;
  }

  /** اسلاید ۲ — دانش‌آموز و جام‌های افتخار (رقابت سالم و پیشرفت) */
  function characterTrophy() {
    return `<svg viewBox="0 0 320 340" fill="none" xmlns="http://www.w3.org/2000/svg" class="tk-illustration">
      ${DEFS}
      <circle cx="160" cy="160" r="132" fill="url(#tk-glow)"/>
      <ellipse cx="160" cy="322" rx="108" ry="16" fill="#000" opacity=".12"/>
      ${chip(52, 70, 24, 'url(#tk-gold)', ICONS.trophy)}
      ${chip(266, 58, 22, 'url(#tk-hoodie-2)', ICONS.star)}
      <g filter="url(#tk-shadow)">${bust('url(#tk-hoodie-2)')}</g>
      ${activityBadge(238, 258, 44, '#2E1065', ICONS.tablet)}
    </svg>`;
  }

  /** اسلاید ۳ — دانش‌آموز با کوله‌پشتی و موشک (فرصت‌های بیشتر) */
  function characterRocket() {
    return `<svg viewBox="0 0 320 340" fill="none" xmlns="http://www.w3.org/2000/svg" class="tk-illustration">
      ${DEFS}
      <circle cx="160" cy="160" r="132" fill="url(#tk-glow)"/>
      <ellipse cx="160" cy="322" rx="108" ry="16" fill="#000" opacity=".12"/>
      ${chip(52, 78, 22, 'url(#tk-hoodie-2)', ICONS.chart)}
      <g filter="url(#tk-shadow)">
        <rect x="72" y="206" width="42" height="80" rx="15" fill="#4C2F9E"/>
        <rect x="81" y="215" width="24" height="13" rx="5" fill="#3A2178"/>
        ${bust('url(#tk-hoodie)')}
      </g>
      ${activityBadge(240, 250, 46, 'url(#tk-gold)', ICONS.rocket)}
    </svg>`;
  }

  /** illustration صفحه فراموشی رمز — موبایل با حباب پیام */
  function phoneOtp() {
    return `<svg viewBox="0 0 220 220" fill="none" xmlns="http://www.w3.org/2000/svg" class="tk-illustration">
      <defs>
        <linearGradient id="fp-phone" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#8B5CF6"/><stop offset="1" stop-color="#5636D6"/>
        </linearGradient>
        <linearGradient id="fp-bubble1" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#F5B400"/><stop offset="1" stop-color="#FFDE7A"/>
        </linearGradient>
        <linearGradient id="fp-bubble2" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#A855F7"/><stop offset="1" stop-color="#6C4CF1"/>
        </linearGradient>
        <radialGradient id="fp-glow" cx="0.5" cy="0.42" r="0.6">
          <stop offset="0" stop-color="#8B5CF6" stop-opacity=".14"/><stop offset="1" stop-color="#8B5CF6" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <circle cx="110" cy="100" r="100" fill="url(#fp-glow)"/>
      <rect x="70" y="38" width="80" height="150" rx="20" fill="url(#fp-phone)"/>
      <rect x="80" y="54" width="60" height="104" rx="6" fill="#fff" opacity=".14"/>
      <rect x="94" y="170" width="32" height="5" rx="2.5" fill="#fff" opacity=".5"/>
      <g>
        <rect x="118" y="56" width="66" height="40" rx="14" fill="url(#fp-bubble1)"/>
        <path d="M132 96 l10 14 6-14z" fill="url(#fp-bubble1)"/>
        <circle cx="136" cy="76" r="3.4" fill="#fff" opacity=".85"/>
        <circle cx="150" cy="76" r="3.4" fill="#fff" opacity=".85"/>
        <circle cx="164" cy="76" r="3.4" fill="#fff" opacity=".85"/>
      </g>
      <g>
        <rect x="30" y="108" width="58" height="36" rx="13" fill="url(#fp-bubble2)"/>
        <path d="M76 144 l-4 12-9-12z" fill="url(#fp-bubble2)"/>
        <rect x="42" y="122" width="34" height="4.5" rx="2.2" fill="#fff" opacity=".8"/>
        <rect x="42" y="130" width="22" height="4.5" rx="2.2" fill="#fff" opacity=".6"/>
      </g>
    </svg>`;
  }

  /** بنر هیرو داشبورد — کاراکتر با المان‌های شناور UI (چالش برنامه‌نویسی) */
  function heroBanner() {
    return `<svg viewBox="40 40 240 260" fill="none" xmlns="http://www.w3.org/2000/svg" class="tk-illustration">
      ${DEFS}
      ${chip(58, 76, 22, 'url(#tk-gold)', ICONS.chart)}
      ${chip(266, 66, 20, 'url(#tk-hoodie-2)', ICONS.star)}
      <ellipse cx="160" cy="292" rx="98" ry="14" fill="#000" opacity=".14"/>
      <g filter="url(#tk-shadow)">${bust('url(#tk-hoodie-2)')}</g>
      ${activityBadge(236, 254, 42, 'url(#tk-gold)', ICONS.rocket)}
    </svg>`;
  }

  /** لوگوی Talentick — variant: 'dark' (متن مشکی، روی پس‌زمینه‌ی روشن) یا 'light' (متن سفید، روی گرادیان بنفش) */
  function logo(variant = 'dark') {
    const text = variant === 'light' ? '#fff' : '#171321';
    const check = variant === 'light' ? '#FFDE7A' : '#7C4DFF';
    return `<svg viewBox="0 0 178 34" fill="none" xmlns="http://www.w3.org/2000/svg" class="tk-logo" role="img" aria-label="Talentick" style="direction:ltr;">
      <text x="0" y="26" direction="ltr" text-anchor="start" textLength="148" lengthAdjust="spacingAndGlyphs" font-family="'Poppins','Vazirmatn',sans-serif" font-size="27" font-weight="700" fill="${text}">Talentic</text>
      <path d="M155 4 L165 26 L178 2" stroke="${check}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </svg>`;
  }

  /** صحنه‌ی تزئینی «تیم/سازمان» — پشت لوگو در هدر صفحات Login/Forget Password */
  function crowdScene() {
    const person = (x, s, o) => `
      <g transform="translate(${x} 0) scale(${s})" opacity="${o}">
        <circle cx="0" cy="0" r="14" fill="#fff"/>
        <path d="M-20 44 C-20 20 -12 8 0 8 C12 8 20 20 20 44 Z" fill="#fff"/>
      </g>`;
    return `<svg viewBox="0 0 300 70" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMax meet">
      ${person(150, 1.15, .95)}
      ${person(80, .9, .55)}
      ${person(220, .9, .55)}
      ${person(20, .68, .3)}
      ${person(280, .68, .3)}
    </svg>`;
  }

  return { characterLaptop, characterTrophy, characterRocket, phoneOtp, heroBanner, logo, crowdScene };
})();
