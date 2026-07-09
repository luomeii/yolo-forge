/**
 * Permission Prompt — Codex-style 3 options
 * Clean design without emojis, floral theme
 */

import React, { useState } from 'react';

interface PermissionPromptProps {
  request: {
    toolName: string;
    arguments: string;
    toolCallId: string;
    description: string;
    risk: 'low' | 'medium' | 'high';
  };
  onRespond: (choice: 'allow_once' | 'allow_always' | 'deny') => void;
}

export const PermissionPrompt: React.FC<PermissionPromptProps> = ({ request, onRespond }) => {
  const riskColors = {
    low: 'var(--success)',
    medium: 'var(--warning)',
    high: 'var(--error)',
  };

  const riskLabels = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
  };

  const commandPreview = (() => {
    if (request.toolName !== 'shell') return null;
    try {
      const args = JSON.parse(request.arguments);
      return args.command || null;
    } catch {
      return null;
    }
  })();

  return (
    <div style={{
      padding: '12px 16px',
      background: 'var(--bg-elevated)',
      borderTop: `2px solid ${riskColors[request.risk]}`,
      boxShadow: 'var(--shadow-md)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{
          width: 20, height: 20, borderRadius: '50%',
          background: riskColors[request.risk],
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 12, fontWeight: 700,
        }}>!</div>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
          权限请求
        </span>
        <span style={{
          padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontSize: 10, fontWeight: 600,
          background: `${riskColors[request.risk]}20`, color: riskColors[request.risk],
        }}>
          {riskLabels[request.risk]}
        </span>
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
        <strong>{request.toolName}</strong> — {request.description.substring(0, 80)}
      </div>

      {commandPreview && (
        <div style={{
          padding: 8, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
          fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
          marginBottom: 12, overflow: 'auto', maxHeight: 60,
        }}>
          <span style={{ color: 'var(--text-tertiary)' }}>$ </span>{commandPreview}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button onClick={() => onRespond('deny')} style={{
          padding: '6px 14px', border: `1px solid ${riskColors.high}30`,
          borderRadius: 'var(--radius-sm)', background: `${riskColors.high}10`,
          color: riskColors.high, cursor: 'pointer', fontSize: 12, fontWeight: 500,
        }}>
          拒绝
        </button>
        <button onClick={() => onRespond('allow_once')} style={{
          padding: '6px 14px', border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)',
          color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12, fontWeight: 500,
        }}>
          本次允许
        </button>
        <button onClick={() => onRespond('allow_always')} style={{
          padding: '6px 14px', border: 'none', borderRadius: 'var(--radius-sm)',
          background: 'var(--accent-primary)', color: '#fff',
          cursor: 'pointer', fontSize: 12, fontWeight: 600,
        }}>
          始终允许
        </button>
      </div>
    </div>
  );
};
