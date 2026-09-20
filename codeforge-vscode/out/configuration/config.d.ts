import * as vscode from "vscode";
export interface CodeForgeConfig {
    serverUrl: string;
    model: string;
    requestTimeout: number;
    enableInlineCompletion: boolean;
    enableChat: boolean;
    enableCodeActions: boolean;
    enableTelemetry: boolean;
    completionDebounceMs: number;
    completionMaxPrefixChars: number;
    completionMaxSuffixChars: number;
    completionMaxTokens: number;
    chatMaxContextChars: number;
    debug: boolean;
}
export declare function getConfig(): CodeForgeConfig;
export declare function onConfigChanged(callback: () => void): vscode.Disposable;
//# sourceMappingURL=config.d.ts.map