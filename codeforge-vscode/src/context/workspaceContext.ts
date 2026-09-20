import * as vscode from "vscode";

export interface EditorContext {
  text: string;
  language: string;
  filename: string;
  startLine: number;
  endLine: number;
  hasSelection: boolean;
}

export function getSelectedText(): string {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return "";
  }
  const selection = editor.selection;
  if (selection.isEmpty) {
    return "";
  }
  return editor.document.getText(selection);
}

export function getEditorContext(maxChars?: number): EditorContext | null {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return null;
  }

  const document = editor.document;
  const selection = editor.selection;

  let text: string;
  let startLine: number;
  let endLine: number;

  if (selection.isEmpty) {
    text = document.getText();
    startLine = 0;
    endLine = document.lineCount - 1;
  } else {
    text = document.getText(selection);
    startLine = selection.start.line;
    endLine = selection.end.line;
  }

  if (maxChars && text.length > maxChars) {
    text = text.slice(0, maxChars);
  }

  return {
    text,
    language: document.languageId,
    filename: document.fileName,
    startLine,
    endLine,
    hasSelection: !selection.isEmpty,
  };
}

export function getCursorPrefix(maxChars: number): string {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return "";
  }

  const document = editor.document;
  const position = editor.selection.active;
  const offset = document.offsetAt(position);
  const text = document.getText();
  return text.slice(Math.max(0, offset - maxChars), offset);
}

export function getCursorSuffix(maxChars: number): string {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return "";
  }

  const document = editor.document;
  const position = editor.selection.active;
  const offset = document.offsetAt(position);
  const text = document.getText();
  return text.slice(offset, Math.min(text.length, offset + maxChars));
}

export function getLanguageId(): string {
  const editor = vscode.window.activeTextEditor;
  return editor?.document.languageId ?? "plaintext";
}

export function getFilename(): string {
  const editor = vscode.window.activeTextEditor;
  return editor?.document.fileName ?? "";
}

export function getWorkspaceRoot(): string {
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
  return workspaceFolder?.uri.fsPath ?? "";
}
