import * as vscode from "vscode";
import { CodeForgeApiClient } from "./api/client.js";
import { getConfig, onConfigChanged } from "./configuration/config.js";
import { CodeForgeStatusBar, type ConnectionState } from "./status/statusBar.js";
import { CodeForgeOutputChannel } from "./utils/outputChannel.js";
import { ChatController } from "./chat/chatController.js";
import { CompletionProvider } from "./completion/completionProvider.js";
import {
  explainCommand,
  generateCommand,
  fixCommand,
  refactorCommand,
  generateTestsCommand,
} from "./commands/index.js";
import { isLocalhost } from "./utils/helpers.js";

let client: CodeForgeApiClient;
let statusBar: CodeForgeStatusBar;
let outputChannel: CodeForgeOutputChannel;
let chatController: ChatController;
let completionProvider: CompletionProvider;
let healthPollTimer: ReturnType<typeof setInterval> | undefined;

const HEALTH_POLL_MS = 30_000;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  outputChannel = new CodeForgeOutputChannel();
  outputChannel.info("CodeForge AI extension activating");

  const config = getConfig();
  client = new CodeForgeApiClient(config.serverUrl, config.requestTimeout);

  const apiKey = await context.secrets.get("codeforge.apiKey");
  if (apiKey) {
    client.setApiKey(apiKey);
  }

  statusBar = new CodeForgeStatusBar();

  chatController = new ChatController(context.extensionUri, client, outputChannel);
  completionProvider = new CompletionProvider(client);

  registerCommands(context, client, chatController);
  registerProviders(context, completionProvider);
  registerConfigWatcher(context);

  checkConnection(client, statusBar, outputChannel);
  healthPollTimer = setInterval(() => {
    checkConnection(client, statusBar, outputChannel);
  }, HEALTH_POLL_MS);

  context.subscriptions.push(
    statusBar,
    outputChannel,
    { dispose: () => clearInterval(healthPollTimer) }
  );

  outputChannel.info("CodeForge AI extension activated");
}

export function deactivate(): void {
  clearInterval(healthPollTimer);
}

function registerCommands(
  context: vscode.ExtensionContext,
  client: CodeForgeApiClient,
  chatController: ChatController
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("codeforge.openChat", () => {
      vscode.commands.executeCommand("codeforge.chatView.focus");
    }),

    vscode.commands.registerCommand("codeforge.explain", () => explainCommand(client)),
    vscode.commands.registerCommand("codeforge.generate", () => generateCommand(client)),
    vscode.commands.registerCommand("codeforge.fix", () => fixCommand(client)),
    vscode.commands.registerCommand("codeforge.refactor", () => refactorCommand(client)),
    vscode.commands.registerCommand("codeforge.generateTests", () => generateTestsCommand(client)),

    vscode.commands.registerCommand("codeforge.selectModel", () => selectModel(client)),
    vscode.commands.registerCommand("codeforge.checkConnection", () =>
      checkConnection(client, statusBar, outputChannel)
    ),
    vscode.commands.registerCommand("codeforge.serverInfo", () => showServerInfo(client)),

    vscode.commands.registerCommand("codeforge.setApiKey", () => setApiKey(context, client)),
    vscode.commands.registerCommand("codeforge.clearApiKey", () => clearApiKey(context, client))
  );
}

function registerProviders(
  context: vscode.ExtensionContext,
  provider: CompletionProvider
): void {
  const config = getConfig();

  if (config.enableInlineCompletion) {
    context.subscriptions.push(
      vscode.languages.registerInlineCompletionItemProvider(
        { scheme: "file" },
        provider
      )
    );
  }

  if (config.enableChat) {
    context.subscriptions.push(
      vscode.window.registerWebviewViewProvider(ChatController.viewType, chatController, {
        webviewOptions: { retainContextWhenHidden: true },
      })
    );
  }
}

function registerConfigWatcher(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    onConfigChanged(() => {
      const cfg = getConfig();
      client.setServerUrl(cfg.serverUrl);
      client.setTimeout(cfg.requestTimeout);
      outputChannel.debug("Configuration reloaded");
    })
  );
}

async function checkConnection(
  client: CodeForgeApiClient,
  statusBar: CodeForgeStatusBar,
  outputChannel: CodeForgeOutputChannel
): Promise<void> {
  statusBar.setState("connecting");

  try {
    const health = await client.health();
    if (health.status === "ok" || health.status === "healthy") {
      statusBar.setState("connected", `Server v${health.version}`);
      outputChannel.debug(`Connected to server v${health.version}`);
    } else {
      statusBar.setState("error", `Server status: ${health.status}`);
    }
  } catch {
    statusBar.setState("disconnected");
  }
}

