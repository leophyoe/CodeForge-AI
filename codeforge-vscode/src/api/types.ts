export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface GenerationConfig {
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  stop_sequences?: string[];
  seed?: number;
}

export interface ChatRequest {
  model: string;
  messages: ChatMessage[];
  config?: GenerationConfig;
  stream?: boolean;
}

export interface CompletionRequest {
  model: string;
  prompt: string;
  config?: GenerationConfig;
  stream?: boolean;
}

export interface UsageInfo {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatChoice[];
  usage: UsageInfo;
}

export interface ChatChoice {
  index: number;
  message: ChatMessage;
  finish_reason: string | null;
}

export interface CompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: CompletionChoice[];
  usage: UsageInfo;
}

export interface CompletionChoice {
  index: number;
  text: string;
  finish_reason: string | null;
}

export interface StreamEvent {
  type: "token" | "end" | "error";
  token?: string;
  done?: boolean;
  error?: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  loaded: boolean;
  architecture?: string;
  context_length?: number;
  device?: string;
  path?: string;
}

export interface HardwareInfo {
  cpu_count: number;
  memory_total_gb: number;
  gpu_available: boolean;
  gpu_name?: string;
  gpu_memory_gb?: number;
}

export interface RuntimeInfo {
  pytorch_installed: boolean;
  pytorch_version?: string;
  cuda_available: boolean;
  device?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
  request_id: string;
}

export interface SystemInfo {
  version: string;
  api_version: string;
  status: string;
  uptime: number;
}

export interface ApiError {
  error: string;
  detail: string;
  request_id?: string;
  status_code: number;
}
