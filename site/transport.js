'use strict';
window.SEBIT_TRANSPORT = Object.freeze({
  async request(path, data, token) {
    const base = (window.SEBIT_CONFIG?.apiBase || '').replace(/\/$/, '');
    if (!base) throw Error('Firebase 연결 주소가 아직 설정되지 않았어요. 배포 안내를 확인해 주세요.');
    const url = new URL(base);
    const local = ['127.0.0.1', 'localhost'].includes(url.hostname);
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) {
      throw Error('Firebase 연결 주소는 HTTPS 주소여야 해요.');
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(base + '/' + encodeURIComponent(path), {
        method: data === undefined ? 'GET' : 'POST',
        mode: 'cors', cache: 'no-store', credentials: 'omit', signal: controller.signal,
        headers: {'Content-Type': 'application/json', ...(token ? {Authorization: 'Bearer ' + token} : {})},
        body: data === undefined ? undefined : JSON.stringify(data)
      });
      let body;
      try { body = await response.json(); }
      catch { throw Error('Firebase 응답을 읽지 못했어요. 배포 주소를 확인해 주세요.'); }
      if (!response.ok) throw Error(body.error || '서버 연결을 확인해 주세요.');
      return body;
    } catch (error) {
      if (error.name === 'AbortError') throw new TypeError('응답을 기다리는 시간이 길어졌어요. 새로고침 후 기록을 확인해 주세요.');
      throw error;
    } finally { clearTimeout(timer); }
  }
});
