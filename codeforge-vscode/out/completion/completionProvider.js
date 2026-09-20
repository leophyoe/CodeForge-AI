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
exports.CompletionProvider = void 0;
const vscode = __importStar(require("vscode"));
const errors_js_1 = require("../api/errors.js");
class CompletionProvider {
    client;
    debounceTimer;
    currentAbort;
    constructor(client) {
        this.client = client;
    }
    provideInlineCompletionItems(document, position, _context, token) {
        const config = vscode.workspace.getConfiguration("codeforge");
        const maxPrefix = config.get("completion.maxPrefixChars", 2000);
        const maxSuffix = config.get("completion.maxSuffixChars", 500);
        const maxTokens = config.get("completion.maxTokens", 256);
        const model = config.get("model", "");
        if (!model) {
            return [];
        }
        const prefix = this.getPrefix(document, position, maxPrefix);
        const suffix = this.getSuffix(document, position, maxSuffix);
        if (!prefix.trim()) {
            return [];
        }
        this.currentAbort?.abort();
        this.currentAbort = new AbortController();
        return new Promise((resolve) => {
            if (token.isCancellationRequested) {
                resolve([]);
                return;
            }
            token.onCancellationRequested(() => {
                this.currentAbort?.abort();
                resolve([]);
            });
            this.fetchCompletion(prefix, suffix, model, maxTokens, document, position)
                .then((items) => {
                if (!token.isCancellationRequested) {
                    resolve(items);
                }
            })
                .catch(() => {
                if (!token.isCancellationRequested) {
                    resolve([]);
                }
            });
        });
    }
    async fetchCompletion(prefix, suffix, model, maxTokens, document, position) {
        try {
            const response = await this.client.complete({
                model,
                prompt: prefix,
                config: {
                    max_tokens: maxTokens,
                    temperature: 0.2,
                    stop_sequences: ["\n\n", "\r\n\r\n"],
                },
                stream: false,
            });
            const text = response.choices[0]?.text;
            if (!text) {
                return [];
            }
            const cleaned = text.replace(/^\s+/, "");
            if (!cleaned) {
                return [];
            }
            return [
                new vscode.InlineCompletionItem(cleaned, new vscode.Range(position, position)),
            ];
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError && err.statusCode === 401) {
                vscode.window.showWarningMessage("CodeForge: Authentication failed. Check your API key.");
            }
            return [];
        }
    }
    getPrefix(document, position, maxChars) {
        const fullText = document.getText();
        const offset = document.offsetAt(position);
        const start = Math.max(0, offset - maxChars);
        return fullText.slice(start, offset);
    }
    getSuffix(document, position, maxChars) {
        const fullText = document.getText();
        const offset = document.offsetAt(position);
        return fullText.slice(offset, Math.min(fullText.length, offset + maxChars));
    }
    dispose() {
        this.currentAbort?.abort();
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
    }
}
exports.CompletionProvider = CompletionProvider;
//# sourceMappingURL=completionProvider.js.map