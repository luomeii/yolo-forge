/**
 * Agent Orchestrator — The core of YOLO-Forge SP
 *
 * Architecture follows Claude Code's state-machine agent loop pattern:
 * - Async generator-based loop with multiple yield points
 * - Multi-provider LLM support (OpenAI + Anthropic)
 * - Structured tool system with Zod schemas
 * - Default-deny permission system with denial tracking
 * - Multi-strategy context compaction
 * - Streaming via SSE
 *
 * This is NOT a simple chat wrapper. It's a full agentic system.
 */

import { EventEmitter } from 'events';
import { LLMProvider, LLMToolCall, LLMStreamEvent } from './providers/types';
import { OpenAIProvider } from './providers/openai-provider';
import { AnthropicProvider } from './providers/anthropic-provider';
import { ToolRegistry } from './tools/registry';
import { PermissionManager, PermissionDecision, PermissionChoice } from './permissions/manager';
import { ContextManager } from './context/manager';
import { SessionManager } from './loop/session';
import { AgentConfig, AgentEvent } from './types';
import { Store } from '../store';

export class AgentOrchestrator extends EventEmitter {
  private providers: Map<string, LLMProvider> = new Map();
  private toolRegistry: ToolRegistry;
  private permissionManager: PermissionManager;
  private contextManager: ContextManager;
  private sessionManager: SessionManager;
  private store: Store;
  private activeLoops: Map<string, AbortController> = new Map();
  private disposed = false;

  constructor(store: Store, pythonWorker: any) {
    super();
    this.store = store;
    this.toolRegistry = new ToolRegistry(pythonWorker);
    this.permissionManager = new PermissionManager();
    this.contextManager = new ContextManager();
    this.sessionManager = new SessionManager();

    // Register LLM providers
    this.providers.set('openai', new OpenAIProvider());
    this.providers.set('anthropic', new AnthropicProvider());
  }

