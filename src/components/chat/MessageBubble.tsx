/**
 * Message Bubble — Individual chat message display
 * Clean design, floral theme, no emojis
 * Tool calls are collapsible
 */

import React, { useState } from 'react';
import { ChatMessage } from '../../stores/app-store';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isError = message.isError;

  const getBubbleStyle = (): React.CSSProperties => {
    const base: React.CSSProperties = {
      padding: '10px 14px',
      borderRadius: 'var(--radius-md)',
      fontSize: 13,
      lineHeight: 1.6,
      maxWidth: '100%',
      wordBreak: 'break-word',
      animation: 'fadeIn 0.2s ease-out',
    };

    if (isUser) {
      return {
        ...base,
        background: 'var(--accent-muted)',
        border: '1px solid rgba(124, 179, 66, 0.2)',
        alignSelf: 'flex-end',
      };
    }

    if (isSystem) {
      return {
        ...base,
        background: 'var(--bg-tertiary)',
        border: '1px solid var(--border-primary)',
        fontSize: 11,
        color: 'var(--text-tertiary)',
        padding: '6px 10px',
      };
    }

    if (isError) {
      return {
        ...base,
        background: 'rgba(239, 83, 80, 0.06)',
        border: '1px solid rgba(239, 83, 80, 0.2)',
        color: 'var(--error)',
      };
    }

    // Assistant
    return {
      ...base,
      background: 'var(--bg-elevated)',
      border: '1px solid var(--border-primary)',
      boxShadow: 'var(--shadow-sm)',
    };
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      width: '100%',
    }}>
      <div style={{
        fontSize: 10,
        color: 'var(--text-tertiary)',
        marginBottom: 3,
        fontWeight: 500,
      }}>
        {isUser ? 'You' : isSystem ? 'System' : 'Agent'}
      </div>

      <div style={getBubbleStyle()}>
        {message.isStreaming && (
          <span style={{
            display: 'inline-block',
            width: 6, height: 14,
            background: 'var(--accent-primary)',
            marginLeft: 2,
            animation: 'pulse 0.8s infinite',
            verticalAlign: 'middle',
          }} />
        )}

        <div style={{ whiteSpace: 'pre-wrap' }}>
          <RenderedContent content={message.content} />
        </div>

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div style={{ marginTop: 8 }}>
            {message.toolCalls.map((tc: any, idx: number) => (
              <ToolCallBadge key={idx} toolCall={tc} expanded={isExpanded} onToggle={() => setIsExpanded(!isExpanded)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const RenderedContent: React.FC<{ content: string }> = ({ content }) => {
  if (!content) return null;
  const paragraphs = content.split('\n\n');

  return (
    <>
      {paragraphs.map((paragraph, i) => {
        if (paragraph.startsWith('```') && paragraph.endsWith('```')) {
          const lines = paragraph.split('\n');
          const lang = lines[0].replace('```', '').trim();
          const code = lines.slice(1, -1).join('\n');
          return (
            <pre key={i} style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-sm)',
              padding: 12,
              marginTop: 8, marginBottom: 8,
              fontSize: 12, overflowX: 'auto',
            }}>
              {lang && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase' }}>{lang}</div>}
              <code>{code}</code>
            </pre>
          );
        }
        return <p key={i} style={{ marginBottom: i < paragraphs.length - 1 ? 8 : 0 }}><RichText text={paragraph} /></p>;
      })}
    </>
  );
};

const RichText: React.FC<{ text: string }> = ({ text }) => {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return <code key={i} style={{ background: 'var(--bg-tertiary)', padding: '1px 4px', borderRadius: 3, fontSize: 12 }}>{part.slice(1, -1)}</code>;
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
};

const ToolCallBadge: React.FC<{ toolCall: any; expanded: boolean; onToggle: () => void }> = ({ toolCall, expanded, onToggle }) => {
  return (
    <div style={{
      marginTop: 4,
      border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-sm)',
      overflow: 'hidden',
      background: 'var(--bg-tertiary)',
    }}>
      <button
        onClick={onToggle}
        style={{
          width: '100%', padding: '5px 10px', border: 'none',
          background: 'transparent', color: 'var(--text-secondary)',
          cursor: 'pointer', fontSize: 11, textAlign: 'left',
          display: 'flex', alignItems: 'center', gap: 6,
        }}
      >
        <span style={{
          width: 16, height: 16, borderRadius: 3,
          background: 'var(--accent-primary)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 9, fontWeight: 700,
        }}>T</span>
        <span style={{ fontWeight: 600 }}>{toolCall.name ?? toolCall.toolName}</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)' }}>{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div style={{
          padding: 8, background: 'var(--bg-secondary)',
          fontSize: 11, fontFamily: 'var(--font-mono)',
          maxHeight: 200, overflow: 'auto',
        }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {toolCall.arguments ?? JSON.stringify(toolCall, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
