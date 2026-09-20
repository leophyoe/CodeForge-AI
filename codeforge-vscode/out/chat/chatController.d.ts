import * as vscode from "vscode";
import type { CodeForgeApiClient } from "../api/client.js";
export declare class ChatController implements vscode.WebviewViewProvider {
    private extensionUri;
    private client;
    private outputChannel;
    static readonly viewType = "codeforge.chatView";
    private view?;
    private conversation;
    private currentAbort?;
    constructor(extensionUri: vscode.Uri, client: CodeForgeApiClient, outputChannel: {
        log: (m: string) => void;
        error: (m: string, e?: unknown) => void;
    });
    resolveWebviewView(webviewView: vscode.WebviewView, _context: vscode.WebviewViewResolveContext, _token: vscode.CancellationToken): void;
    handleUserMessage(text: string): Promise<void>;
    cancelGeneration(): void;
    clearConversation(): void;
    private appendUserMessage;
    private startAssistantMessage;
    private appendToken;
    private finishAssistantMessage;
    private appendAssistantMessage;
    private appendErrorMessage;
    private setLoading;
    private getHtml;
}
//# sourceMappingURL=chatController.d.ts.map