  /**
   * Main agent loop — follows Claude Code's async generator pattern
   * with 7 distinct yield points for state management
   */
  async *runAgentLoop(
    userMessage: string,
    sessionId: string,
    abortSignal: AbortSignal
  ): AsyncGenerator<AgentEvent> {
    const session = this.sessionManager.getOrCreate(sessionId);
    const config = await this.getConfig();

    // ── Yield Point 1: User message received ──
    yield { type: 'user_message', content: userMessage, timestamp: Date.now() };

    // Add user message to session
    session.addMessage({ role: 'user', content: userMessage });

    // Build system prompt with context
    const systemPrompt = await this.buildSystemPrompt(session);

    // ── Yield Point 2: Context assembled ──
    yield { type: 'context_assembled', tokenEstimate: this.contextManager.estimateTokens(session.messages) };

    let iterations = 0;
    const maxIterations = config.maxIterations ?? 25;

    while (iterations < maxIterations && !abortSignal.aborted) {
      iterations++;

      // Check if context compaction is needed
      const tokenEstimate = this.contextManager.estimateTokens(session.messages);
      if (tokenEstimate > (config.compactionThreshold ?? 80000)) {
        // ── Yield Point 3: Compaction needed ──
        yield { type: 'compaction_needed', tokenEstimate, threshold: config.compactionThreshold ?? 80000 };

        const compacted = await this.contextManager.compact(
          session.messages,
          session.id,
          this.getActiveProvider(config)
        );

        session.messages = compacted.messages;

        yield { type: 'compaction_done', newTokenEstimate: compacted.tokenEstimate };
      }

      // Get tool schemas for this iteration
      const tools = this.toolRegistry.getSchemas();

      // Build message payload for LLM
      const messages = this.contextManager.buildPayload(session.messages, systemPrompt);

      // ── Yield Point 4: LLM call starting ──
      yield { type: 'llm_call_start', provider: config.provider, model: config.model, iteration: iterations };

      try {
        const provider = this.getActiveProvider(config);
        const stream = provider.chatStream({
          messages,
          tools,
          model: config.model,
          temperature: config.temperature ?? 0.3,
          maxTokens: config.maxTokens ?? 4096,
        });

        let assistantContent = '';
        let reasoningContent = '';
        let toolCalls: LLMToolCall[] = [];
        let currentToolCall: Partial<LLMToolCall> | null = null;

        for await (const event of stream) {
          if (abortSignal.aborted) break;

          switch (event.type) {
            case 'text_delta':
              assistantContent += event.text;
              // ── Yield Point 5: Streaming token ──
              yield { type: 'text_delta', text: event.text };
              break;

            case 'reasoning_delta':
              reasoningContent += event.text;
              break;

            case 'tool_call_start':
              currentToolCall = {
                id: event.toolCallId,
                name: event.toolName,
                arguments: '',
              };
              break;

            case 'tool_call_delta':
              if (currentToolCall) {
                currentToolCall.arguments = (currentToolCall.arguments ?? '') + event.argumentsDelta;
              }
              break;

            case 'tool_call_end':
              if (currentToolCall && currentToolCall.id && currentToolCall.name) {
                toolCalls.push({
                  id: currentToolCall.id,
                  name: currentToolCall.name,
                  arguments: currentToolCall.arguments ?? '{}',
                });
              }
              currentToolCall = null;
              break;
          }
        }

        // Add assistant message to session (with reasoning_content for thinking-mode models)
        session.addMessage({
          role: 'assistant',
          content: assistantContent,
          toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
          reasoningContent: reasoningContent || undefined,
        });

        // If no tool calls, the agent is done
        if (toolCalls.length === 0) {
          // ── Yield Point 6: Agent complete ──
          yield {
            type: 'agent_complete',
            content: assistantContent,
            iterations,
            tokenUsage: { total: tokenEstimate },
          };
          break;
        }

        // Execute tool calls
        for (const toolCall of toolCalls) {
          if (abortSignal.aborted) break;

          const tool = this.toolRegistry.getTool(toolCall.name);
          if (!tool) {
            const errorMsg = `Unknown tool: ${toolCall.name}`;
            session.addMessage({
              role: 'tool',
              toolCallId: toolCall.id,
              content: JSON.stringify({ error: errorMsg }),
              isError: true,
            });

            yield { type: 'tool_error', toolName: toolCall.name, error: errorMsg };
            continue;
          }

          // ── Yield Point 7: Tool execution ──
          yield { type: 'tool_call', toolName: toolCall.name, arguments: toolCall.arguments };

          // Permission check
          const permission = await this.permissionManager.checkPermission(
            toolCall.name,
            toolCall.arguments,
            tool.definition
          );

          if (permission.decision === PermissionDecision.DENY) {
            const denyMsg = permission.reason ?? 'Permission denied by user';
            session.addMessage({
              role: 'tool',
              toolCallId: toolCall.id,
              content: JSON.stringify({ denied: true, reason: denyMsg }),
              isError: true,
            });

            yield { type: 'tool_denied', toolName: toolCall.name, reason: denyMsg };
            continue;
          }

          if (permission.decision === PermissionDecision.ASK) {
            // Register pending promise BEFORE yielding to avoid race condition
            const decisionPromise = this.permissionManager.waitForUserDecision(toolCall.id);
            console.log(`[Orchestrator] Permission requested for ${toolCall.name} (id=${toolCall.id})`);

            // Yield permission request — UI must respond
            yield {
              type: 'permission_request',
              toolName: toolCall.name,
              arguments: toolCall.arguments,
              toolCallId: toolCall.id,
              description: tool.definition.description,
              risk: tool.definition.riskLevel,
            };

            // Wait with timeout (120s) to prevent permanent hang
            try {
              const userDecision = await Promise.race([
                decisionPromise,
                new Promise<PermissionDecision>((_, reject) =>
                  setTimeout(() => reject(new Error('Permission timeout (120s)')), 120000)
                ),
              ]);
              console.log(`[Orchestrator] Permission resolved: ${userDecision} for ${toolCall.name}`);

              if (userDecision === PermissionDecision.DENY) {
                session.addMessage({
                  role: 'tool',
                  toolCallId: toolCall.id,
                  content: JSON.stringify({ denied: true, reason: 'User denied' }),
                  isError: true,
                });
                yield { type: 'tool_denied', toolName: toolCall.name, reason: 'User denied' };
                continue;
              }
            } catch (err: any) {
              console.error(`[Orchestrator] Permission error: ${err.message}`);
              this.permissionManager.cleanupPendingRequest(toolCall.id);
              // CRITICAL: Add a tool result message so the tool_call_id is satisfied
              session.addMessage({
                role: 'tool',
                toolCallId: toolCall.id,
                content: JSON.stringify({ error: `Permission timeout: ${err.message}. Please try again.` }),
                isError: true,
              });
              yield { type: 'tool_error', toolName: toolCall.name, error: `Permission timeout: ${err.message}` };
              continue;
            }
          }

          // Execute the tool with global timeout protection (120s max)
          try {
            const parsedArgs = JSON.parse(toolCall.arguments);
            const toolPromise = tool.execute(parsedArgs, {
              sessionId,
              workingDirectory: session.workingDirectory,
              abortSignal,
            });

            // Global timeout: 120 seconds for any tool
            const result = await Promise.race([
              toolPromise,
              new Promise<never>((_, reject) =>
                setTimeout(() => reject(new Error(`Tool ${toolCall.name} timed out after 120s`)), 120000)
              ),
            ]);

            const resultStr = typeof result === 'string' ? result : JSON.stringify(result, null, 2);

            // For large results, save to disk and pass reference
            if (resultStr.length > 10000) {
              const refPath = await this.contextManager.persistToolResult(
                session.id,
                toolCall.id,
                resultStr
              );
              session.addMessage({
                role: 'tool',
                toolCallId: toolCall.id,
                content: JSON.stringify({
                  summary: resultStr.substring(0, 2000) + '\n...[truncated]',
                  fullResultPath: refPath,
                  totalLength: resultStr.length,
                }),
              });
            } else {
              session.addMessage({
                role: 'tool',
                toolCallId: toolCall.id,
                content: resultStr,
              });
            }

            yield { type: 'tool_result', toolName: toolCall.name, result: resultStr.substring(0, 500) };
          } catch (error: any) {
            const errorMsg = error.message ?? String(error);
            session.addMessage({
              role: 'tool',
              toolCallId: toolCall.id,
              content: JSON.stringify({ error: errorMsg }),
              isError: true,
            });
            yield { type: 'tool_error', toolName: toolCall.name, error: errorMsg };
          }
        }

        // CRITICAL: After processing all tool calls, verify every tool_call_id has a tool result.
        // If any are missing (e.g. due to abort or early break), add placeholder tool messages.
        // This prevents the "400: tool_calls must be followed by tool messages" API error.
        const toolCallIds = toolCalls.map(tc => tc.id);
        const existingToolResults = session.messages
          .filter(m => m.role === 'tool' && m.toolCallId)
          .map(m => m.toolCallId);
        for (const tcId of toolCallIds) {
          if (!existingToolResults.includes(tcId)) {
            console.warn(`[Orchestrator] Missing tool result for ${tcId}, adding placeholder`);
            session.addMessage({
              role: 'tool',
              toolCallId: tcId,
              content: JSON.stringify({ error: 'Tool execution was skipped or aborted' }),
              isError: true,
            });
          }
        }

        // Continue the loop — model will process tool results
      } catch (error: any) {
        if (error.name === 'AbortError') break;
        yield { type: 'llm_error', error: error.message ?? String(error) };
        break;
      }
    }

    // Save session
    await this.sessionManager.saveSession(session);
  }

