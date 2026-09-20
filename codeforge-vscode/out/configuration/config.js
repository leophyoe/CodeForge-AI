"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.getConfig = getConfig;
exports.onConfigChanged = onConfigChanged;
const vscode = __importStar(require("vscode"));
function getConfig() {
    const cfg = vscode.workspace.getConfiguration("codeforge");
    return {
        serverUrl: cfg.get("server.url", "http://127.0.0.1:8000"),
        model: cfg.get("model", ""),
        requestTimeout: cfg.get("requestTimeout", 60),
        enableInlineCompletion: cfg.get("enableInlineCompletion", true),
        enableChat: cfg.get("enableChat", true),
        enableCodeActions: cfg.get("enableCodeActions", true),
        enableTelemetry: cfg.get("enableTelemetry", false),
        completionDebounceMs: cfg.get("completion.debounceMs", 300),
        completionMaxPrefixChars: cfg.get("completion.maxPrefixChars", 2000),
        completionMaxSuffixChars: cfg.get("completion.maxSuffixChars", 500),
        completionMaxTokens: cfg.get("completion.maxTokens", 256),
        chatMaxContextChars: cfg.get("chat.maxContextChars", 8000),
        debug: cfg.get("debug", false),
    };
}
function onConfigChanged(callback) {
    return vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration("codeforge")) {
            callback();
        }
    });
}
//# sourceMappingURL=config.js.map