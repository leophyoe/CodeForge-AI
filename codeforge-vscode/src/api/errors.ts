import type { ApiError } from "./types.js";

export class CodeForgeError extends Error {
  public readonly statusCode: number;
  public readonly detail: string;
  public readonly requestId?: string;

  constructor(message: string, statusCode: number, detail: string, requestId?: string) {
    super(message);
    this.name = "CodeForgeError";
    this.statusCode = statusCode;
    this.detail = detail;
    this.requestId = requestId;
  }

  static fromResponse(statusCode: number, body: unknown, requestId?: string): CodeForgeError {
    const err = body as ApiError;
    const message = err?.error ?? `HTTP ${statusCode}`;
    const detail = err?.detail ?? "Unknown error";
    return new CodeForgeError(message, statusCode, detail, requestId ?? err?.request_id);
  }
}

export class ConnectionError extends CodeForgeError {
  constructor(message: string) {
    super(message, 0, "Unable to connect to CodeForge server");
    this.name = "ConnectionError";
  }
}

export class TimeoutError extends CodeForgeError {
  constructor(message: string) {
    super(message, 0, "Request timed out");
    this.name = "TimeoutError";
  }
}

export class AuthenticationError extends CodeForgeError {
  constructor(message = "Authentication failed") {
    super(message, 401, "Invalid or missing API key");
    this.name = "AuthenticationError";
  }
}

export class ModelNotFoundError extends CodeForgeError {
  constructor(modelId: string) {
    super(`Model not found: ${modelId}`, 404, `Model '${modelId}' does not exist`);
    this.name = "ModelNotFoundError";
  }
}

export class ModelNotLoadedError extends CodeForgeError {
  constructor(modelId: string) {
    super(`Model not loaded: ${modelId}`, 409, `Model '${modelId}' is not loaded`);
    this.name = "ModelNotLoadedError";
  }
}

export class RateLimitError extends CodeForgeError {
  constructor(message = "Rate limit exceeded") {
    super(message, 429, "Too many requests");
    this.name = "RateLimitError";
  }
}

export class ServerError extends CodeForgeError {
  constructor(statusCode: number, message?: string) {
    super(message ?? `Server error: ${statusCode}`, statusCode, "Internal server error");
    this.name = "ServerError";
  }
}
