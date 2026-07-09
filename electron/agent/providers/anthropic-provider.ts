/**
 * Anthropic Provider — Uses the Anthropic SDK (Claude Messages API pattern)
 *
 * Key patterns from Claude Code:
 * - Streaming via text_stream iterator
 * - Strict tool schema enforcement
 * - Prompt caching for cost optimization
 * - Multi-turn tool use with parallel tool calls
 */

import Anthropic from '@anthropic-ai/sdk';
import {
  LLMProvider,
  LLMProviderConfig,
  LLMChatRequest,
  LLMChatResponse,
  LLMStreamEvent,
  LLMPayloadMessage,
} from './types';

export class AnthropicProvider implements LLMProvider {
  readonly name = 'anthropic';
  private client: Anthropic | null = null;
  private config: LLMProviderConfig = {
    apiKey: '',
    model: 'claude-sonnet-4-20250514',
  };

  private ensureClient(): Anthropic {
    if (!this.client || !this.config.apiKey) {
      throw new Error('Anthropic API key not configured. Please set it in Settings.');
    }
    return this.client;
  }

  updateConfig(config: Partial<LLMProviderConfig>): void {
    Object.assign(this.config, config);
    if (this.config.apiKey) {
      this.client = new Anthropic({
        apiKey: this.config.apiKey,
        baseURL: this.config.baseUrl || undefined,
      });
    }
  }

  async chat(request: LLMChatRequest): Promise<LLMChatResponse> {
    const client = this.ensureClient();
    const { system, messages } = this.separateSystemMessage(request.messages);

    const response = await client.messages.create({
      model: request.model,
      max_tokens: request.maxTokens ?? 4096,
      system: system || undefined,
      messages,
      tools: this.buildTools(request.tools),
      temperature: request.temperature ?? 0.3,
    });

    let content = '';
    const toolCalls: any[] = [];

    for (const block of response.content) {
      if (block.type === 'text') {
        content += block.text;
      } else if (block.type === 'tool_use') {
        toolCalls.push({
          id: block.id,
          name: block.name,
          arguments: JSON.stringify(block.input),
        });
      }
    }

    return {
      content,
      toolCalls,
      usage: {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
      },
    };
  }

  async *chatStream(request: LLMChatRequest): AsyncIterable<LLMStreamEvent> {
    const client = this.ensureClient();
    const { system, messages } = this.separateSystemMessage(request.messages);

    const stream = client.messages.stream({
      model: request.model,
      max_tokens: request.maxTokens ?? 4096,
      system: system || undefined,
      messages,
      tools: this.buildTools(request.tools),
      temperature: request.temperature ?? 0.3,
    });

    let currentToolId = '';
    let currentToolName = '';

    for await (const event of stream) {
      switch (event.type) {
        case 'content_block_delta':
          if (event.delta.type === 'text_delta') {
            yield { type: 'text_delta', text: event.delta.text };
          } else if (event.delta.type === 'input_json_delta') {
            yield {
              type: 'tool_call_delta',
              toolCallId: currentToolId,
              argumentsDelta: event.delta.partial_json,
            };
          }
          break;

        case 'content_block_start':
          if (event.content_block.type === 'tool_use') {
            currentToolId = event.content_block.id;
            currentToolName = event.content_block.name;
            yield {
              type: 'tool_call_start',
              toolCallId: currentToolId,
              toolName: currentToolName,
            };
          }
          break;

        case 'content_block_stop':
          if (currentToolId) {
            yield { type: 'tool_call_end' };
            currentToolId = '';
            currentToolName = '';
          }
          break;

        case 'message_stop':
          yield { type: 'done' };
          break;
      }
    }
  }

  estimateTokens(messages: LLMPayloadMessage[]): number {
    // Anthropic's tokenizer is roughly similar to OpenAI's
    let totalChars = 0;
    for (const msg of messages) {
      totalChars += (msg.content?.length ?? 0) * 1.3;
      if (msg.toolCalls) {
        for (const tc of msg.toolCalls) {
          totalChars += (tc.arguments?.length ?? 0) * 1.3;
        }
      }
    }
    return Math.ceil(totalChars / 3.5); // Anthropic tends to have slightly more tokens
  }

  private separateSystemMessage(messages: LLMPayloadMessage[]): {
    system: string;
    messages: any[];
  } {
    let system = '';
    const filteredMessages: any[] = [];

    for (const msg of messages) {
      if (msg.role === 'system') {
        system += (system ? '\n\n' : '') + msg.content;
        continue;
      }

      // Convert to Anthropic format
      if (msg.role === 'assistant' && msg.toolCalls?.length) {
        const content: any[] = [];
        if (msg.content) {
          content.push({ type: 'text', text: msg.content });
        }
        for (const tc of msg.toolCalls) {
          content.push({
            type: 'tool_use',
            id: tc.id,
            name: tc.name,
            input: JSON.parse(tc.arguments),
          });
        }
        filteredMessages.push({ role: 'assistant', content });
      } else if (msg.role === 'tool') {
        filteredMessages.push({
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: msg.toolCallId,
              content: msg.content,
              is_error: msg.isError ?? false,
            },
          ],
        });
      } else {
        filteredMessages.push({
          role: msg.role,
          content: msg.content,
        });
      }
    }

    return { system, messages: filteredMessages };
  }

  private buildTools(tools?: any[]): any[] | undefined {
    if (!tools?.length) return undefined;

    return tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      input_schema: {
        ...tool.input_schema,
        // Anthropic requires strict schema
        additionalProperties: false,
      },
    }));
  }
}
