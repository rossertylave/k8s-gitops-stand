// Ступінчасте зростання інтенсивності запитів для дослідження HPA (E4).
// Профіль: розігрів -> зростання -> плато -> спад; інтенсивності задаються змінними.
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const HOST = __ENV.HOST_HEADER || 'shop-dev.localhost';
const WORK = __ENV.WORK || '1';
const LOW = parseInt(__ENV.RATE_LOW || '5', 10);
const HIGH = parseInt(__ENV.RATE_HIGH || '40', 10);

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-arrival-rate',
      startRate: LOW,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 400,
      stages: [
        { target: LOW, duration: '2m' },   // базовий рівень
        { target: HIGH, duration: '2m' },  // зростання
        { target: HIGH, duration: '6m' },  // плато (реакція HPA)
        { target: LOW, duration: '1m' },   // спад
        { target: LOW, duration: '5m' },   // спостереження scale down
      ],
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
