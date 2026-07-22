/**
 * Test de charge Argus — k6 (https://k6.io/)
 *
 * Simule un usage SOC réaliste : login, consultation du dashboard, des
 * alertes et des logs, en boucle, avec un nombre croissant d'utilisateurs
 * virtuels concurrents.
 *
 * ATTENTION : ne JAMAIS lancer ce script contre l'instance de production
 * (https://logplus.duckdns.org) sans prévenir au préalable — même une charge
 * modeste peut dégrader la démo en direct ou déclencher les protections
 * anti-bruteforce sur le compte de test. Utiliser une instance de dev/staging
 * dédiée (docker-compose.dev.yml) ou une fenêtre de maintenance annoncée.
 *
 * Usage :
 *   BASE_URL=http://localhost:8000 TEST_EMAIL=... TEST_PASSWORD=... \
 *     k6 run loadtest/k6-script.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const TEST_EMAIL = __ENV.TEST_EMAIL || "loadtest@argus.local";
const TEST_PASSWORD = __ENV.TEST_PASSWORD || "change-me";

export const options = {
  scenarios: {
    ramping_soc_usage: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 10 },
        { duration: "1m", target: 50 },
        { duration: "1m", target: 100 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<800"], // 95% des requêtes sous 800ms
    http_req_failed: ["rate<0.01"], // moins de 1% d'erreurs
  },
};

export default function () {
  // NOTE : ce flux suppose un login direct (pas d'OTP) — à adapter si le
  // compte de test a le 2FA email activé (utiliser un compte de test dédié
  // sans OTP, ou un token JWT pré-généré passé en variable d'env).
  const loginRes = http.post(
    `${BASE_URL}/api/auth/login/`,
    JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(loginRes, { "login OK": (r) => r.status === 200 });

  const token = loginRes.json("data.access") || loginRes.json("access");
  if (!token) {
    sleep(1);
    return;
  }
  const authHeaders = { headers: { Authorization: `Bearer ${token}` } };

  const dashboardRes = http.get(`${BASE_URL}/api/dashboard/summary/`, authHeaders);
  check(dashboardRes, { "dashboard OK": (r) => r.status === 200 });

  const alertsRes = http.get(`${BASE_URL}/api/alerts/?page=1`, authHeaders);
  check(alertsRes, { "alerts OK": (r) => r.status === 200 });

  const logsRes = http.get(`${BASE_URL}/api/logs/?page=1`, authHeaders);
  check(logsRes, { "logs OK": (r) => r.status === 200 });

  sleep(Math.random() * 2 + 1);
}
