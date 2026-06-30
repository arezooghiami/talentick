// Talentick — API Client

const api = {
  async _fetch(method, path, body = null) {
    const token = Auth.getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(CONFIG.API_BASE + path, opts);

    if (res.status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }

    let data;
    try { data = await res.json(); } catch { data = null; }

    if (!res.ok) {
      const msg = data?.detail || `خطا: ${res.status}`;
      throw new Error(Array.isArray(msg) ? msg[0]?.msg || msg : msg);
    }
    return data;
  },

  get:    (path)       => api._fetch('GET', path),
  post:   (path, body) => api._fetch('POST', path, body),
  patch:  (path, body) => api._fetch('PATCH', path, body),
  delete: (path)       => api._fetch('DELETE', path),

  /** آپلود فایل (multipart/form-data) — برای تصویر/ویدیو/فایل محتوا. */
  async upload(path, file) {
    const token = Auth.getToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(CONFIG.API_BASE + path, { method: 'POST', headers, body: formData });

    if (res.status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }

    let data;
    try { data = await res.json(); } catch { data = null; }

    if (!res.ok) {
      const msg = data?.detail || `خطا: ${res.status}`;
      throw new Error(Array.isArray(msg) ? msg[0]?.msg || msg : msg);
    }
    return data;
  },
};
