"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ServerError = exports.RateLimitError = exports.ModelNotLoadedError = exports.ModelNotFoundError = exports.AuthenticationError = exports.TimeoutError = exports.ConnectionError = exports.CodeForgeError = void 0;
class CodeForgeError extends Error {
    statusCode;
    detail;
    requestId;
    constructor(message, statusCode, detail, requestId) {
        super(message);
        this.name = "CodeForgeError";
        this.statusCode = statusCode;
        this.detail = detail;
        this.requestId = requestId;
    }
    static fromResponse(statusCode, body, requestId) {
        const err = body;
        const message = err?.error ?? `HTTP ${statusCode}`;
        const detail = err?.detail ?? "Unknown error";
        return new CodeForgeError(message, statusCode, detail, requestId ?? err?.request_id);
    }
}
exports.CodeForgeError = CodeForgeError;
class ConnectionError extends CodeForgeError {
    constructor(message) {
        super(message, 0, "Unable to connect to CodeForge server");
        this.name = "ConnectionError";
    }
}
exports.ConnectionError = ConnectionError;
class TimeoutError extends CodeForgeError {
    constructor(message) {
        super(message, 0, "Request timed out");
        this.name = "TimeoutError";
    }
}
exports.TimeoutError = TimeoutError;
class AuthenticationError extends CodeForgeError {
    constructor(message = "Authentication failed") {
        super(message, 401, "Invalid or missing API key");
        this.name = "AuthenticationError";
    }
}
exports.AuthenticationError = AuthenticationError;
class ModelNotFoundError extends CodeForgeError {
    constructor(modelId) {
        super(`Model not found: ${modelId}`, 404, `Model '${modelId}' does not exist`);
        this.name = "ModelNotFoundError";
    }
}
exports.ModelNotFoundError = ModelNotFoundError;
class ModelNotLoadedError extends CodeForgeError {
    constructor(modelId) {
        super(`Model not loaded: ${modelId}`, 409, `Model '${modelId}' is not loaded`);
        this.name = "ModelNotLoadedError";
    }
}
exports.ModelNotLoadedError = ModelNotLoadedError;
class RateLimitError extends CodeForgeError {
    constructor(message = "Rate limit exceeded") {
        super(message, 429, "Too many requests");
        this.name = "RateLimitError";
    }
}
exports.RateLimitError = RateLimitError;
class ServerError extends CodeForgeError {
    constructor(statusCode, message) {
        super(message ?? `Server error: ${statusCode}`, statusCode, "Internal server error");
        this.name = "ServerError";
    }
}
exports.ServerError = ServerError;
//# sourceMappingURL=errors.js.map