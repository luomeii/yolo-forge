/**
 * Chat Panel — Right-side Agent Chat interface
 *
 * Following Codex CLI / Claude Code conversation pattern:
 * - Streaming message display
 * - Tool call visualization with expand/collapse
 * - Permission request prompts
 * - Markdown rendering
 * - Multi-session support
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAppStore } from '../../stores/app-store';
import { MessageBubble } from './MessageBubble';
import { PermissionPrompt } from './PermissionPrompt';
import { t } from '../../i18n';

export const ChatPanel: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    isAgentRunning,
    permissionRequest,
    addMessage,
    updateMessage,
    setAgentRunning,
    setCurrentToolCall,
    setPermissionRequest,
    createSession,
    deleteSession,
    setActiveSession,
    renameSession,
    locale,
  } = useAppStore();

  const [input, setInput] = useState('');
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [inputHeight, setInputHeight] = useState(80); // adjustable input area height
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const messages = activeSession?.messages ?? [];

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || !activeSessionId || isAgentRunning) return;

    const userMessage = input.trim();
    setInput('');

    // Add user message
    const userMsgId = `msg_${Date.now()}_user`;
    addMessage(activeSessionId, {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      timestamp: Date.now(),
    });

    // Create assistant message placeholder
    const assistantMsgId = `msg_${Date.now()}_assistant`;
    addMessage(activeSessionId, {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    });

    setStreamingMessageId(assistantMsgId);
    setAgentRunning(true);

    try {
      const stream = window.electronAPI.agent.sendMessageStream(userMessage, activeSessionId);

      stream.onToken((token: string) => {
        // Append token to the streaming message
        const session = useAppStore.getState().sessions.find((s) => s.id === activeSessionId);
        const msg = session?.messages.find((m) => m.id === assistantMsgId);
        if (msg) {
          updateMessage(activeSessionId, assistantMsgId, {
            content: msg.content + token,
          });
        }
      });

      stream.onToolCall((toolCall: any) => {
        setCurrentToolCall(toolCall);
      });

      stream.onToolResult((result: any) => {
        setCurrentToolCall(null);
        // Don't add a separate message for each tool result — too cluttered.
        // The tool call/result is already shown in the assistant message's toolCalls display.
        // Only add a subtle system note if it's an error
        if (result.type === 'tool_error' || result.error) {
          addMessage(activeSessionId, {
            id: `msg_${Date.now()}_tool_${Math.random().toString(36).substring(2, 6)}`,
            role: 'system',
            content: `[${result.toolName}] ${result.error || 'execution failed'}`,
            timestamp: Date.now(),
            isError: true,
          });
        }
      });

      stream.onPermissionRequest((request: any) => {
        setPermissionRequest(request);
      });

      stream.onComplete(() => {
        updateMessage(activeSessionId, assistantMsgId, { isStreaming: false });
        setStreamingMessageId(null);
        setAgentRunning(false);
        stream.dispose();
      });

      stream.onError((error: any) => {
        updateMessage(activeSessionId, assistantMsgId, {
          content: `Error: ${error.error || error.message || 'Unknown error'}`,
          isStreaming: false,
          isError: true,
        });
        setStreamingMessageId(null);
        setAgentRunning(false);
        stream.dispose();
      });
    } catch (error: any) {
      updateMessage(activeSessionId, assistantMsgId, {
        content: `❌ Failed to send message: ${error.message}`,
        isStreaming: false,
        isError: true,
      });
      setStreamingMessageId(null);
      setAgentRunning(false);
    }
  }, [input, activeSessionId, isAgentRunning]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePermissionResponse = (choice: 'allow_once' | 'allow_always' | 'deny') => {
    if (permissionRequest?.toolCallId) {
      const api = window.electronAPI as any;
      if (api.agent && api.agent.respondPermission) {
        api.agent.respondPermission(
          permissionRequest.toolCallId,
          choice,
          permissionRequest.toolName,
          permissionRequest.arguments,
        );
      } else {
        console.error('respondPermission not available in preload');
      }
    }
    setPermissionRequest(null);
  };

  const handleStop = () => {
    if (activeSessionId) {
      window.electronAPI.agent.stop(activeSessionId);
      setAgentRunning(false);
      if (streamingMessageId && activeSessionId) {
        updateMessage(activeSessionId, streamingMessageId, { isStreaming: false });
      }
      setStreamingMessageId(null);
    }
  };

  return (
    <div style={{
      flex: 1,
      minWidth: 0,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg-elevated)',
      borderLeft: '1px solid var(--border-primary)',
    }}>
      {/* ─── Chat Header ─── */}
      <div style={{
        height: 44,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        borderBottom: '1px solid var(--border-primary)',
      }}>
        <span style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text-primary)',
        }}>
          {t('chat.title')}
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => createSession()}
            title={t('chat.newSession')}
            style={{
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid var(--border-primary)',
              borderRadius: 6,
              background: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            +
          </button>
        </div>
      </div>

      {/* ─── Session Tabs (single row, scrollable) ─── */}
      {sessions.length > 0 && (
        <div style={{
          display: 'flex',
          gap: 2,
          padding: '4px 8px',
          borderBottom: '1px solid var(--border-primary)',
          overflowX: 'auto',
          overflowY: 'hidden',
          background: 'var(--bg-secondary)',
          flexShrink: 0,
          maxHeight: 36,
        }}>
          {sessions.map((session) => (
            <div key={session.id} style={{
              display: 'flex',
              alignItems: 'center',
              borderRadius: 'var(--radius-sm)',
              background: session.id === activeSessionId ? 'var(--accent-muted)' : 'transparent',
              flexShrink: 0,
            }}>
              <button
                onClick={() => setActiveSession(session.id)}
                style={{
                  padding: '4px 8px',
                  border: 'none',
                  background: 'transparent',
                  fontSize: 11,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  color: session.id === activeSessionId ? 'var(--accent-deep)' : 'var(--text-tertiary)',
                }}
              >
                {session.name}
              </button>
              {session.id === activeSessionId && (
                <button
                  onClick={() => {
                    const newName = prompt(locale === 'zh' ? '重命名会话:' : 'Rename session:', session.name);
                    if (newName && newName.trim()) {
                      renameSession(session.id, newName.trim());
                    }
                  }}
                  style={{
                    border: 'none', background: 'transparent',
                    color: 'var(--text-tertiary)', cursor: 'pointer',
                    fontSize: 10, padding: '0 2px', lineHeight: 1,
                  }}
                  title={locale === 'zh' ? '重命名' : 'Rename'}
                >E</button>
              )}
              {sessions.length > 1 && (
                <button
                  onClick={() => {
                    if (confirm(locale === 'zh' ? `删除会话"${session.name}"?` : `Delete session "${session.name}"?`)) {
                      deleteSession(session.id);
                    }
                  }}
                  style={{
                    border: 'none', background: 'transparent',
                    color: 'var(--text-tertiary)', cursor: 'pointer',
                    fontSize: 12, padding: '0 4px', lineHeight: 1,
                  }}
                  title={locale === 'zh' ? '删除' : 'Delete'}
                >×</button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ─── Messages Area ─── */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        {messages.length === 0 && (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            color: 'var(--text-tertiary)',
          }}>
            <div style={{ fontSize: 36, opacity: 0.3 }}></div>
            <p style={{ fontSize: 14, textAlign: 'center', lineHeight: 1.6 }}>
              Ask me anything about your YOLO dataset.<br />
              I can inspect, convert, train, and analyze.
            </p>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
              width: '100%',
              maxWidth: 280,
            }}>
              {[
                t('chat.suggestion1'),
                t('chat.suggestion2'),
                t('chat.suggestion3'),
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  style={{
                    padding: '8px 12px',
                    border: '1px solid var(--border-primary)',
                    borderRadius: 8,
                    background: 'var(--bg-elevated)',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                    fontSize: 12,
                    textAlign: 'left',
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isAgentRunning && !streamingMessageId && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            color: 'var(--text-tertiary)',
            fontSize: 13,
          }}>
            <span style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: 'var(--accent-primary)',
              animation: 'pulse 1.5s infinite',
            }} />
            {t('chat.agentRunning')}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ─── Permission Prompt ─── */}
      {permissionRequest && (
        <PermissionPrompt
          request={permissionRequest}
          onRespond={handlePermissionResponse}
        />
      )}

      {/* ─── Vertical Resizable Divider (messages ↔ input) ─── */}
      <div
        onMouseDown={(e) => {
          e.preventDefault();
          const startY = e.clientY;
          const startH = inputHeight;
          const onMove = (ev: MouseEvent) => {
            const delta = startY - ev.clientY;
            setInputHeight(Math.max(50, Math.min(300, startH + delta)));
          };
          const onUp = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
          };
          document.addEventListener('mousemove', onMove);
          document.addEventListener('mouseup', onUp);
          document.body.style.cursor = 'row-resize';
          document.body.style.userSelect = 'none';
        }}
        style={{
          height: 4,
          cursor: 'row-resize',
          background: 'transparent',
          borderTop: '1px solid var(--border-primary)',
          flexShrink: 0,
          position: 'relative',
          transition: 'background 0.2s ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--accent-muted)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
      >
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 32, height: 2,
          background: 'var(--border-secondary)',
          borderRadius: 1,
        }} />
      </div>

      {/* ─── Input Area ─── */}
      <div style={{
        padding: '12px 16px',
        background: 'var(--bg-elevated)',
        flexShrink: 0,
        minHeight: inputHeight,
      }}>
        <div style={{
          display: 'flex',
          gap: 8,
          alignItems: 'stretch',
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.placeholder')}
            rows={2}
            style={{
              flex: 1,
              padding: '10px 14px',
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              fontSize: 13,
              fontFamily: 'var(--font-sans)',
              resize: 'none',
              outline: 'none',
              minHeight: 48,
              maxHeight: 120,
              lineHeight: 1.5,
              boxSizing: 'border-box',
            }}
          />
          {isAgentRunning ? (
            <button
              onClick={handleStop}
              style={{
                padding: '8px 12px',
                border: '1px solid var(--error)',
                borderRadius: 8,
                background: 'rgba(244, 67, 54, 0.1)',
                color: 'var(--error)',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {t('chat.stop')}
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              style={{
                padding: '8px 12px',
                border: 'none',
                borderRadius: 8,
                background: input.trim() ? 'var(--accent-primary)' : 'var(--bg-active)',
                color: input.trim() ? '#fff' : 'var(--text-tertiary)',
                cursor: input.trim() ? 'pointer' : 'default',
                fontSize: 12,
                fontWeight: 600,
                transition: 'all 0.15s ease',
              }}
            >
              {t('chat.send')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