async function selectModel(client: CodeForgeApiClient): Promise<void> {
  try {
    const models = await client.getModels();

    if (models.length === 0) {
      vscode.window.showInformationMessage("No models available on the CodeForge server.");
      return;
    }

    const items = models.map((m) => ({
      label: m.name ?? m.id,
      description: m.loaded ? "Loaded" : "Not loaded",
      detail: `ID: ${m.id}`,
      id: m.id,
    }));

    const selected = await vscode.window.showQuickPick(items, {
      placeHolder: "Select a model for CodeForge",
      matchOnDescription: true,
    });

    if (selected) {
      await vscode.workspace.getConfiguration("codeforge").update("model", selected.id, vscode.ConfigurationTarget.Global);
      outputChannel.info(`Model selected: ${selected.id}`);

      if (!selected.description?.includes("Loaded")) {
        const load = await vscode.window.showInformationMessage(
          `Model "${selected.label}" is not loaded. Load it now?`,
          "Load",
          "Later"
        );
        if (load === "Load") {
          statusBar.setState("loading", `Loading ${selected.label}...`);
          try {
            await client.loadModel(selected.id);
            statusBar.setState("connected", `Model: ${selected.label}`);
            vscode.window.showInformationMessage(`CodeForge: Model "${selected.label}" loaded.`);
          } catch (err) {
            statusBar.setState("error", "Failed to load model");
            vscode.window.showErrorMessage(
              `Failed to load model: ${err instanceof Error ? err.message : String(err)}`
            );
          }
        }
      }
    }
  } catch (err) {
    vscode.window.showErrorMessage(
      `Failed to list models: ${err instanceof Error ? err.message : String(err)}`
    );
  }
}

async function showServerInfo(client: CodeForgeApiClient): Promise<void> {
  try {
    const [health, system, runtime, models] = await Promise.allSettled([
      client.health(),
      client.getSystem(),
      client.getRuntime(),
      client.getModels(),
    ]);

    const lines: string[] = ["## CodeForge Server Information", ""];

    if (health.status === "fulfilled") {
      lines.push(`**Status:** ${health.value.status}`);
      lines.push(`**Version:** ${health.value.version}`);
    } else {
      lines.push("**Status:** Unable to connect");
    }

    if (system.status === "fulfilled") {
      lines.push(`**API Version:** ${system.value.api_version}`);
      lines.push(`**Uptime:** ${Math.round(system.value.uptime)}s`);
    }

    if (runtime.status === "fulfilled") {
      lines.push("");
      lines.push("### Runtime");
      lines.push(`**PyTorch:** ${runtime.value.pytorch_installed ? runtime.value.pytorch_version ?? "Installed" : "Not installed"}`);
      lines.push(`**CUDA:** ${runtime.value.cuda_available ? "Available" : "Not available"}`);
      if (runtime.value.device) {
        lines.push(`**Device:** ${runtime.value.device}`);
      }
    }

    if (models.status === "fulfilled") {
      lines.push("");
      lines.push(`### Models (${models.value.length})`);
      for (const m of models.value) {
        const status = m.loaded ? "Loaded" : "Not loaded";
        lines.push(`- **${m.name ?? m.id}** (${status})`);
      }
    }

    const panel = vscode.window.createWebviewPanel(
      "codeforgeServerInfo",
      "CodeForge: Server Information",
      vscode.ViewColumn.One,
      { enableScripts: false }
    );
    panel.webview.html = `<!DOCTYPE html>
<html><head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
  <style>body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:16px;white-space:pre-wrap;}</style>
</head><body>${lines.join("\n").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</body></html>`;
  } catch (err) {
    vscode.window.showErrorMessage(
      `Failed to get server info: ${err instanceof Error ? err.message : String(err)}`
    );
  }
}

async function setApiKey(
  context: vscode.ExtensionContext,
  client: CodeForgeApiClient
): Promise<void> {
  const key = await vscode.window.showInputBox({
    prompt: "Enter your CodeForge API key",
    password: true,
    placeHolder: "API key",
  });

  if (key) {
    await context.secrets.store("codeforge.apiKey", key);
    client.setApiKey(key);
    vscode.window.showInformationMessage("CodeForge: API key saved.");
    outputChannel.info("API key updated");
  }
}

async function clearApiKey(
  context: vscode.ExtensionContext,
  client: CodeForgeApiClient
): Promise<void> {
  await context.secrets.delete("codeforge.apiKey");
  client.setApiKey("");
  vscode.window.showInformationMessage("CodeForge: API key cleared.");
  outputChannel.info("API key cleared");
}
