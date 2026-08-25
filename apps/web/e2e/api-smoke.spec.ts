import { test, expect } from "@playwright/test";

test.describe("API Health Endpoint Smoke", () => {
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8080";

  test("GET /health returns HTTP 200, valid schema, and generated request ID", async ({
    request,
  }) => {
    const response = await request.get(`${apiBaseUrl}/health`);

    expect(response.status(), "API health check must return HTTP 200").toBe(200);

    // Verify x-request-id header exists
    const headers = response.headers();
    const requestId = headers["x-request-id"];
    expect(requestId, "x-request-id response header must exist").toBeDefined();
    expect(typeof requestId, "x-request-id must be a string").toBe("string");
    expect(requestId.length, "x-request-id must not be empty").toBeGreaterThan(0);

    // Verify schema and content
    const data = await response.json();
    expect(data.status, "status must be 'ok'").toBe("ok");
    expect(data.service, "service must be 'croviq-api'").toBe("croviq-api");
    expect(typeof data.git_sha, "git_sha must exist as string").toBe("string");
    expect(data.git_sha.length, "git_sha must not be empty").toBeGreaterThan(0);
  });

  test("GET /health with custom x-request-id returns matching request ID", async ({ request }) => {
    const customRequestId = "e2e-test-request";
    const response = await request.get(`${apiBaseUrl}/health`, {
      headers: {
        "x-request-id": customRequestId,
      },
    });

    expect(response.status(), "API health check must return HTTP 200").toBe(200);

    // Verify x-request-id header matches provided request ID
    const headers = response.headers();
    expect(headers["x-request-id"], "x-request-id header must match provided value").toBe(
      customRequestId,
    );

    // Verify schema and content
    const data = await response.json();
    expect(data.status, "status must be 'ok'").toBe("ok");
    expect(data.service, "service must be 'croviq-api'").toBe("croviq-api");
    expect(typeof data.git_sha, "git_sha must exist as string").toBe("string");
    expect(data.git_sha.length, "git_sha must not be empty").toBeGreaterThan(0);
  });
});
