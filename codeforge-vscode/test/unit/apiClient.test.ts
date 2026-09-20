import * as assert from "assert";
import { CodeForgeApiClient } from "../../src/api/client";
import { CodeForgeError, ConnectionError, AuthenticationError } from "../../src/api/errors";

suite("API Client", () => {
  let client: CodeForgeApiClient;

  setup(() => {
    client = new CodeForgeApiClient("http://127.0.0.1:8000", 10);
  });

  suite("constructor", () => {
    test("sets server url", () => {
      assert.strictEqual(client.getServerUrl(), "http://127.0.0.1:8000");
    });
  });

  suite("setServerUrl", () => {
    test("updates server url", () => {
      client.setServerUrl("http://192.168.1.100:9000");
      assert.strictEqual(client.getServerUrl(), "http://192.168.1.100:9000");
    });
  });

  suite("request", () => {
    test("throws ConnectionError when server unreachable", async () => {
      try {
        await client.request("GET", "/v1/health");
        assert.fail("Should have thrown");
      } catch (err) {
        assert.ok(err instanceof ConnectionError);
      }
    });
  });

  suite("health", () => {
    test("throws ConnectionError when server unreachable", async () => {
      try {
        await client.health();
        assert.fail("Should have thrown");
      } catch (err) {
        assert.ok(err instanceof ConnectionError);
      }
    });
  });

  suite("getModels", () => {
    test("throws ConnectionError when server unreachable", async () => {
      try {
        await client.getModels();
        assert.fail("Should have thrown");
      } catch (err) {
        assert.ok(err instanceof ConnectionError);
      }
    });
  });

  suite("chat", () => {
    test("throws ConnectionError when server unreachable", async () => {
      try {
        await client.chat({
          model: "test",
          messages: [{ role: "user", content: "hello" }],
        });
        assert.fail("Should have thrown");
      } catch (err) {
        assert.ok(err instanceof ConnectionError);
      }
    });
  });

  suite("setApiKey", () => {
    test("sets api key", () => {
      client.setApiKey("test-key");
      // No error means success - key is internal
    });
  });
});

suite("Error Classes", () => {
  suite("CodeForgeError", () => {
    test("creates error with fields", () => {
      const err = new CodeForgeError("test", 400, "detail", "req-123");
      assert.strictEqual(err.message, "test");
      assert.strictEqual(err.statusCode, 400);
      assert.strictEqual(err.detail, "detail");
      assert.strictEqual(err.requestId, "req-123");
      assert.strictEqual(err.name, "CodeForgeError");
    });

    test("creates error without requestId", () => {
      const err = new CodeForgeError("test", 400, "detail");
      assert.strictEqual(err.requestId, undefined);
    });

    test("fromResponse creates error from body", () => {
      const err = CodeForgeError.fromResponse(422, {
        error: "Validation Error",
        detail: "Field required",
      });
      assert.strictEqual(err.message, "Validation Error");
      assert.strictEqual(err.statusCode, 422);
      assert.strictEqual(err.detail, "Field required");
    });

    test("fromResponse handles null body", () => {
      const err = CodeForgeError.fromResponse(500, null);
      assert.strictEqual(err.statusCode, 500);
      assert.strictEqual(err.message, "HTTP 500");
    });
  });

  suite("AuthenticationError", () => {
    test("creates 401 error", () => {
      const err = new AuthenticationError();
      assert.strictEqual(err.statusCode, 401);
      assert.strictEqual(err.name, "AuthenticationError");
    });
  });

  suite("ConnectionError", () => {
    test("creates connection error", () => {
      const err = new ConnectionError("Cannot connect");
      assert.strictEqual(err.statusCode, 0);
      assert.strictEqual(err.name, "ConnectionError");
    });
  });
});
