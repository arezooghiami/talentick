// Talentick — API Client
// اگر access_token منقضی شود (401)، یک‌بار به‌صورت خودکار با refresh_token
// تمدید و درخواست اصلی دوباره تلاش می‌شود — کاربر معمولاً چیزی متوجه نمی‌شود.
// اگر تمدید هم شکست بخورد (refresh_token هم منقضی/باطل است)، به لاگین می‌رود.

const api = {
  async _fetch(method, path, body = null, _isRetry = false) {
    const token = Auth.getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(CONFIG.API_BASE + path, opts);

    if (res.status === 401 && !_isRetry) {
      const refreshed = await Auth.refreshSession();
      if (refreshed) {
        return this._fetch(method, path, body, true);
      }
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
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

  /**
   * آپلود فایل (multipart/form-data) — برای تصویر/ویدیو/فایل محتوا.
   * onProgress(percent:0-100) اختیاری است — فقط با XMLHttpRequest ممکن است
   * (fetch در همه‌ی مرورگرها پیشرفت آپلود بدنه‌ی درخواست را گزارش نمی‌دهد)،
   * برای همین این متد به‌جای fetch از XHR استفاده می‌کند.
   */
  async upload(path, file, onProgress = null, _isRetry = false) {
    const token = Auth.getToken();
    const formData = new FormData();
    formData.append('file', file);

    const { status, data } = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', CONFIG.API_BASE + path);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
        };
      }
      xhr.onload = () => {
        let parsed = null;
        try { parsed = JSON.parse(xhr.responseText); } catch { /* بدنه‌ی غیر JSON */ }
        resolve({ status: xhr.status, data: parsed });
      };
      xhr.onerror = () => reject(new Error('خطا در ارتباط با سرور'));
      xhr.send(formData);
    });

    if (status === 401 && !_isRetry) {
      const refreshed = await Auth.refreshSession();
      if (refreshed) {
        return this.upload(path, file, onProgress, true);
      }
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }

    if (status < 200 || status >= 300) {
      const msg = data?.detail || `خطا: ${status}`;
      throw new Error(Array.isArray(msg) ? msg[0]?.msg || msg : msg);
    }
    return data;
  },

  /**
   * آپلود مستقیم مرورگر → MinIO با presigned URL (بدون عبور بایت‌های فایل از
   * اپ) — برای فایل/ویدیوی حجیم محتوا (`/contents/upload`). ابتدا از اپ یک
   * presigned PUT URL می‌گیرد، سپس خود فایل را مستقیم با PUT به MinIO
   * می‌فرستد. onProgress(percent:0-100) اختیاری است.
   * خروجی مثل api.upload یک آبجکت با فیلد url (مسیر پایدار داخلی) است.
   */
  async uploadDirect(path, file, onProgress = null, extra = {}) {
    const { upload_url, url } = await this.post(path, { filename: file.name, ...extra });

    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('PUT', upload_url);
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
        };
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new Error(`آپلود ناموفق بود (خطا: ${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error('خطا در ارتباط با فضای ذخیره‌سازی'));
      xhr.send(file);
    });

    return { url, filename: file.name, size: file.size, content_type: file.type };
  },

  /** دانلود فایل باینری (Excel و ...) با هدر احراز هویت — دانلود مستقیم در مرورگر. */
  async download(path, filename, _isRetry = false) {
    const token = Auth.getToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(CONFIG.API_BASE + path, { headers });

    if (res.status === 401 && !_isRetry) {
      const refreshed = await Auth.refreshSession();
      if (refreshed) return this.download(path, filename, true);
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (res.status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      let msg = `خطا: ${res.status}`;
      try { const data = await res.json(); msg = data?.detail || msg; } catch { /* body غیر JSON */ }
      throw new Error(Array.isArray(msg) ? msg[0]?.msg || msg : msg);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
