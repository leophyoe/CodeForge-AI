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
exports.CodeForgeStatusBar = void 0;
const vscode = __importStar(require("vscode"));
class CodeForgeStatusBar {
    item;
    state = "disconnected";
    constructor() {
        this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
        this.item.command = "codeforge.checkConnection";
        this.setState("disconnected");
        this.item.show();
    }
    setState(state, message) {
        this.state = state;
        switch (state) {
            case "connecting":
                this.item.text = "$(sync~spin) CodeForge: Connecting...";
                this.item.tooltip = "Connecting to CodeForge server";
                this.item.backgroundColor = undefined;
                break;
            case "connected":
                this.item.text = "$(check) CodeForge: Connected";
                this.item.tooltip = message ?? "CodeForge server is online";
                this.item.backgroundColor = undefined;
                break;
            case "disconnected":
                this.item.text = "$(circle-slash) CodeForge: Offline";
                this.item.tooltip = message ?? "CodeForge server is not reachable";
                this.item.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
                break;
            case "error":
                this.item.text = "$(warning) CodeForge: Error";
                this.item.tooltip = message ?? "Connection error";
                this.item.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground");
                break;
            case "loading":
                this.item.text = "$(sync~spin) CodeForge: Loading Model...";
                this.item.tooltip = message ?? "Loading model";
                this.item.backgroundColor = undefined;
                break;
        }
    }
    getState() {
        return this.state;
    }
    dispose() {
        this.item.dispose();
    }
}
exports.CodeForgeStatusBar = CodeForgeStatusBar;
//# sourceMappingURL=statusBar.js.map