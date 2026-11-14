// Стале навантаження з постійною інтенсивністю надходження запитів (відкрита модель).
// Використовується в експериментах E2, E5 (доступність під час змін і відмов)
// та E0 (калібрування середнього часу обслуговування).
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const HOST = __ENV.HOST_HEADER || 'shop-dev.localhost';
const WORK = __ENV.WORK || '1';
const RATE = parseInt(__ENV.RATE || '5', 10);
const DURATION = __ENV.DURATION || '2m';

export const options = {
  scenarios: {
    steady: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 20,
      maxVUs: 200,
    },
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const res = http.get(`${BASE_URL}/api/items?work=${WORK}`, {
    headers: { Host: HOST },
    timeout: '10s',
  });
  check(res, { 'status 200': (r) => r.status === 200 });
}
