export type ConnectionState = "connecting" | "connected" | "disconnected" | "error" | "loading";
export declare class CodeForgeStatusBar {
    private item;
    private state;
    constructor();
    setState(state: ConnectionState, message?: string): void;
    getState(): ConnectionState;
    dispose(): void;
}
//# sourceMappingURL=statusBar.d.ts.map