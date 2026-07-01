import http from "k6/http";
import { check, fail, sleep } from "k6";

const baseUrl = (__ENV.LOAD_TEST_BASE_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);
const maxVirtualUsers = Number(__ENV.LOAD_TEST_MAX_VUS || 20);
const smokeTest = __ENV.LOAD_TEST_SMOKE === "true";

if (!Number.isInteger(maxVirtualUsers) || maxVirtualUsers < 1) {
  throw new Error("LOAD_TEST_MAX_VUS debe ser un entero mayor que cero");
}

export const options = {
  scenarios: {
    admin_dashboard: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: smokeTest
        ? [
            { duration: "2s", target: 1 },
            { duration: "5s", target: 1 },
            { duration: "2s", target: 0 },
          ]
        : [
            {
              duration: "15s",
              target: Math.max(1, Math.ceil(maxVirtualUsers / 4)),
            },
            {
              duration: "30s",
              target: Math.max(1, Math.ceil(maxVirtualUsers / 2)),
            },
            { duration: "45s", target: maxVirtualUsers },
            { duration: "15s", target: 0 },
          ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
    "http_req_duration{endpoint:admin_summary}": ["p(95)<500"],
    "http_req_duration{endpoint:admin_internships}": ["p(95)<800"],
  },
};

function login() {
  const email = __ENV.LOAD_TEST_EMAIL;
  const password = __ENV.LOAD_TEST_PASSWORD;

  if (!email || !password) {
    fail(
      "Defina LOAD_TEST_EMAIL y LOAD_TEST_PASSWORD, o entregue LOAD_TEST_TOKEN",
    );
  }

  const response = http.post(
    `${baseUrl}/auth/login`,
    JSON.stringify({ email, password }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { endpoint: "login_setup" },
    },
  );

  const loginSucceeded = check(response, {
    "login de preparación responde 200": (result) => result.status === 200,
    "login entrega access_token": (result) =>
      typeof result.json("access_token") === "string",
  });

  if (!loginSucceeded) {
    fail(`No fue posible autenticar la cuenta de carga (${response.status})`);
  }

  return response.json("access_token");
}

export function setup() {
  const token = __ENV.LOAD_TEST_TOKEN || login();
  return { token };
}

export default function ({ token }) {
  const headers = { Authorization: `Bearer ${token}` };

  const summary = http.get(`${baseUrl}/admin/summary`, {
    headers,
    tags: { endpoint: "admin_summary" },
  });
  check(summary, {
    "resumen administrativo responde 200": (response) =>
      response.status === 200,
  });

  const internships = http.get(`${baseUrl}/admin/internships`, {
    headers,
    tags: { endpoint: "admin_internships" },
  });
  check(internships, {
    "listado administrativo responde 200": (response) =>
      response.status === 200,
  });

  sleep(1);
}