  /**
   * Convenience method: run agent and collect all events
   */
  async run(
    userMessage: string,
    sessionId: string,
    onEvent?: (event: AgentEvent) => void
  ): Promise<AgentEvent[]> {
    const controller = new AbortController();
    this.activeLoops.set(sessionId, controller);

    const events: AgentEvent[] = [];
    try {
      for await (const event of this.runAgentLoop(userMessage, sessionId, controller.signal)) {
        events.push(event);
        onEvent?.(event);
        this.emit('agentEvent', event);
      }
    } finally {
      this.activeLoops.delete(sessionId);
    }
    return events;
  }

  /**
   * Stop a running agent loop
   */
  stop(sessionId: string): void {
    const controller = this.activeLoops.get(sessionId);
    if (controller) {
      controller.abort();
      this.activeLoops.delete(sessionId);
    }
  }

  /**
   * Respond to a permission request from the UI (Codex-style)
   * choice: 'allow_once' | 'allow_always' | 'deny'
   */
  respondPermission(toolCallId: string, choice: string, toolName?: string, args?: string): void {
    const choiceEnum = choice === 'allow_always' ? PermissionChoice.ALLOW_ALWAYS
                     : choice === 'deny' ? PermissionChoice.DENY
                     : PermissionChoice.ALLOW_ONCE;
    this.permissionManager.resolveUserDecision(toolCallId, choiceEnum, toolName, args);
  }

