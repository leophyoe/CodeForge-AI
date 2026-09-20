import type {
  ChatRequest,
  ChatResponse,
  CompletionRequest,
  CompletionResponse,
  HealthResponse,
  HardwareInfo,
  RuntimeInfo,
  SystemInfo,
  ModelInfo,
} from "./types.js";
import { CodeForgeError, ConnectionError, TimeoutError, AuthenticationError } from "./errors.js";

export class CodeForgeApiClient {
  private baseUrl: string;
  private timeoutMs: number;
  private apiKey: string | undefined;

  constructor(serverUrl: string, timeoutSec: number) {
    this.baseUrl = serverUrl;
    this.timeoutMs = timeoutSec * 1000;
  }

  setServerUrl(url: string): void {
    this.baseUrl = url;
  }

  setTimeout(sec: number): void {
    this.timeoutMs = sec * 1000;
  }

  setApiKey(key: string): void {
    this.apiKey = key;
  }

  getServerUrl(): string {
    return this.baseUrl;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) {
      h["X-API-Key"] = this.apiKey;
    }
    return h;
  }

  async request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    if (signal) {
      signal.addEventListener("abort", () => controller.abort());
    }

    try {
      const init: RequestInit = {
        method,
        headers: this.headers(),
        signal: controller.signal,
      };
      if (body !== undefined) {
        init.body = JSON.stringify(body);
      }

      const response = await fetch(url, init);

      if (!response.ok) {
        let errBody: unknown;
        try {
          errBody = await response.json();
        } catch {
          errBody = null;
        }

        if (response.status === 401) {
          throw new AuthenticationError();
        }
        throw CodeForgeError.fromResponse(response.status, errBody);
      }

      return (await response.json()) as T;
    } catch (err) {
      if (err instanceof CodeForgeError) {
        throw err;
      }
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new TimeoutError(`Request to ${path} timed out`);
      }
      if (err instanceof TypeError && err.message.includes("fetch")) {
        throw new ConnectionError(`Cannot connect to ${this.baseUrl}`);
      }
      throw new ConnectionError(String(err));
    } finally {
      clearTimeout(timeout);
    }
  }

  async requestStream(
    method: string,
    path: string,
    body?: unknown,
    signal?: AbortSignal
  ): Promise<ReadableStreamDefaultReader<Uint8Array>> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    if (signal) {
      signal.addEventListener("abort", () => controller.abort());
    }

    try {
      const init: RequestInit = {
        method,
        headers: this.headers(),
        signal: controller.signal,
      };
      if (body !== undefined) {
        init.body = JSON.stringify(body);
      }

      const response = await fetch(url, init);

      if (!response.ok) {
        let errBody: unknown;
        try {
          errBody = await response.json();
        } catch {
          errBody = null;
        }
        throw CodeForgeError.fromResponse(response.status, errBody);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

      return response.body.getReader();
    } catch (err) {
      if (err instanceof CodeForgeError) {
        throw err;
      }
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new TimeoutError("Streaming request timed out");
      }
      throw new ConnectionError(String(err));
    } finally {
      clearTimeout(timeout);
    }
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/v1/health");
  }

  async ready(): Promise<{ ready: boolean; models_loaded: number }> {
    return this.request("GET", "/v1/ready");
  }

  async getModels(): Promise<ModelInfo[]> {
    const resp = await this.request<{ models: ModelInfo[] }>("GET", "/v1/models");
    return resp.models;
  }

  async getModel(id: string): Promise<ModelInfo> {
    return this.request<ModelInfo>("GET", `/v1/models/${encodeURIComponent(id)}`);
  }

  async loadModel(id: string): Promise<{ status: string }> {
    return this.request<{ status: string }>("POST", `/v1/models/${encodeURIComponent(id)}/load`);
  }

  async unloadModel(id: string): Promise<{ status: string }> {
    return this.request<{ status: string }>("POST", `/v1/models/${encodeURIComponent(id)}/unload`);
  }

  async getHardware(): Promise<HardwareInfo> {
    return this.request<HardwareInfo>("GET", "/v1/hardware");
  }

  async getRuntime(): Promise<RuntimeInfo> {
    return this.request<RuntimeInfo>("GET", "/v1/runtime");
  }

  async getSystem(): Promise<SystemInfo> {
    return this.request<SystemInfo>("GET", "/v1/system");
  }

  async chat(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>("POST", "/v1/chat", request);
  }

  async streamChat(
    request: ChatRequest,
    signal?: AbortSignal
  ): Promise<ReadableStreamDefaultReader<Uint8Array>> {
    return this.requestStream("POST", "/v1/chat", { ...request, stream: true }, signal);
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    return this.request<CompletionResponse>("POST", "/v1/completions", request);
  }

  async streamCompletion(
    request: CompletionRequest,
    signal?: AbortSignal
  ): Promise<ReadableStreamDefaultReader<Uint8Array>> {
    return this.requestStream("POST", "/v1/completions", { ...request, stream: true }, signal);
  }
}
