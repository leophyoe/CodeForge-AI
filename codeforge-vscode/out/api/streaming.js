"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SSEStreamReader = void 0;
exports.createSSEStream = createSSEStream;
class SSEStreamReader {
    reader;
    buffer = "";
    constructor(reader) {
        this.reader = reader;
    }
    async *events() {
        let eventType = "";
        let eventData = "";
        while (true) {
            const { done, value } = await this.reader.read();
            if (done) {
                break;
            }
            this.buffer += new TextDecoder().decode(value);
            const lines = this.buffer.split("\n");
            this.buffer = lines.pop() ?? "";
            for (const line of lines) {
                if (line.startsWith("event: ")) {
                    eventType = line.slice(7).trim();
                }
                else if (line.startsWith("data: ")) {
                    eventData = line.slice(6);
                }
                else if (line === "" && eventData) {
                    const event = this.parseEvent(eventType, eventData);
                    if (event) {
                        yield event;
                    }
                    eventType = "";
                    eventData = "";
                }
            }
        }
        if (eventData) {
            const event = this.parseEvent(eventType, eventData);
            if (event) {
                yield event;
            }
        }
    }
    parseEvent(type, data) {
        if (data === "[DONE]") {
            return { type: "end", done: true };
        }
        try {
            const parsed = JSON.parse(data);
            if (parsed.error) {
                return { type: "error", error: String(parsed.error) };
            }
            const token = parsed.token ?? parsed.text ?? parsed.content;
            if (typeof token === "string") {
                return { type: "token", token };
            }
            const choices = parsed.choices;
            if (choices && choices.length > 0) {
                const choice = choices[0];
                const delta = choice.delta;
                const content = delta?.content ?? choice.text;
                if (typeof content === "string") {
                    return { type: "token", token: content };
                }
            }
            return null;
        }
        catch {
            if (type === "token" || type === "data") {
                return { type: "token", token: data };
            }
            return null;
        }
    }
}
exports.SSEStreamReader = SSEStreamReader;
function createSSEStream(response) {
    if (!response.body) {
        throw new Error("Response body is null");
    }
    return new SSEStreamReader(response.body.getReader());
}
//# sourceMappingURL=streaming.js.map