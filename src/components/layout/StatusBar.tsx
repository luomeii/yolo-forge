/**
 * Status Bar — bottom status bar
 */

import React from 'react';
import { useAppStore } from '../../stores/app-store';

export const StatusBar: React.FC = () => {
  const isAgentRunning = useAppStore((s) => s.isAgentRunning);
  const agentConfig = useAppStore((s) => s.agentConfig);
  const activeSessionId = useAppStore((s) => s.activeSessionId);
  const locale = useAppStore((s) => s.locale);

  return (
    <div style={{
      height: 'var(--statusbar-height)',
      minHeight: 28,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 12px',
      background: 'var(--bg-elevated)',
      borderTop: '1px solid var(--border-primary)',
      fontSize: 11,
      color: 'var(--text-tertiary)',
      userSelect: 'none',
    }}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: isAgentRunning ? 'var(--success)' : 'var(--text-tertiary)',
            animation: isAgentRunning ? 'pulse 2s infinite' : 'none',
          }} />
          {isAgentRunning ? (locale === 'zh' ? '运行中' : 'Running') : (locale === 'zh' ? '就绪' : 'Ready')}
        </span>
        <span>{agentConfig.provider.toUpperCase()}</span>
        <span>{agentConfig.model}</span>
      </div>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        <span>YOLO-Forge SP v3.0.0</span>
      </div>
    </div>
  );
};