  // ─── Private Methods ───

  private getActiveProvider(config: AgentConfig): LLMProvider {
    const provider = this.providers.get(config.provider);
    if (!provider) throw new Error(`Unknown provider: ${config.provider}`);
    return provider;
  }

  private async getConfig(): Promise<AgentConfig> {
    const config = await this.store.get('agent');
    return {
      provider: config?.provider ?? 'openai',
      model: config?.model ?? 'gpt-4o',
      apiKey: config?.apiKey ?? '',
      baseUrl: config?.baseUrl,
      temperature: config?.temperature ?? 0.3,
      maxTokens: config?.maxTokens ?? 4096,
      maxIterations: config?.maxIterations ?? 25,
      compactionThreshold: config?.compactionThreshold ?? 80000,
    };
  }

  private async buildSystemPrompt(session: any): Promise<string> {
    const basePrompt = `你是 YOLO-Forge SP，一个智能的YOLO数据集工作站助手。请用中文回复。

## 核心原则

1. **优先使用专用工具**：扫描数据集用inspect_dataset，训练用train_model，不要用shell替代
2. **禁止用shell训练**：训练必须用train_model工具，不能用shell调yolo命令
3. **高效工具调用**：每次任务尽量在3-5次工具调用内完成
4. **操作前先询问**：训练前必须问清数据集路径、模型、epochs、conda环境、导出目录
5. **用中文回复**：除非用户用英文
6. **device参数**：GPU训练用device="0"或device="auto"，CPU用device="cpu"

## 工具使用策略

| 场景 | 必须用 | 禁止用 |
|------|--------|--------|
| 扫描数据集 | inspect_dataset | shell dir/ls |
| 查看文件 | read_file | shell cat/type |
| 训练模型 | train_model | shell yolo train |
| 生成报告 | generate_report | shell python |
| 查看GPU | shell nvidia-smi | - |
| 查看conda环境 | shell conda env list | - |

## train_model工具参数
- data_yaml (必填): data.yaml路径
- conda_env (必填): conda环境名
- model: yolov8n.pt/yolov8s.pt/yolov8m.pt等
- epochs: 训练轮数
- imgsz: 320/416/640/1280
- batch: -1自动
- device: auto/cpu/0/1（GPU用0）
- workers: 数据加载线程
- save_period: 每N轮保存
- optimizer: auto/SGD/Adam/AdamW
- lr0/lrf/momentum/weight_decay/warmup_epochs/patience
- augment: 数据增强
- project: 导出目录
- name: 项目名
- resume: 继续训练

## 重要：当工具调用失败时
- 如果inspect_dataset返回错误，告诉用户Python worker可能没启动
- 如果train_model返回错误，不要用shell替代，告诉用户问题
- 如果权限超时，告诉用户重新尝试

工作目录: ${session.workingDirectory ?? '未设置'}`;

    const customInstructions = await this.store.get('customInstructions');
    if (customInstructions) {
      return basePrompt + '\n\n自定义指令:\n' + customInstructions;
    }
    return basePrompt;
  }

  /**
   * List all sessions (delegates to SessionManager)
   */
  async listSessions() {
    return this.sessionManager.listSessions();
  }

  /**
   * Create a new session
   */
  async createSession() {
    return this.sessionManager.create();
  }

  /**
   * Delete a session
   */
  async deleteSession(sessionId: string) {
    return this.sessionManager.deleteSession(sessionId);
  }

  /**
   * Update provider configuration at runtime
   */
  updateProviderConfig(config: any): void {
    if (config.provider && config.apiKey) {
      const provider = this.providers.get(config.provider);
      if (provider) {
        provider.updateConfig({
          apiKey: config.apiKey,
          baseUrl: config.baseUrl,
          model: config.model,
          temperature: config.temperature,
          maxTokens: config.maxTokens,
        });
      }
    }
  }

  dispose(): void {
    this.disposed = true;
    for (const [id, controller] of this.activeLoops) {
      controller.abort();
    }
    this.activeLoops.clear();
    this.removeAllListeners();
  }
}
