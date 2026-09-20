"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CodeForgeApiClient = void 0;
const errors_js_1 = require("./errors.js");
class CodeForgeApiClient {
    baseUrl;
    timeoutMs;
    apiKey;
    constructor(serverUrl, timeoutSec) {
        this.baseUrl = serverUrl;
        this.timeoutMs = timeoutSec * 1000;
    }
    setServerUrl(url) {
        this.baseUrl = url;
    }
    setTimeout(sec) {
        this.timeoutMs = sec * 1000;
    }
    setApiKey(key) {
        this.apiKey = key;
    }
    getServerUrl() {
        return this.baseUrl;
    }
    headers() {
        const h = { "Content-Type": "application/json" };
        if (this.apiKey) {
            h["X-API-Key"] = this.apiKey;
        }
        return h;
    }
    async request(method, path, body, signal) {
        const url = `${this.baseUrl}${path}`;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
        if (signal) {
            signal.addEventListener("abort", () => controller.abort());
        }
        try {
            const init = {
                method,
                headers: this.headers(),
                signal: controller.signal,
            };
            if (body !== undefined) {
                init.body = JSON.stringify(body);
            }
            const response = await fetch(url, init);
            if (!response.ok) {
                let errBody;
                try {
                    errBody = await response.json();
                }
                catch {
                    errBody = null;
                }
                if (response.status === 401) {
                    throw new errors_js_1.AuthenticationError();
                }
                throw errors_js_1.CodeForgeError.fromResponse(response.status, errBody);
            }
            return (await response.json());
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError) {
                throw err;
            }
            if (err instanceof DOMException && err.name === "AbortError") {
                throw new errors_js_1.TimeoutError(`Request to ${path} timed out`);
            }
            if (err instanceof TypeError && err.message.includes("fetch")) {
                throw new errors_js_1.ConnectionError(`Cannot connect to ${this.baseUrl}`);
            }
            throw new errors_js_1.ConnectionError(String(err));
        }
        finally {
            clearTimeout(timeout);
        }
    }
    async requestStream(method, path, body, signal) {
        const url = `${this.baseUrl}${path}`;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
        if (signal) {
            signal.addEventListener("abort", () => controller.abort());
        }
        try {
            const init = {
                method,
                headers: this.headers(),
                signal: controller.signal,
            };
            if (body !== undefined) {
                init.body = JSON.stringify(body);
            }
            const response = await fetch(url, init);
            if (!response.ok) {
                let errBody;
                try {
                    errBody = await response.json();
                }
                catch {
                    errBody = null;
                }
                throw errors_js_1.CodeForgeError.fromResponse(response.status, errBody);
            }
            if (!response.body) {
                throw new Error("No response body");
            }
            return response.body.getReader();
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError) {
                throw err;
            }
            if (err instanceof DOMException && err.name === "AbortError") {
                throw new errors_js_1.TimeoutError("Streaming request timed out");
            }
            throw new errors_js_1.ConnectionError(String(err));
        }
        finally {
            clearTimeout(timeout);
        }
    }
    async health() {
        return this.request("GET", "/v1/health");
    }
    async ready() {
        return this.request("GET", "/v1/ready");
    }
    async getModels() {
        const resp = await this.request("GET", "/v1/models");
        return resp.models;
    }
    async getModel(id) {
        return this.request("GET", `/v1/models/${encodeURIComponent(id)}`);
    }
    async loadModel(id) {
        return this.request("POST", `/v1/models/${encodeURIComponent(id)}/load`);
    }
    async unloadModel(id) {
        return this.request("POST", `/v1/models/${encodeURIComponent(id)}/unload`);
    }
    async getHardware() {
        return this.request("GET", "/v1/hardware");
    }
    async getRuntime() {
        return this.request("GET", "/v1/runtime");
    }
    async getSystem() {
        return this.request("GET", "/v1/system");
    }
    async chat(request) {
        return this.request("POST", "/v1/chat", request);
    }
    async streamChat(request, signal) {
        return this.requestStream("POST", "/v1/chat", { ...request, stream: true }, signal);
    }
    async complete(request) {
        return this.request("POST", "/v1/completions", request);
    }
    async streamCompletion(request, signal) {
        return this.requestStream("POST", "/v1/completions", { ...request, stream: true }, signal);
    }
}
exports.CodeForgeApiClient = CodeForgeApiClient;
//# sourceMappingURL=client.js.map