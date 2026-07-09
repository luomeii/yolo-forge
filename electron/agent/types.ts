/**
 * Agent Type Definitions
 *
 * Unified types for the agent system, following patterns from
 * both OpenAI Responses API and Anthropic Messages API
 */

// ─── Configuration ───

export interface AgentConfig {
  provider: 'openai' | 'anthropic';
  model: string;
  apiKey: string;
  baseUrl?: string;
  temperature?: number;
  maxTokens?: number;
  maxIterations?: number;
  compactionThreshold?: number;
}

// ─── Agent State Machine ───

export enum AgentStateType {
  IDLE = 'idle',
  THINKING = 'thinking',
  EXECUTING_TOOL = 'executing_tool',
  WAITING_PERMISSION = 'waiting_permission',
  COMPACTING = 'compacting',
  STREAMING = 'streaming',
  COMPLETED = 'completed',
  ERROR = 'error',
  ABORTED = 'aborted',
}

// ─── Agent Events ───

export type AgentEvent =
  | { type: 'user_message'; content: string; timestamp: number }
  | { type: 'context_assembled'; tokenEstimate: number }
  | { type: 'compaction_needed'; tokenEstimate: number; threshold: number }
  | { type: 'compaction_done'; newTokenEstimate: number }
  | { type: 'llm_call_start'; provider: string; model: string; iteration: number }
  | { type: 'text_delta'; text: string }
  | { type: 'tool_call'; toolName: string; arguments: string }
  | { type: 'tool_result'; toolName: string; result: string }
  | { type: 'tool_denied'; toolName: string; reason: string }
  | { type: 'tool_error'; toolName: string; error: string }
  | { type: 'permission_request'; toolName: string; arguments: string; toolCallId: string; description: string; risk: 'low' | 'medium' | 'high' }
  | { type: 'agent_complete'; content: string; iterations: number; tokenUsage: { total: number } }
  | { type: 'llm_error'; error: string };

// ─── Tool Definitions ───

export interface ToolDefinition {
  name: string;
  description: string;
  riskLevel: 'low' | 'medium' | 'high';
  parameters: ToolParameterSchema;
  isReadOnly: boolean;
  isDestructive: boolean;
}

export interface ToolParameterSchema {
  type: 'object';
  properties: Record<string, ToolParameterProperty>;
  required?: string[];
}

export interface ToolParameterProperty {
  type: string;
  description: string;
  enum?: string[];
  default?: any;
}

export interface ToolExecutionContext {
  sessionId: string;
  workingDirectory?: string;
  abortSignal: AbortSignal;
}

// ─── Session ───

export interface SessionMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  toolCalls?: LLMToolCall[];
  toolCallId?: string;
  isError?: boolean;
  timestamp?: number;
  reasoningContent?: string;  // For thinking-mode models
}

export interface LLMToolCall {
  id: string;
  name: string;
  arguments: string;
}

export interface Session {
  id: string;
  messages: SessionMessage[];
  workingDirectory?: string;
  createdAt: number;
  updatedAt: number;
  metadata?: Record<string, any>;
}
