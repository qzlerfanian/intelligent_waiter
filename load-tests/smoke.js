import http from 'k6/http';
import { check, sleep } from 'k6';
export const options = { stages: [{ duration: '30s', target: 20 }, { duration: '60s', target: 50 }, { duration: '15s', target: 0 }], thresholds: { http_req_failed: ['rate<0.01'], http_req_duration: ['p(95)<500'] } };
const base = __ENV.BASE_URL || 'http://localhost:8000/api/v1';
export default function () { const response = http.get(`${base}/health/`, { headers: { 'X-Request-ID': `k6-${__VU}-${__ITER}` } }); check(response, { healthy: value => value.status === 200, correlation: value => !!value.headers['X-Request-Id'] }); sleep(1); }
