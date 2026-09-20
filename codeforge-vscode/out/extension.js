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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const client_js_1 = require("./api/client.js");
const config_js_1 = require("./configuration/config.js");
const statusBar_js_1 = require("./status/statusBar.js");
const outputChannel_js_1 = require("./utils/outputChannel.js");
const chatController_js_1 = require("./chat/chatController.js");
const completionProvider_js_1 = require("./completion/completionProvider.js");
const index_js_1 = require("./commands/index.js");
let client;
let statusBar;
let outputChannel;
let chatController;
let completionProvider;
let healthPollTimer;
const HEALTH_POLL_MS = 30_000;
async function activate(context) {
    outputChannel = new outputChannel_js_1.CodeForgeOutputChannel();
    outputChannel.info("CodeForge AI extension activating");
    const config = (0, config_js_1.getConfig)();
    client = new client_js_1.CodeForgeApiClient(config.serverUrl, config.requestTimeout);
    const apiKey = await context.secrets.get("codeforge.apiKey");
    if (apiKey) {
        client.setApiKey(apiKey);
    }
    statusBar = new statusBar_js_1.CodeForgeStatusBar();
    chatController = new chatController_js_1.ChatController(context.extensionUri, client, outputChannel);
    completionProvider = new completionProvider_js_1.CompletionProvider(client);
    registerCommands(context, client, chatController);
    registerProviders(context, completionProvider);
    registerConfigWatcher(context);
    checkConnection(client, statusBar, outputChannel);
    healthPollTimer = setInterval(() => {
        checkConnection(client, statusBar, outputChannel);
    }, HEALTH_POLL_MS);
    context.subscriptions.push(statusBar, outputChannel, { dispose: () => clearInterval(healthPollTimer) });
    outputChannel.info("CodeForge AI extension activated");
}
function deactivate() {
    clearInterval(healthPollTimer);
}
function registerCommands(context, client, chatController) {
    context.subscriptions.push(vscode.commands.registerCommand("codeforge.openChat", () => {
        vscode.commands.executeCommand("codeforge.chatView.focus");
    }), vscode.commands.registerCommand("codeforge.explain", () => (0, index_js_1.explainCommand)(client)), vscode.commands.registerCommand("codeforge.generate", () => (0, index_js_1.generateCommand)(client)), vscode.commands.registerCommand("codeforge.fix", () => (0, index_js_1.fixCommand)(client)), vscode.commands.registerCommand("codeforge.refactor", () => (0, index_js_1.refactorCommand)(client)), vscode.commands.registerCommand("codeforge.generateTests", () => (0, index_js_1.generateTestsCommand)(client)), vscode.commands.registerCommand("codeforge.selectModel", () => selectModel(client)), vscode.commands.registerCommand("codeforge.checkConnection", () => checkConnection(client, statusBar, outputChannel)), vscode.commands.registerCommand("codeforge.serverInfo", () => showServerInfo(client)), vscode.commands.registerCommand("codeforge.setApiKey", () => setApiKey(context, client)), vscode.commands.registerCommand("codeforge.clearApiKey", () => clearApiKey(context, client)));
}
function registerProviders(context, provider) {
    const config = (0, config_js_1.getConfig)();
    if (config.enableInlineCompletion) {
        context.subscriptions.push(vscode.languages.registerInlineCompletionItemProvider({ scheme: "file" }, provider));
    }
    if (config.enableChat) {
        context.subscriptions.push(vscode.window.registerWebviewViewProvider(chatController_js_1.ChatController.viewType, chatController, {
            webviewOptions: { retainContextWhenHidden: true },
        }));
    }
}
function registerConfigWatcher(context) {
    context.subscriptions.push((0, config_js_1.onConfigChanged)(() => {
        const cfg = (0, config_js_1.getConfig)();
        client.setServerUrl(cfg.serverUrl);
        client.setTimeout(cfg.requestTimeout);
        outputChannel.debug("Configuration reloaded");
    }));
}
async function checkConnection(client, statusBar, outputChannel) {
    statusBar.setState("connecting");
    try {
        const health = await client.health();
        if (health.status === "ok" || health.status === "healthy") {
            statusBar.setState("connected", `Server v${health.version}`);
            outputChannel.debug(`Connected to server v${health.version}`);
        }
        else {
            statusBar.setState("error", `Server status: ${health.status}`);
        }
    }
    catch {
        statusBar.setState("disconnected");
    }
}
async function selectModel(client) {
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
                const load = await vscode.window.showInformationMessage(`Model "${selected.label}" is not loaded. Load it now?`, "Load", "Later");
                if (load === "Load") {
                    statusBar.setState("loading", `Loading ${selected.label}...`);
                    try {
                        await client.loadModel(selected.id);
                        statusBar.setState("connected", `Model: ${selected.label}`);
                        vscode.window.showInformationMessage(`CodeForge: Model "${selected.label}" loaded.`);
                    }
                    catch (err) {
                        statusBar.setState("error", "Failed to load model");
                        vscode.window.showErrorMessage(`Failed to load model: ${err instanceof Error ? err.message : String(err)}`);
                    }
                }
            }
        }
    }
    catch (err) {
        vscode.window.showErrorMessage(`Failed to list models: ${err instanceof Error ? err.message : String(err)}`);
    }
}
async function showServerInfo(client) {
    try {
        const [health, system, runtime, models] = await Promise.allSettled([
            client.health(),
            client.getSystem(),
            client.getRuntime(),
            client.getModels(),
        ]);
        const lines = ["## CodeForge Server Information", ""];
        if (health.status === "fulfilled") {
            lines.push(`**Status:** ${health.value.status}`);
            lines.push(`**Version:** ${health.value.version}`);
        }
        else {
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
        const panel = vscode.window.createWebviewPanel("codeforgeServerInfo", "CodeForge: Server Information", vscode.ViewColumn.One, { enableScripts: false });
        panel.webview.html = `<!DOCTYPE html>
<html><head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
  <style>body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:16px;white-space:pre-wrap;}</style>
</head><body>${lines.join("\n").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</body></html>`;
    }
    catch (err) {
        vscode.window.showErrorMessage(`Failed to get server info: ${err instanceof Error ? err.message : String(err)}`);
    }
}
async function setApiKey(context, client) {
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
async function clearApiKey(context, client) {
    await context.secrets.delete("codeforge.apiKey");
    client.setApiKey("");
    vscode.window.showInformationMessage("CodeForge: API key cleared.");
    outputChannel.info("API key cleared");
}
//# sourceMappingURL=extension.js.map