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

export function getConfig(): CodeForgeConfig {
  const cfg = vscode.workspace.getConfiguration("codeforge");
  return {
    serverUrl: cfg.get<string>("server.url", "http://127.0.0.1:8000"),
    model: cfg.get<string>("model", ""),
    requestTimeout: cfg.get<number>("requestTimeout", 60),
    enableInlineCompletion: cfg.get<boolean>("enableInlineCompletion", true),
    enableChat: cfg.get<boolean>("enableChat", true),
    enableCodeActions: cfg.get<boolean>("enableCodeActions", true),
    enableTelemetry: cfg.get<boolean>("enableTelemetry", false),
    completionDebounceMs: cfg.get<number>("completion.debounceMs", 300),
    completionMaxPrefixChars: cfg.get<number>("completion.maxPrefixChars", 2000),
    completionMaxSuffixChars: cfg.get<number>("completion.maxSuffixChars", 500),
    completionMaxTokens: cfg.get<number>("completion.maxTokens", 256),
    chatMaxContextChars: cfg.get<number>("chat.maxContextChars", 8000),
    debug: cfg.get<boolean>("debug", false),
  };
}

export function onConfigChanged(callback: () => void): vscode.Disposable {
  return vscode.workspace.onDidChangeConfiguration((e) => {
    if (e.affectsConfiguration("codeforge")) {
      callback();
    }
  });
}
