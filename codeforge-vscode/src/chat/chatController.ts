import * as vscode from "vscode";
import type { CodeForgeApiClient } from "../api/client.js";
import type { ChatMessage, StreamEvent } from "../api/types.js";
import { SSEStreamReader } from "../api/streaming.js";
import { CodeForgeError } from "../api/errors.js";

interface ChatConversation {
  id: string;
  messages: ChatMessage[];
}

export class ChatController implements vscode.WebviewViewProvider {
  public static readonly viewType = "codeforge.chatView";
  private view?: vscode.WebviewView;
  private conversation: ChatConversation = { id: "", messages: [] };
  private currentAbort?: AbortController;

  constructor(
    private extensionUri: vscode.Uri,
    private client: CodeForgeApiClient,
    private outputChannel: { log: (m: string) => void; error: (m: string, e?: unknown) => void }
  ) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this.view = webviewView;

    webviewView.webview.options = {
      enableScripts: false,
      localResourceRoots: [this.extensionUri],
    };

    webviewView.webview.html = this.getHtml();

    webviewView.webview.onDidReceiveMessage(async (message) => {
      if (message.type === "sendMessage") {
        await this.handleUserMessage(message.text);
      } else if (message.type === "cancel") {
        this.cancelGeneration();
      }
    });

    webviewView.onDidDispose(() => {
      this.cancelGeneration();
    });
  }

  async handleUserMessage(text: string): Promise<void> {
    if (!text.trim()) {
      return;
    }

    const config = vscode.workspace.getConfiguration("codeforge");
    const model = config.get<string>("model", "");

    if (!model) {
      this.appendAssistantMessage(
        "No model selected. Use **CodeForge: Select Model** to choose a model first."
      );
      return;
    }

    this.conversation.messages.push({ role: "user", content: text });
    this.appendUserMessage(text);

    const abortController = new AbortController();
    this.currentAbort = abortController;

    try {
      this.setLoading(true);

      const reader = await this.client.streamChat(
        {
          model,
          messages: this.conversation.messages,
          stream: true,
        },
        abortController.signal
      );

      const streamReader = new SSEStreamReader(reader);
      let fullResponse = "";

      this.startAssistantMessage();

      for await (const event of streamReader.events()) {
        if (abortController.signal.aborted) {
          break;
        }

        if (event.type === "token" && event.token) {
          fullResponse += event.token;
          this.appendToken(event.token);
        } else if (event.type === "error") {
          this.appendErrorMessage(event.error ?? "Unknown streaming error");
        } else if (event.type === "end") {
          break;
        }
      }

      this.finishAssistantMessage();
      this.conversation.messages.push({ role: "assistant", content: fullResponse });
    } catch (err) {
      if (abortController.signal.aborted) {
        this.appendErrorMessage("Generation cancelled.");
      } else if (err instanceof CodeForgeError) {
        this.appendErrorMessage(`Error: ${err.message}`);
        this.outputChannel.error("Chat error", err);
      } else {
        this.appendErrorMessage("Failed to connect to CodeForge server.");
        this.outputChannel.error("Chat error", err);
      }
    } finally {
      this.setLoading(false);
      this.currentAbort = undefined;
    }
  }

  cancelGeneration(): void {
    this.currentAbort?.abort();
    this.currentAbort = undefined;
  }

  clearConversation(): void {
    this.conversation = { id: "", messages: [] };
    this.view?.webview.postMessage({ type: "clear" });
  }

  private appendUserMessage(text: string): void {
    this.view?.webview.postMessage({ type: "userMessage", text });
  }

  private startAssistantMessage(): void {
    this.view?.webview.postMessage({ type: "startAssistantMessage" });
  }

  private appendToken(token: string): void {
    this.view?.webview.postMessage({ type: "appendToken", token });
  }

  private finishAssistantMessage(): void {
    this.view?.webview.postMessage({ type: "finishAssistantMessage" });
  }

  private appendAssistantMessage(text: string): void {
    this.view?.webview.postMessage({ type: "assistantMessage", text });
  }

  private appendErrorMessage(text: string): void {
    this.view?.webview.postMessage({ type: "errorMessage", text });
  }

  private setLoading(loading: boolean): void {
    this.view?.webview.postMessage({ type: "setLoading", loading });
  }

  private getHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'unsafe-inline';">
  <title>CodeForge Chat</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      padding: 8px;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    #messages {
      flex: 1;
      overflow-y: auto;
      padding-bottom: 8px;
    }
    .message {
      margin-bottom: 12px;
      padding: 8px 12px;
      border-radius: 6px;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .user {
      background: var(--vscode-editor-inactiveSelectionBackground);
      margin-left: 20px;
    }
    .assistant {
      background: transparent;
    }
    .error {
      background: var(--vscode-inputValidation-errorBackground);
      color: var(--vscode-errorForeground);
      border: 1px solid var(--vscode-inputValidation-errorBorder);
    }
    .role {
      font-size: 0.85em;
      font-weight: bold;
      margin-bottom: 4px;
      opacity: 0.7;
    }
    code {
      font-family: var(--vscode-editor-font-family);
      background: var(--vscode-textCodeBlock-background);
      padding: 1px 4px;
      border-radius: 3px;
    }
    pre {
      background: var(--vscode-textCodeBlock-background);
      padding: 8px;
      border-radius: 4px;
      overflow-x: auto;
      margin: 4px 0;
    }
    pre code {
      background: none;
      padding: 0;
    }
    #input-area {
      display: flex;
      gap: 4px;
      padding-top: 8px;
      border-top: 1px solid var(--vscode-panel-border);
    }
    #input {
      flex: 1;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: 4px;
      padding: 6px 8px;
      font-family: inherit;
      font-size: inherit;
      resize: none;
      min-height: 32px;
      max-height: 120px;
    }
    #input:focus { outline: 1px solid var(--vscode-focusBorder); }
    button {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 4px;
      padding: 6px 12px;
      cursor: pointer;
      font-family: inherit;
    }
    button:hover { background: var(--vscode-button-hoverBackground); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    #cancel-btn {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
  </style>
</head>
<body>
  <div id="messages"></div>
  <div id="input-area">
    <textarea id="input" placeholder="Ask CodeForge..." rows="1"></textarea>
    <button id="send-btn">Send</button>
    <button id="cancel-btn" style="display:none">Cancel</button>
  </div>
  <script>
    const messages = document.getElementById('messages');
    const input = document.getElementById('input');
    const sendBtn = document.getElementById('send-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    let currentDiv = null;

    function scrollToBottom() {
      messages.scrollTop = messages.scrollHeight;
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    function formatContent(text) {
      let html = escapeHtml(text);
      html = html.replace(/\`\`\`(\\w*)\\n([\\s\\S]*?)\`\`\`/g, '<pre><code>$2</code></pre>');
      html = html.replace(/\`\`(.*?)\`\`/g, '<code>$1</code>');
      html = html.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
      return html;
    }

    function appendMessage(role, text, cssClass) {
      const div = document.createElement('div');
      div.className = 'message ' + cssClass;
      div.innerHTML = '<div class="role">' + escapeHtml(role) + '</div><div class="content">' + formatContent(text) + '</div>';
      messages.appendChild(div);
      scrollToBottom();
      return div;
    }

    function setLoading(loading) {
      sendBtn.disabled = loading;
      sendBtn.style.display = loading ? 'none' : '';
      cancelBtn.style.display = loading ? '' : 'none';
      input.disabled = loading;
    }

    window.addEventListener('message', (event) => {
      const msg = event.data;
      switch (msg.type) {
        case 'userMessage':
          appendMessage('You', msg.text, 'user');
          break;
        case 'startAssistantMessage':
          currentDiv = appendMessage('CodeForge', '', 'assistant');
          break;
        case 'appendToken':
          if (currentDiv) {
            const content = currentDiv.querySelector('.content');
            content.innerHTML = formatContent(content.textContent + msg.token);
            scrollToBottom();
          }
          break;
        case 'finishAssistantMessage':
          currentDiv = null;
          break;
        case 'assistantMessage':
          appendMessage('CodeForge', msg.text, 'assistant');
          break;
        case 'errorMessage':
          appendMessage('Error', msg.text, 'error');
          break;
        case 'setLoading':
          setLoading(msg.loading);
          break;
        case 'clear':
          messages.innerHTML = '';
          break;
      }
    });

    sendBtn.addEventListener('click', () => {
      const text = input.value.trim();
      if (text) {
        vscode.postMessage({ type: 'sendMessage', text });
        input.value = '';
        input.style.height = 'auto';
      }
    });

    cancelBtn.addEventListener('click', () => {
      vscode.postMessage({ type: 'cancel' });
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
      }
    });

    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });
  </script>
</body>
</html>`;
  }
}
