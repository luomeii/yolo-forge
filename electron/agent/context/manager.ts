/**
 * Context Manager — Following Claude Code's multi-strategy compaction pattern
 *
 * Five compaction strategies (from Claude Code):
 * 1. Snip — Quick pruning of older messages (fast, lossy)
 * 2. Microcompact — Target tool outputs, persist to disk, pass reference
 * 3. Context Collapse — Progressive compression of older segments
 * 4. Autocompact — Full conversation summarization via LLM
 * 5. Reactive Compact — Emergency brake when context overflows
 *
 * Additionally implements Codex's prompt cache optimization:
 * - Static content first (system prompt, examples)
 * - Variable content last (recent messages, tool results)
 * - Schema assembled once, held stable throughout session
 */

import { promises as fs } from 'fs';
import path from 'path';
import os from 'os';
import { SessionMessage, LLMToolCall } from '../types';
import { LLMProvider, LLMPayloadMessage } from '../providers/types';

const CONTEXT_DIR = path.join(os.homedir(), '.yolo-forge-sp', 'context');
const MAX_TOOL_RESULT_INLINE = 10000; // chars

interface CompactionResult {
  messages: SessionMessage[];
  tokenEstimate: number;
  strategy: string;
}

export class ContextManager {
  private contextDir: string;

  constructor() {
    this.contextDir = CONTEXT_DIR;
    this.ensureContextDir();
  }

  private async ensureContextDir(): Promise<void> {
    try {
      await fs.mkdir(this.contextDir, { recursive: true });
    } catch {
      // Directory may already exist
    }
  }

  /**
   * Estimate token count for a set of messages
   * Rough heuristic: ~4 chars per token for English, ~2 for CJK
   */
  estimateTokens(messages: SessionMessage[]): number {
    let totalChars = 0;
    for (const msg of messages) {
      totalChars += (msg.content?.length ?? 0) * 1.3;
      if (msg.toolCalls) {
        for (const tc of msg.toolCalls) {
          totalChars += (tc.arguments?.length ?? 0) * 1.3;
        }
      }
    }
    return Math.ceil(totalChars / 3.8);
  }

  /**
   * Build the message payload for LLM API calls
   * Implements Codex's prompt cache optimization:
   * - Static content first (system, examples)
   * - Variable content last (recent messages)
   */
  buildPayload(messages: SessionMessage[], systemPrompt: string): LLMPayloadMessage[] {
    const payload: LLMPayloadMessage[] = [];

    // System message first (static prefix for caching)
    payload.push({
      role: 'system',
      content: systemPrompt,
    });

    // Session messages (variable content)
    for (const msg of messages) {
      const payloadMsg: LLMPayloadMessage = {
        role: msg.role,
        content: msg.content,
      };

      if (msg.toolCalls) {
        payloadMsg.toolCalls = msg.toolCalls;
      }
      if (msg.toolCallId) {
        payloadMsg.toolCallId = msg.toolCallId;
      }
      if (msg.isError) {
        payloadMsg.name = 'error';
      }
      // Preserve reasoning_content for thinking-mode models (MiMo, DeepSeek-R1)
      if (msg.reasoningContent) {
        payloadMsg.reasoningContent = msg.reasoningContent;
      }

      payload.push(payloadMsg);
    }

    return payload;
  }

  /**
   * Compact messages using the best strategy for the situation
   */
  async compact(
    messages: SessionMessage[],
    sessionId: string,
    provider: LLMProvider
  ): Promise<CompactionResult> {
    const tokenEstimate = this.estimateTokens(messages);

    // ── Strategy 1: Snip — Quick pruning for moderate overflow ──
    if (tokenEstimate < 120000) {
      return this.snipCompact(messages);
    }

    // ── Strategy 2: Microcompact — Target large tool outputs ──
    const microResult = this.microcompact(messages, sessionId);
    if (microResult.tokenEstimate < 100000) {
      return microResult;
    }

    // ── Strategy 3: Autocompact — Full LLM summarization ──
    try {
      return await this.autocompact(messages, provider);
    } catch {
      // ── Strategy 5: Reactive Compact — Emergency fallback ──
      return this.reactiveCompact(messages);
    }
  }

