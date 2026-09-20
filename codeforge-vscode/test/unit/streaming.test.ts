import * as assert from "assert";
import type { StreamEvent } from "../../src/api/types";
import { SSEStreamReader } from "../../src/api/streaming";

function createMockReader(data: string): ReadableStreamDefaultReader<Uint8Array> {
  const encoder = new TextEncoder();
  const chunks = data.split("\n").map((line) => encoder.encode(line + "\n"));
  let index = 0;

  return {
    read: async () => {
      if (index < chunks.length) {
        return { done: false, value: chunks[index++]! };
      }
      return { done: true, value: undefined };
    },
    cancel: async () => {},
    closed: Promise.resolve(),
    releaseLock: () => {},
  };
}

suite("SSE Streaming", () => {
  test("parses token events", async () => {
    const sseData = 'event: token\ndata: {"token":"hello"}\n\nevent: token\ndata: {"token":" world"}\n\n';
    const reader = new SSEStreamReader(createMockReader(sseData));
    const events: StreamEvent[] = [];

    for await (const event of reader.events()) {
      events.push(event);
    }

    assert.strictEqual(events.length, 2);
    assert.strictEqual(events[0]!.type, "token");
    assert.strictEqual(events[0]!.token, "hello");
    assert.strictEqual(events[1]!.token, " world");
  });

  test("parses done event", async () => {
    const sseData = 'data: [DONE]\n\n';
    const reader = new SSEStreamReader(createMockReader(sseData));
    const events: StreamEvent[] = [];

    for await (const event of reader.events()) {
      events.push(event);
    }

    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0]!.type, "end");
    assert.strictEqual(events[0]!.done, true);
  });

  test("parses error events", async () => {
    const sseData = 'data: {"error":"something went wrong"}\n\n';
    const reader = new SSEStreamReader(createMockReader(sseData));
    const events: StreamEvent[] = [];

    for await (const event of reader.events()) {
      events.push(event);
    }

    assert.strictEqual(events.length, 1);
    assert.strictEqual(events[0]!.type, "error");
    assert.strictEqual(events[0]!.error, "something went wrong");
  });

  test("parses OpenAI format chunks", async () => {
    const sseData =
      'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: {"choices":[{"delta":{"content":" world"}}]}\n\n';
    const reader = new SSEStreamReader(createMockReader(sseData));
    const events: StreamEvent[] = [];

    for await (const event of reader.events()) {
      events.push(event);
    }

    assert.strictEqual(events.length, 2);
    assert.strictEqual(events[0]!.token, "Hello");
    assert.strictEqual(events[1]!.token, " world");
  });

  test("handles mixed events", async () => {
    const sseData =
      'event: token\ndata: {"token":"a"}\n\nevent: token\ndata: {"token":"b"}\n\ndata: [DONE]\n\n';
    const reader = new SSEStreamReader(createMockReader(sseData));
    const events: StreamEvent[] = [];

    for await (const event of reader.events()) {
      events.push(event);
    }

    assert.strictEqual(events.length, 3);
    assert.strictEqual(events[0]!.token, "a");
    assert.strictEqual(events[1]!.token, "b");
    assert.strictEqual(events[2]!.done, true);
  });

  test("handles empty stream", async () => {
    const reader = new SSEStreamReader(createMockReader(""));
    const events: StreamEvent[] = [];

    for await (const event of reader.events()) {
      events.push(event);
    }

    assert.strictEqual(events.length, 0);
  });
});
