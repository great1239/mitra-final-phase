import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8090";
const ATTACH_PRODUCTS = (__ENV.ATTACH_PRODUCTS || "true") !== "false";
const PROFILE = (__ENV.PROFILE || "runtime").toLowerCase();
const MAX_VUS = Math.max(1, Number(__ENV.MAX_VUS || "15"));
const RAMP_VUS = Math.max(1, Math.ceil(MAX_VUS / 3));

const echoManifest = JSON.parse(
  open("../../contracts/examples/product-echo.json"),
);
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
        { duration: "30s", target: RAMP_VUS },
        { duration: "1m", target: MAX_VUS },
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

  if (PROFILE === "runtime") {
    if (ATTACH_PRODUCTS) {
      attach(echoManifest);
    }
    return {
      profile: PROFILE,
      echoSession: createSession(
        echoManifest.product_id,
        "k6-runtime-workspace",
      ),
    };
  }

  if (PROFILE !== "bhiv") {
    throw new Error(`Unsupported PROFILE=${PROFILE}; use runtime or bhiv`);
  }

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

  return { profile: PROFILE, uniguruSession, samruddhiSession };
}

export default function (sessions) {
  if (sessions.profile === "runtime") {
    const response = postJson(
      "/api/v1/intents/dispatch",
      versioned({
        session_id: sessions.echoSession,
        product_id: echoManifest.product_id,
        capability_id: "echo-observation",
        intent_id: "echo.repeat",
        payload: {
          message: `k6 runtime load ${__VU}-${__ITER}`,
        },
      }),
    );
    check(response, {
      "dispatch completed": (item) => item.status === 200,
      "dispatch has receipt": (item) =>
        Boolean(item.json("dispatch.dispatch_id")),
      "dispatch output matches input": (item) =>
        item.json("dispatch.response.payload.message") ===
        `k6 runtime load ${__VU}-${__ITER}`,
    });
    sleep(1);
    return;
  }

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
