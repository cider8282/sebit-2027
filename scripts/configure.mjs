// Run in GitHub Actions; public and private configuration are written separately.
import fs from 'node:fs';
const project = process.env.FIREBASE_PROJECT_ID || '';
const originText = process.env.PAGES_ORIGIN || '';
const secret = process.env.SEBIT_SETUP_KEY || '';
if (!/^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(project)) throw Error('FIREBASE_PROJECT_ID를 확인하세요.');
const origin = new URL(originText);
if (origin.protocol !== 'https:' || origin.origin !== originText || origin.pathname !== '/') {
  throw Error('PAGES_ORIGIN은 경로와 마지막 /를 뺀 HTTPS 주소여야 합니다. 예: https://yourname.github.io');
}
if (!/^[A-Za-z0-9_-]{24,128}$/.test(secret)) throw Error('SEBIT_SETUP_KEY는 영문·숫자·_·-로 만든 24~128자리 비밀 코드여야 합니다.');
const apiBase = `https://asia-northeast3-${project}.cloudfunctions.net/sebit_api`;
fs.writeFileSync('site/config.js', `window.SEBIT_CONFIG = Object.freeze(${JSON.stringify({apiBase})});\n`);
fs.writeFileSync(`functions/.env.${project}`, `SEBIT_ALLOWED_ORIGINS=${origin.origin}\n`, {mode:0o600});
fs.writeFileSync('/tmp/sebit-setup-key.txt', secret, {mode:0o600});
console.log('Public connection settings and private deployment settings prepared.');
