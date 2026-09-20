import * as vscode from "vscode";
import type { CodeForgeApiClient } from "../api/client.js";
export declare class CompletionProvider implements vscode.InlineCompletionItemProvider {
    private client;
    private debounceTimer?;
    private currentAbort?;
    constructor(client: CodeForgeApiClient);
    provideInlineCompletionItems(document: vscode.TextDocument, position: vscode.Position, _context: vscode.InlineCompletionContext, token: vscode.CancellationToken): vscode.ProviderResult<vscode.InlineCompletionItem[] | vscode.InlineCompletionList>;
    private fetchCompletion;
    private getPrefix;
    private getSuffix;
    dispose(): void;
}
//# sourceMappingURL=completionProvider.d.ts.map