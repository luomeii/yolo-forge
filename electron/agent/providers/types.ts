/**
 * LLM Provider Type Definitions
 *
 * Unified interface abstracting OpenAI and Anthropic APIs
 */

export interface LLMProviderConfig {
  apiKey: string;
  baseUrl?: string;
  model: string;
  temperature?: number;
  maxTokens?: number;
}

export interface LLMChatRequest {
  messages: LLMPayloadMessage[];
  tools?: LLMToolSchema[];
  model: string;
  temperature?: number;
  maxTokens?: number;
}

export interface LLMPayloadMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  toolCalls?: LLMToolCall[];
  toolCallId?: string;
  name?: string;
  isError?: boolean;
  reasoningContent?: string;  // For thinking-mode models (MiMo, DeepSeek-R1)
}

export interface LLMToolCall {
  id: string;
  name: string;
  arguments: string;
}

export interface LLMToolSchema {
  name: string;
  description: string;
  input_schema: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
}

export interface LLMStreamEvent {
  type: 'text_delta' | 'tool_call_start' | 'tool_call_delta' | 'tool_call_end' | 'done' | 'error' | 'reasoning_delta';
  text?: string;
  toolCallId?: string;
  toolName?: string;
  argumentsDelta?: string;
  error?: string;
}

export interface LLMProvider {
  readonly name: string;

  chat(request: LLMChatRequest): Promise<LLMChatResponse>;

  chatStream(request: LLMChatRequest): AsyncIterable<LLMStreamEvent>;

  updateConfig(config: Partial<LLMProviderConfig>): void;

  estimateTokens(messages: LLMPayloadMessage[]): number;
}

export interface LLMChatResponse {
  content: string;
  toolCalls: LLMToolCall[];
  usage: {
    inputTokens: number;
    outputTokens: number;
  };
}
