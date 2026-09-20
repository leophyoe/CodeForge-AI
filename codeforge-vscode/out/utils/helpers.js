"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.truncate = truncate;
exports.extractCodeBlock = extractCodeBlock;
exports.formatModelId = formatModelId;
exports.sanitizeUrl = sanitizeUrl;
exports.isLocalhost = isLocalhost;
function truncate(text, maxChars) {
    if (text.length <= maxChars) {
        return text;
    }
    return text.slice(0, maxChars) + "\n... [truncated]";
}
function extractCodeBlock(text) {
    const match = text.match(/```(?:\w+)?\n([\s\S]*?)```/);
    return match?.[1] ?? null;
}
function formatModelId(id) {
    return id.replace(/^.*[/\\]/, "").replace(/\.(gguf|bin|safetensors)$/, "");
}
function sanitizeUrl(url) {
    try {
        const parsed = new URL(url);
        return parsed.toString();
    }
    catch {
        return "";
    }
}
function isLocalhost(url) {
    try {
        const parsed = new URL(url);
        return (parsed.hostname === "localhost" ||
            parsed.hostname === "127.0.0.1" ||
            parsed.hostname === "::1" ||
            parsed.hostname === "[::1]");
    }
    catch {
        return false;
    }
}
//# sourceMappingURL=helpers.js.map