export declare class CodeForgeError extends Error {
    readonly statusCode: number;
    readonly detail: string;
    readonly requestId?: string;
    constructor(message: string, statusCode: number, detail: string, requestId?: string);
    static fromResponse(statusCode: number, body: unknown, requestId?: string): CodeForgeError;
}
export declare class ConnectionError extends CodeForgeError {
    constructor(message: string);
}
export declare class TimeoutError extends CodeForgeError {
    constructor(message: string);
}
export declare class AuthenticationError extends CodeForgeError {
    constructor(message?: string);
}
export declare class ModelNotFoundError extends CodeForgeError {
    constructor(modelId: string);
}
export declare class ModelNotLoadedError extends CodeForgeError {
    constructor(modelId: string);
}
export declare class RateLimitError extends CodeForgeError {
    constructor(message?: string);
}
export declare class ServerError extends CodeForgeError {
    constructor(statusCode: number, message?: string);
}
//# sourceMappingURL=errors.d.ts.map