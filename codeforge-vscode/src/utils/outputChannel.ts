import * as vscode from "vscode";

export class CodeForgeOutputChannel {
  private channel: vscode.OutputChannel;

  constructor() {
    this.channel = vscode.window.createOutputChannel("CodeForge");
  }

  log(message: string): void {
    const timestamp = new Date().toISOString();
    this.channel.appendLine(`[${timestamp}] ${message}`);
  }

  debug(message: string): void {
    const config = vscode.workspace.getConfiguration("codeforge");
    if (config.get<boolean>("debug", false)) {
      this.log(`[DEBUG] ${message}`);
    }
  }

  error(message: string, err?: unknown): void {
    this.log(`[ERROR] ${message}`);
    if (err instanceof Error) {
      this.log(`  ${err.message}`);
    } else if (err) {
      this.log(`  ${String(err)}`);
    }
  }

  warn(message: string): void {
    this.log(`[WARN] ${message}`);
  }

  info(message: string): void {
    this.log(`[INFO] ${message}`);
  }

  show(): void {
    this.channel.show();
  }

  dispose(): void {
    this.channel.dispose();
  }
}
