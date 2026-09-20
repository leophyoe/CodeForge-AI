import type { ChatRequest, ChatResponse, CompletionRequest, CompletionResponse, HealthResponse, HardwareInfo, RuntimeInfo, SystemInfo, ModelInfo } from "./types.js";
export declare class CodeForgeApiClient {
    private baseUrl;
    private timeoutMs;
    private apiKey;
    constructor(serverUrl: string, timeoutSec: number);
    setServerUrl(url: string): void;
    setTimeout(sec: number): void;
    setApiKey(key: string): void;
    getServerUrl(): string;
    private headers;
    request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T>;
    requestStream(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<ReadableStreamDefaultReader<Uint8Array>>;
    health(): Promise<HealthResponse>;
    ready(): Promise<{
        ready: boolean;
        models_loaded: number;
    }>;
    getModels(): Promise<ModelInfo[]>;
    getModel(id: string): Promise<ModelInfo>;
    loadModel(id: string): Promise<{
        status: string;
    }>;
    unloadModel(id: string): Promise<{
        status: string;
    }>;
    getHardware(): Promise<HardwareInfo>;
    getRuntime(): Promise<RuntimeInfo>;
    getSystem(): Promise<SystemInfo>;
    chat(request: ChatRequest): Promise<ChatResponse>;
    streamChat(request: ChatRequest, signal?: AbortSignal): Promise<ReadableStreamDefaultReader<Uint8Array>>;
    complete(request: CompletionRequest): Promise<CompletionResponse>;
    streamCompletion(request: CompletionRequest, signal?: AbortSignal): Promise<ReadableStreamDefaultReader<Uint8Array>>;
}
//# sourceMappingURL=client.d.ts.map