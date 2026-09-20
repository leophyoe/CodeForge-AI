export interface EditorContext {
    text: string;
    language: string;
    filename: string;
    startLine: number;
    endLine: number;
    hasSelection: boolean;
}
export declare function getSelectedText(): string;
export declare function getEditorContext(maxChars?: number): EditorContext | null;
export declare function getCursorPrefix(maxChars: number): string;
export declare function getCursorSuffix(maxChars: number): string;
export declare function getLanguageId(): string;
export declare function getFilename(): string;
export declare function getWorkspaceRoot(): string;
//# sourceMappingURL=workspaceContext.d.ts.map