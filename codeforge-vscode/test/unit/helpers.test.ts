import * as assert from "assert";
import {
  truncate,
  extractCodeBlock,
  formatModelId,
  isLocalhost,
} from "../src/utils/helpers";

suite("Utility Helpers", () => {
  suite("truncate", () => {
    test("returns text unchanged when under limit", () => {
      assert.strictEqual(truncate("hello", 10), "hello");
    });

    test("truncates when over limit", () => {
      const result = truncate("hello world", 5);
      assert.ok(result.startsWith("hello"));
      assert.ok(result.includes("truncated"));
    });

    test("handles exact limit", () => {
      assert.strictEqual(truncate("hello", 5), "hello");
    });

    test("handles empty string", () => {
      assert.strictEqual(truncate("", 10), "");
    });
  });

  suite("extractCodeBlock", () => {
    test("extracts code from markdown block", () => {
      const input = "Here is code:\n```python\nprint('hello')\n```";
      assert.strictEqual(extractCodeBlock(input), "print('hello')\n");
    });

    test("returns null when no code block", () => {
      assert.strictEqual(extractCodeBlock("no code here"), null);
    });

    test("handles multiple code blocks", () => {
      const input = "```a\nfirst\n```\n```b\nsecond\n```";
      assert.strictEqual(extractCodeBlock(input), "first\n");
    });

    test("handles code block without language", () => {
      const input = "```\ncode\n```";
      assert.strictEqual(extractCodeBlock(input), "code\n");
    });
  });

  suite("formatModelId", () => {
    test("removes path prefix", () => {
      assert.strictEqual(formatModelId("/path/to/model.gguf"), "model");
    });

    test("handles Windows paths", () => {
      assert.strictEqual(formatModelId("C:\\models\\test.bin"), "test");
    });

    test("returns plain id unchanged", () => {
      assert.strictEqual(formatModelId("my-model"), "my-model");
    });

    test("removes safetensors extension", () => {
      assert.strictEqual(formatModelId("model.safetensors"), "model");
    });
  });

  suite("isLocalhost", () => {
    test("detects localhost", () => {
      assert.strictEqual(isLocalhost("http://localhost:8000"), true);
    });

    test("detects 127.0.0.1", () => {
      assert.strictEqual(isLocalhost("http://127.0.0.1:8000"), true);
    });

    test("detects ipv6 loopback", () => {
      assert.strictEqual(isLocalhost("http://[::1]:8000"), true);
    });

    test("rejects remote host", () => {
      assert.strictEqual(isLocalhost("http://192.168.1.100:8000"), false);
    });

    test("rejects invalid url", () => {
      assert.strictEqual(isLocalhost("not-a-url"), false);
    });
  });
});
