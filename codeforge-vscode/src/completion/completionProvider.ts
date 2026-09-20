import * as vscode from "vscode";
import type { CodeForgeApiClient } from "../api/client.js";
import { CodeForgeError } from "../api/errors.js";
import { getCursorPrefix, getCursorSuffix, getLanguageId, getFilename } from "../context/workspaceContext.js";

export class CompletionProvider implements vscode.InlineCompletionItemProvider {
  private debounceTimer?: ReturnType<typeof setTimeout>;
  private currentAbort?: AbortController;

  constructor(private client: CodeForgeApiClient) {}

  provideInlineCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position,
    _context: vscode.InlineCompletionContext,
    token: vscode.CancellationToken
  ): vscode.ProviderResult<vscode.InlineCompletionItem[] | vscode.InlineCompletionList> {
    const config = vscode.workspace.getConfiguration("codeforge");
    const maxPrefix = config.get<number>("completion.maxPrefixChars", 2000);
    const maxSuffix = config.get<number>("completion.maxSuffixChars", 500);
    const maxTokens = config.get<number>("completion.maxTokens", 256);
    const model = config.get<string>("model", "");

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

  private async fetchCompletion(
    prefix: string,
    suffix: string,
    model: string,
    maxTokens: number,
    document: vscode.TextDocument,
    position: vscode.Position
  ): Promise<vscode.InlineCompletionItem[]> {
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
    } catch (err) {
      if (err instanceof CodeForgeError && err.statusCode === 401) {
        vscode.window.showWarningMessage("CodeForge: Authentication failed. Check your API key.");
      }
      return [];
    }
  }

  private getPrefix(document: vscode.TextDocument, position: vscode.Position, maxChars: number): string {
    const fullText = document.getText();
    const offset = document.offsetAt(position);
    const start = Math.max(0, offset - maxChars);
    return fullText.slice(start, offset);
  }

  private getSuffix(document: vscode.TextDocument, position: vscode.Position, maxChars: number): string {
    const fullText = document.getText();
    const offset = document.offsetAt(position);
    return fullText.slice(offset, Math.min(fullText.length, offset + maxChars));
  }

  dispose(): void {
    this.currentAbort?.abort();
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
  }
}