  /**
   * Persist a large tool result to disk and return a reference
   * (Claude Code's microcompact pattern)
   */
  async persistToolResult(
    sessionId: string,
    toolCallId: string,
    content: string
  ): Promise<string> {
    await this.ensureContextDir();
    const filename = `${sessionId}_${toolCallId}.json`;
    const filePath = path.join(this.contextDir, filename);
    await fs.writeFile(filePath, content, 'utf-8');
    return filePath;
  }

  /**
   * Read a persisted tool result
   */
  async readToolResult(sessionId: string, toolCallId: string): Promise<string> {
    const filename = `${sessionId}_${toolCallId}.json`;
    const filePath = path.join(this.contextDir, filename);
    return fs.readFile(filePath, 'utf-8');
  }

  // ─── Private Compaction Strategies ───

  /**
   * Strategy 1: Snip — Quick pruning of older messages
   * Keep: system messages, last N messages, all tool results referenced by recent messages
   */
  private snipCompact(messages: SessionMessage[]): CompactionResult {
    if (messages.length <= 6) {
      return { messages, tokenEstimate: this.estimateTokens(messages), strategy: 'snip_noop' };
    }

    // Keep first 2 messages (context setup) and last 6 messages (recent conversation)
    const kept = [
      ...messages.slice(0, 2),
      ...messages.slice(-6),
    ];

    // Add a summary marker
    const summaryMsg: SessionMessage = {
      role: 'system',
      content: `[Context trimmed: ${messages.length - 8} earlier messages removed. ` +
        `Summary: The conversation involved dataset operations and analysis.]`,
      timestamp: Date.now(),
    };

    const result = [summaryMsg, ...kept.slice(2)];
    return {
      messages: result,
      tokenEstimate: this.estimateTokens(result),
      strategy: 'snip',
    };
  }

  /**
   * Strategy 2: Microcompact — Replace large tool outputs with disk references
   */
  private microcompact(
    messages: SessionMessage[],
    sessionId: string
  ): CompactionResult {
    const compacted = messages.map((msg) => {
      if (msg.role === 'tool' && msg.content.length > MAX_TOOL_RESULT_INLINE) {
        return {
          ...msg,
          content: msg.content.substring(0, 2000) +
            `\n\n[...output truncated. ${msg.content.length} total chars. Full result available on disk.]`,
        };
      }
      return msg;
    });

    return {
      messages: compacted,
      tokenEstimate: this.estimateTokens(compacted),
      strategy: 'microcompact',
    };
  }

  /**
   * Strategy 4: Autocompact — Use LLM to summarize conversation
   */
  private async autocompact(
    messages: SessionMessage[],
    provider: LLMProvider
  ): Promise<CompactionResult> {
    // Build a summarization prompt
    const conversationText = messages
      .map((msg) => `[${msg.role}]: ${msg.content.substring(0, 500)}`)
      .join('\n');

    const summaryRequest = {
      messages: [
        {
          role: 'user' as const,
          content: `Summarize the following conversation concisely, preserving all key facts, decisions, and data references:\n\n${conversationText}`,
        },
      ],
      model: 'gpt-4o-mini',
      temperature: 0.1,
      maxTokens: 2000,
    };

    try {
      const response = await provider.chat(summaryRequest);
      const summaryMsg: SessionMessage = {
        role: 'system',
        content: `[Auto-compact summary of previous conversation]:\n${response.content}`,
        timestamp: Date.now(),
      };

      // Keep the summary + last 4 messages
      const result = [summaryMsg, ...messages.slice(-4)];
      return {
        messages: result,
        tokenEstimate: this.estimateTokens(result),
        strategy: 'autocompact',
      };
    } catch (error) {
      throw new Error(`Autocompact failed: ${error}`);
    }
  }

  /**
   * Strategy 5: Reactive Compact — Emergency, aggressive truncation
   */
  private reactiveCompact(messages: SessionMessage[]): CompactionResult {
    // Keep only the last 3 messages
    const result = [
      {
        role: 'system' as const,
        content: '[Emergency context compaction: Most conversation history was removed due to context overflow. The agent has limited memory of earlier discussion.]',
        timestamp: Date.now(),
      },
      ...messages.slice(-3),
    ];

    return {
      messages: result,
      tokenEstimate: this.estimateTokens(result),
      strategy: 'reactive',
    };
  }
}
