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
exports.getSelectedText = getSelectedText;
exports.getEditorContext = getEditorContext;
exports.getCursorPrefix = getCursorPrefix;
exports.getCursorSuffix = getCursorSuffix;
exports.getLanguageId = getLanguageId;
exports.getFilename = getFilename;
exports.getWorkspaceRoot = getWorkspaceRoot;
const vscode = __importStar(require("vscode"));
function getSelectedText() {
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
function getEditorContext(maxChars) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        return null;
    }
    const document = editor.document;
    const selection = editor.selection;
    let text;
    let startLine;
    let endLine;
    if (selection.isEmpty) {
        text = document.getText();
        startLine = 0;
        endLine = document.lineCount - 1;
    }
    else {
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
function getCursorPrefix(maxChars) {
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
function getCursorSuffix(maxChars) {
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
function getLanguageId() {
    const editor = vscode.window.activeTextEditor;
    return editor?.document.languageId ?? "plaintext";
}
function getFilename() {
    const editor = vscode.window.activeTextEditor;
    return editor?.document.fileName ?? "";
}
function getWorkspaceRoot() {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    return workspaceFolder?.uri.fsPath ?? "";
}
//# sourceMappingURL=workspaceContext.js.map