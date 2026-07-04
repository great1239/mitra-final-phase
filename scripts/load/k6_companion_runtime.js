import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8090";
const ATTACH_PRODUCTS = (__ENV.ATTACH_PRODUCTS || "true") !== "false";

const uniguruManifest = JSON.parse(
  open("../../contracts/examples/product-uniguru-runtime.json"),
);
const samruddhiManifest = JSON.parse(
  open("../../contracts/examples/product-trade-bot-main.json"),
);

export const options = {
  scenarios: {
    bhiv_runtime_load: {
      executor: "ramping-vus",
      stages: [
        { duration: "30s", target: 5 },
        { duration: "1m", target: 15 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<1500"],
    checks: ["rate>0.98"],
  },
};

function versioned(payload = {}) {
  return {
    schema_version: "1.0.0",
    contract_version: "1.0.0",
    runtime_version: "1.0.0",
    compatibility_version: "mitra-companion-1",
    ...payload,
  };
}

function postJson(path, body) {
  return http.post(`${BASE_URL}${path}`, JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

function attach(manifest) {
  const response = postJson(
    "/api/v1/attachments",
    versioned({ manifest }),
  );
  check(response, {
    [`attached ${manifest.product_id}`]: (item) =>
      item.status === 201 || item.status === 409,
  });
}

function createSession(productId, workspaceId) {
  const response = postJson(
    "/api/v1/sessions",
    versioned({
      actor_id: `k6-${productId}`,
      client_type: "standalone",
      workspace_id: workspaceId,
      product_id: productId,
    }),
  );
  check(response, {
    [`session ${productId}`]: (item) => item.status === 201,
  });
  return response.json("session.session_id");
}

export function setup() {
  const ready = http.get(`${BASE_URL}/ready`);
  check(ready, { "runtime ready": (item) => item.status === 200 });

  if (ATTACH_PRODUCTS) {
    attach(uniguruManifest);
    attach(samruddhiManifest);
  }

  const uniguruSession = createSession(
    uniguruManifest.product_id,
    "k6-uniguru-workspace",
  );
  const samruddhiSession = createSession(
    samruddhiManifest.product_id,
    "k6-samruddhi-workspace",
  );

  const context = http.get(
    `${BASE_URL}/api/v1/sessions/${uniguruSession}/context?scope=session`,
  );
  check(context, {
    "context load succeeds": (item) => item.status === 200,
  });

  return { uniguruSession, samruddhiSession };
}

export default function (sessions) {
  const useUniguru = __ITER % 2 === 0;
  const body = useUniguru
    ? versioned({
        session_id: sessions.uniguruSession,
        intent_id: "uniguru.execute-query",
        payload: {
          query: `k6 curriculum question ${__VU}-${__ITER}`,
          emit_proof: false,
        },
      })
    : versioned({
        session_id: sessions.samruddhiSession,
        intent_id: "tradebot.predict",
        payload: {
          symbols: ["RELIANCE.NS"],
          horizon: "intraday",
          risk_profile: "moderate",
        },
      });

  const response = postJson("/api/v1/intents/dispatch", body);
  check(response, {
    "dispatch completed": (item) => item.status === 200,
    "dispatch has receipt": (item) => Boolean(item.json("dispatch.dispatch_id")),
  });
  sleep(1);
}
