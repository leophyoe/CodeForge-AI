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
exports.explainCommand = explainCommand;
exports.generateCommand = generateCommand;
exports.fixCommand = fixCommand;
exports.refactorCommand = refactorCommand;
exports.generateTestsCommand = generateTestsCommand;
const vscode = __importStar(require("vscode"));
const workspaceContext_js_1 = require("../context/workspaceContext.js");
const errors_js_1 = require("../api/errors.js");
async function promptForInstruction(prompt) {
    return vscode.window.showInputBox({
        prompt,
        placeHolder: "e.g., Improve readability, add error handling...",
    });
}
async function sendToChat(client, systemPrompt, userContent) {
    const config = vscode.workspace.getConfiguration("codeforge");
    const model = config.get("model", "");
    if (!model) {
        throw new Error("No model selected. Use CodeForge: Select Model first.");
    }
    const response = await client.chat({
        model,
        messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: userContent },
        ],
        stream: false,
    });
    return response.choices[0]?.message?.content ?? "";
}
async function showDiffPreview(originalUri, proposedContent, title) {
    const tempUri = vscode.Uri.parse(`untitled:${title}-${Date.now()}.txt`);
    const edit = new vscode.WorkspaceEdit();
    edit.insert(tempUri, new vscode.Position(0, 0), proposedContent);
    await vscode.workspace.applyEdit(edit);
    await vscode.commands.executeCommand("vscode.diff", originalUri, tempUri, title);
    const apply = await vscode.window.showInformationMessage("Apply this change?", "Apply", "Reject");
    if (apply === "Apply") {
        const originalEdit = new vscode.WorkspaceEdit();
        const document = await vscode.workspace.openTextDocument(originalUri);
        const fullRange = new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));
        originalEdit.replace(originalUri, fullRange, proposedContent);
        await vscode.workspace.applyEdit(originalEdit);
        vscode.window.showInformationMessage("Change applied.");
    }
    const cleanupEdit = new vscode.WorkspaceEdit();
    cleanupEdit.delete(tempUri, new vscode.Range(0, 0, 0, 0));
    await vscode.workspace.applyEdit(cleanupEdit);
}
async function explainCommand(client) {
    const ctx = (0, workspaceContext_js_1.getEditorContext)(8000);
    if (!ctx) {
        vscode.window.showWarningMessage("Open a file and select code to explain.");
        return;
    }
    const language = ctx.language;
    const filename = ctx.filename.split(/[/\\]/).pop() ?? ctx.filename;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "CodeForge: Explaining code..." }, async () => {
        try {
            const explanation = await sendToChat(client, `You are a helpful coding assistant. Explain the following ${language} code clearly and concisely. Focus on what the code does, how it works, and any notable patterns. File: ${filename}`, ctx.hasSelection
                ? `Explain this code:\n\`\`\`${language}\n${ctx.text}\n\`\`\``
                : `Explain this file:\n\`\`\`${language}\n${ctx.text}\n\`\`\``);
            const panel = vscode.window.createWebviewPanel("codeforgeExplain", "CodeForge: Explanation", vscode.ViewColumn.Beside, { enableScripts: false });
            panel.webview.html = `<!DOCTYPE html>
<html><head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
  <style>body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:16px;white-space:pre-wrap;word-wrap:break-word;}</style>
</head><body>${escapeHtml(explanation)}</body></html>`;
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError) {
                vscode.window.showErrorMessage(`CodeForge: ${err.message}`);
            }
            else {
                vscode.window.showErrorMessage("CodeForge: Failed to explain code.");
            }
        }
    });
}
async function generateCommand(client) {
    const ctx = (0, workspaceContext_js_1.getEditorContext)(8000);
    const instruction = await promptForInstruction("What should CodeForge generate?");
    if (!instruction) {
        return;
    }
    const language = ctx?.language ?? "plaintext";
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "CodeForge: Generating code..." }, async () => {
        try {
            const contextInfo = ctx?.hasSelection
                ? `\n\nContext (selected code):\n\`\`\`${language}\n${ctx.text}\n\`\`\``
                : "";
            const code = await sendToChat(client, `You are a helpful coding assistant. Generate code based on the user's instruction. Return ONLY the code in a markdown code block with the appropriate language tag. Do not include explanations.`, `${instruction}${contextInfo}`);
            const extracted = extractCodeBlock(code) ?? code;
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                editor.insertSnippet(new vscode.SnippetString(extracted));
            }
            else {
                const doc = await vscode.workspace.openTextDocument({ language, content: extracted });
                await vscode.window.showTextDocument(doc);
            }
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError) {
                vscode.window.showErrorMessage(`CodeForge: ${err.message}`);
            }
            else {
                vscode.window.showErrorMessage("CodeForge: Failed to generate code.");
            }
        }
    });
}
async function fixCommand(client) {
    const ctx = (0, workspaceContext_js_1.getEditorContext)(8000);
    if (!ctx) {
        vscode.window.showWarningMessage("Open a file and select code to fix.");
        return;
    }
    let diagnosticInfo = "";
    const editor = vscode.window.activeTextEditor;
    if (editor) {
        const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
        if (diagnostics.length > 0) {
            diagnosticInfo = "\n\nDiagnostics:\n" + diagnostics
                .map((d) => `- Line ${d.range.start.line + 1}: ${d.message}`)
                .join("\n");
        }
    }
    const filename = ctx.filename.split(/[/\\]/).pop() ?? ctx.filename;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "CodeForge: Fixing code..." }, async () => {
        try {
            const fixed = await sendToChat(client, `You are a helpful coding assistant. Fix the bugs in the following ${ctx.language} code. Return the corrected code in a markdown code block. File: ${filename}`, `Fix this code:\n\`\`\`${ctx.language}\n${ctx.text}\n\`\`\`${diagnosticInfo}`);
            const extracted = extractCodeBlock(fixed) ?? fixed;
            if (extracted.trim() === ctx.text.trim()) {
                vscode.window.showInformationMessage("CodeForge: No changes needed. Code appears correct.");
                return;
            }
            const originalUri = vscode.Uri.file(ctx.filename);
            const document = await vscode.workspace.openTextDocument(originalUri);
            const fullRange = new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));
            const originalContent = document.getText(fullRange);
            const tempUri = vscode.Uri.parse(`untitled:CodeForge Fix ${Date.now()}.txt`);
            const edit = new vscode.WorkspaceEdit();
            edit.insert(tempUri, new vscode.Position(0, 0), extracted);
            await vscode.workspace.applyEdit(edit);
            await vscode.commands.executeCommand("vscode.diff", originalUri, tempUri, "CodeForge: Proposed Fix");
            const action = await vscode.window.showInformationMessage("Apply this fix?", "Apply", "Reject");
            if (action === "Apply") {
                const applyEdit = new vscode.WorkspaceEdit();
                applyEdit.replace(originalUri, fullRange, extracted);
                await vscode.workspace.applyEdit(applyEdit);
                vscode.window.showInformationMessage("Fix applied.");
            }
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError) {
                vscode.window.showErrorMessage(`CodeForge: ${err.message}`);
            }
            else {
                vscode.window.showErrorMessage("CodeForge: Failed to fix code.");
            }
        }
    });
}
async function refactorCommand(client) {
    const ctx = (0, workspaceContext_js_1.getEditorContext)(8000);
    if (!ctx) {
        vscode.window.showWarningMessage("Open a file and select code to refactor.");
        return;
    }
    const instruction = await promptForInstruction("How should CodeForge refactor this code?");
    if (!instruction) {
        return;
    }
    const filename = ctx.filename.split(/[/\\]/).pop() ?? ctx.filename;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "CodeForge: Refactoring code..." }, async () => {
        try {
            const refactored = await sendToChat(client, `You are a helpful coding assistant. Refactor the following ${ctx.language} code according to the user's instruction. Return the refactored code in a markdown code block. File: ${filename}`, `Refactor this code: ${instruction}\n\n\`\`\`${ctx.language}\n${ctx.text}\n\`\`\``);
            const extracted = extractCodeBlock(refactored) ?? refactored;
            if (extracted.trim() === ctx.text.trim()) {
                vscode.window.showInformationMessage("CodeForge: No changes needed after refactoring.");
                return;
            }
            const originalUri = vscode.Uri.file(ctx.filename);
            const document = await vscode.workspace.openTextDocument(originalUri);
            const fullRange = new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));
            const tempUri = vscode.Uri.parse(`untitled:CodeForge Refactor ${Date.now()}.txt`);
            const tempEdit = new vscode.WorkspaceEdit();
            tempEdit.insert(tempUri, new vscode.Position(0, 0), extracted);
            await vscode.workspace.applyEdit(tempEdit);
            await vscode.commands.executeCommand("vscode.diff", originalUri, tempUri, "CodeForge: Proposed Refactor");
            const action = await vscode.window.showInformationMessage("Apply this refactor?", "Apply", "Reject");
            if (action === "Apply") {
                const applyEdit = new vscode.WorkspaceEdit();
                applyEdit.replace(originalUri, fullRange, extracted);
                await vscode.workspace.applyEdit(applyEdit);
                vscode.window.showInformationMessage("Refactor applied.");
            }
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError) {
                vscode.window.showErrorMessage(`CodeForge: ${err.message}`);
            }
            else {
                vscode.window.showErrorMessage("CodeForge: Failed to refactor code.");
            }
        }
    });
}
async function generateTestsCommand(client) {
    const ctx = (0, workspaceContext_js_1.getEditorContext)(8000);
    if (!ctx) {
        vscode.window.showWarningMessage("Open a file and select code to generate tests for.");
        return;
    }
    const filename = ctx.filename.split(/[/\\]/).pop() ?? ctx.filename;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "CodeForge: Generating tests..." }, async () => {
        try {
            const tests = await sendToChat(client, `You are a helpful coding assistant. Generate comprehensive unit tests for the following ${ctx.language} code. Return the test code in a markdown code block with the appropriate language tag. Use common testing frameworks for the language. File: ${filename}`, `Generate tests for:\n\`\`\`${ctx.language}\n${ctx.text}\n\`\`\``);
            const extracted = extractCodeBlock(tests) ?? tests;
            const testFilename = `${filename}.test.${ctx.language === "typescript" ? "ts" : ctx.language === "javascript" ? "js" : ctx.language}`;
            const testUri = vscode.Uri.file(testFilename);
            const exists = await vscode.workspace.fs.stat(testUri).then(() => true, () => false);
            if (exists) {
                const action = await vscode.window.showWarningMessage(`File ${testFilename} already exists.`, "Overwrite", "Append", "Cancel");
                if (action === "Overwrite") {
                    const edit = new vscode.WorkspaceEdit();
                    const doc = await vscode.workspace.openTextDocument(testUri);
                    const fullRange = new vscode.Range(doc.positionAt(0), doc.positionAt(doc.getText().length));
                    edit.replace(testUri, fullRange, extracted);
                    await vscode.workspace.applyEdit(edit);
                }
                else if (action === "Append") {
                    const edit = new vscode.WorkspaceEdit();
                    edit.insert(testUri, new vscode.Position(0, 0), extracted + "\n\n");
                    await vscode.workspace.applyEdit(edit);
                }
            }
            else {
                const confirm = await vscode.window.showInformationMessage(`Create ${testFilename}?`, "Create", "Cancel");
                if (confirm === "Create") {
                    const edit = new vscode.WorkspaceEdit();
                    edit.createFile(testUri);
                    edit.insert(testUri, new vscode.Position(0, 0), extracted);
                    await vscode.workspace.applyEdit(edit);
                    await vscode.window.showTextDocument(testUri);
                }
            }
        }
        catch (err) {
            if (err instanceof errors_js_1.CodeForgeError) {
                vscode.window.showErrorMessage(`CodeForge: ${err.message}`);
            }
            else {
                vscode.window.showErrorMessage("CodeForge: Failed to generate tests.");
            }
        }
    });
}
function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}
function extractCodeBlock(text) {
    const match = text.match(/```(?:\w+)?\n([\s\S]*?)```/);
    return match?.[1] ?? null;
}
//# sourceMappingURL=index.js.map