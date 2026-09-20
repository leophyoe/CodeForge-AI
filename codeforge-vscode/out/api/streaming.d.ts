import type { StreamEvent } from "./types.js";
export declare class SSEStreamReader {
    private reader;
    private buffer;
    constructor(reader: ReadableStreamDefaultReader<Uint8Array>);
    events(): AsyncGenerator<StreamEvent>;
    private parseEvent;
}
export declare function createSSEStream(response: Response): SSEStreamReader;
//# sourceMappingURL=streaming.d.ts.map