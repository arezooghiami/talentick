// Talentick — App Config
const CONFIG = {
  // مسیر نسبی — چون backend (app/main.py) خودِ فرانت را روی همین origin
  // سرو می‌کند (و در production پشت همین Nginx/دامنه است)؛ آدرس مطلق
  // localhost:8000 قبلی باعث می‌شد پشت هر origin دیگری (nginx:80،
  // دامنه واقعی) کار نکند.
  API_BASE: '/api',
  TOKEN_KEY: 'talentick_token',
  REFRESH_TOKEN_KEY: 'talentick_refresh_token',
  USER_KEY: 'talentick_user',
};
