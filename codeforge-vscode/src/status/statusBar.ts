import * as vscode from "vscode";

export type ConnectionState = "connecting" | "connected" | "disconnected" | "error" | "loading";

export class CodeForgeStatusBar {
  private item: vscode.StatusBarItem;
  private state: ConnectionState = "disconnected";

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.item.command = "codeforge.checkConnection";
    this.setState("disconnected");
    this.item.show();
  }

  setState(state: ConnectionState, message?: string): void {
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

  getState(): ConnectionState {
    return this.state;
  }

  dispose(): void {
    this.item.dispose();
  }
}
