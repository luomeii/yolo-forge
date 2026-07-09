/**
 * OpenAI Provider — Uses the OpenAI SDK (Responses API pattern from Codex)
 *
 * Key patterns from Codex CLI:
 * - Streaming via SSE
 * - Stateless requests (full conversation sent each time)
 * - Prompt caching optimization (static content first, variable last)
 * - Handles reasoning_content for thinking-mode models (MiMo, DeepSeek, etc.)
 */

import OpenAI from 'openai';
import {
  LLMProvider,
  LLMProviderConfig,
  LLMChatRequest,
  LLMChatResponse,
  LLMStreamEvent,
  LLMPayloadMessage,
} from './types';

export class OpenAIProvider implements LLMProvider {
  readonly name = 'openai';
  private client: OpenAI | null = null;
  private config: LLMProviderConfig = {
    apiKey: '',
    model: 'gpt-4o',
  };

  private ensureClient(): OpenAI {
    if (!this.client || !this.config.apiKey) {
      throw new Error('OpenAI API key not configured. Please set it in Settings.');
    }
    return this.client;
  }

  updateConfig(config: Partial<LLMProviderConfig>): void {
    Object.assign(this.config, config);
    if (this.config.apiKey) {
      this.client = new OpenAI({
        apiKey: this.config.apiKey,
        baseURL: this.config.baseUrl || undefined,
      });
    }
  }

  async chat(request: LLMChatRequest): Promise<LLMChatResponse> {
    const client = this.ensureClient();
    const messages = this.buildMessages(request);
    const tools = this.buildTools(request);

    const response = await client.chat.completions.create({
      model: request.model,
      messages,
      temperature: request.temperature ?? 0.3,
      max_tokens: request.maxTokens ?? 8192,
      ...(tools ? { tools } : {}),
      stream: false,
    });

    const choice = response.choices[0];
    const message = choice.message;

    return {
      content: message.content ?? '',
      toolCalls: (message.tool_calls ?? []).map((tc) => ({
        id: tc.id,
        name: tc.function.name,
        arguments: tc.function.arguments,
      })),
      usage: {
        inputTokens: response.usage?.prompt_tokens ?? 0,
        outputTokens: response.usage?.completion_tokens ?? 0,
      },
    };
  }

  async *chatStream(request: LLMChatRequest): AsyncIterable<LLMStreamEvent> {
    const client = this.ensureClient();
    const messages = this.buildMessages(request);
    const tools = this.buildTools(request);

    console.log(`[OpenAIProvider] chatStream start, model=${request.model}, ${messages.length} msgs, ${tools?.length || 0} tools`);

    // Build request params — disable thinking mode for compatibility
    const params: any = {
      model: request.model,
      messages,
      temperature: request.temperature ?? 0.3,
      max_tokens: request.maxTokens ?? 8192,
      stream: true,
    };

    if (tools?.length) {
      params.tools = tools;
    }

    // Disable thinking mode for models that support it (MiMo, DeepSeek-R1, etc.)
    // This prevents the "reasoning_content must be passed back" error
    // Some endpoints use `enable_thinking`, others use `thinking`
    // We try both — the API will ignore unknown params
    params.enable_thinking = false;
    params.thinking = { type: 'disabled' };

    const stream = await client.chat.completions.create(params) as any;

    let chunkCount = 0;
    let hasReasoningContent = false;

    for await (const chunk of stream as AsyncIterable<any>) {
      chunkCount++;
      const delta = chunk.choices[0]?.delta as any;
      if (!delta) continue;

      // Text content
      if (delta.content) {
        yield { type: 'text_delta', text: delta.content };
      }

      // Reasoning content (MiMo/DeepSeek thinking mode) — capture and pass back later
      if (delta.reasoning_content) {
        hasReasoningContent = true;
        yield { type: 'reasoning_delta', text: delta.reasoning_content };
      }

      // Tool calls
      if (delta.tool_calls) {
        for (const tc of delta.tool_calls) {
          if (tc.id) {
            yield {
              type: 'tool_call_start',
              toolCallId: tc.id,
              toolName: tc.function?.name ?? '',
            };
          }
          if (tc.function?.arguments) {
            yield {
              type: 'tool_call_delta',
              toolCallId: tc.id ?? '',
              argumentsDelta: tc.function.arguments,
            };
          }
        }
      }

      // Check for finish
      const finishReason = chunk.choices[0]?.finish_reason;
      if (finishReason === 'tool_calls') {
        yield { type: 'tool_call_end' };
      }
    }

    console.log(`[OpenAIProvider] chatStream done, ${chunkCount} chunks, reasoning=${hasReasoningContent}`);

    yield { type: 'done' };
  }

  estimateTokens(messages: LLMPayloadMessage[]): number {
    let totalChars = 0;
    for (const msg of messages) {
      totalChars += (msg.content?.length ?? 0) * 1.3;
      if (msg.toolCalls) {
        for (const tc of msg.toolCalls) {
          totalChars += (tc.arguments?.length ?? 0) * 1.3;
        }
      }
    }
    return Math.ceil(totalChars / 4);
  }

  private buildMessages(request: LLMChatRequest): OpenAI.ChatCompletionMessageParam[] {
    return request.messages.map((msg): OpenAI.ChatCompletionMessageParam => {
      if (msg.role === 'tool' && msg.toolCallId) {
        return {
          role: 'tool' as const,
          tool_call_id: msg.toolCallId,
          content: msg.content,
        };
      }
      if (msg.role === 'assistant' && msg.toolCalls?.length) {
        const assistantMsg: any = {
          role: 'assistant' as const,
          content: msg.content || null,
          tool_calls: msg.toolCalls.map((tc) => ({
            id: tc.id,
            type: 'function' as const,
            function: {
              name: tc.name,
              arguments: tc.arguments,
            },
          })),
        };
        // Pass reasoning_content back for thinking-mode models (MiMo, DeepSeek-R1)
        if (msg.reasoningContent) {
          assistantMsg.reasoning_content = msg.reasoningContent;
        }
        return assistantMsg;
      }
      if (msg.role === 'system') {
        return { role: 'system' as const, content: msg.content };
      }
      if (msg.role === 'user') {
        return { role: 'user' as const, content: msg.content };
      }
      // Fallback for 'assistant' without tool calls
      const fallbackMsg: any = { role: 'assistant' as const, content: msg.content };
      if (msg.reasoningContent) {
        fallbackMsg.reasoning_content = msg.reasoningContent;
      }
      return fallbackMsg;
    });
  }

  private buildTools(request: LLMChatRequest): OpenAI.ChatCompletionTool[] | undefined {
    if (!request.tools?.length) return undefined;
    return request.tools.map((tool) => ({
      type: 'function' as const,
      function: {
        name: tool.name,
        description: tool.description,
        parameters: tool.input_schema,
      },
    }));
  }
}
