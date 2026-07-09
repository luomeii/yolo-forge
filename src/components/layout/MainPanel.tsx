/**
 * Main Panel — Center area that switches between panels
 * Supports i18n + all panels including Reviewer and TaskManager
 */

import React from 'react';
import { useAppStore } from '../../stores/app-store';
import { InspectorPanel } from '../panels/InspectorPanel';
import { ConverterPanel } from '../panels/ConverterPanel';
import { TrainerPanel } from '../panels/TrainerPanel';
import { SettingsPanel } from '../panels/SettingsPanel';
import { ReviewerPanel } from '../panels/ReviewerPanel';
import { TaskManagerPanel } from '../panels/TaskManagerPanel';
import { t } from '../../i18n';

export const MainPanel: React.FC = () => {
  const activePanel = useAppStore((s) => s.activePanel);
  const setActivePanel = useAppStore((s) => s.setActivePanel);
  const locale = useAppStore((s) => s.locale);

  console.log(`MainPanel render, locale=${locale}, active=${activePanel}`);

  const renderPanel = () => {
    switch (activePanel) {
      case 'chat': return <ChatPlaceholder onNavigate={setActivePanel} />;
      case 'inspector': return <InspectorPanel />;
      case 'converter': return <ConverterPanel />;
      case 'trainer': return <TrainerPanel />;
      case 'reviewer': return <ReviewerPanel />;
      case 'tasks': return <TaskManagerPanel />;
      case 'settings': return <SettingsPanel />;
      default: return <ChatPlaceholder onNavigate={setActivePanel} />;
    }
  };

  return (
    <div style={{ flex: 1, height: '100%', overflow: 'auto', background: 'var(--bg-primary)' }}>
      {renderPanel()}
    </div>
  );
};

interface ChatPlaceholderProps {
  onNavigate: (panel: any) => void;
}

const ChatPlaceholder: React.FC<ChatPlaceholderProps> = ({ onNavigate }) => {
  const actions: { labelKey: string; panel: any; icon: string }[] = [
    { labelKey: 'main.action1', panel: 'inspector', icon: 'I' },
    { labelKey: 'main.action2', panel: 'converter', icon: 'F' },
    { labelKey: 'main.action3', panel: 'trainer', icon: 'T' },
  ];

  return (
    <div className="floral-bg gold-silk-bg gold-corner" style={{
      height: '100%', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 20,
      color: 'var(--text-tertiary)', padding: 40, position: 'relative', overflow: 'hidden',
    }}>
      {/* Decorative SVG leaf ornaments — herbal vine pattern */}
      <svg className="leaf-decoration" style={{ top: '8%', right: '5%', width: 220, height: 220 }} viewBox="0 0 100 100" fill="none">
        <path d="M50 10 C 30 30, 20 50, 50 90 C 80 50, 70 30, 50 10 Z" fill="var(--accent-primary)" />
        <path d="M50 10 L 50 90" stroke="var(--accent-deep)" strokeWidth="0.3" />
        <path d="M50 30 C 40 35, 35 40, 50 50" stroke="var(--accent-primary)" strokeWidth="0.2" fill="none" opacity="0.5" />
        <path d="M50 30 C 60 35, 65 40, 50 50" stroke="var(--accent-primary)" strokeWidth="0.2" fill="none" opacity="0.5" />
        <path d="M50 50 C 40 55, 35 60, 50 70" stroke="var(--accent-primary)" strokeWidth="0.2" fill="none" opacity="0.5" />
        <path d="M50 50 C 60 55, 65 60, 50 70" stroke="var(--accent-primary)" strokeWidth="0.2" fill="none" opacity="0.5" />
      </svg>
      <svg className="leaf-decoration" style={{ bottom: '8%', left: '5%', width: 180, height: 180, transform: 'rotate(180deg)' }} viewBox="0 0 100 100" fill="none">
        <path d="M50 10 C 30 30, 20 50, 50 90 C 80 50, 70 30, 50 10 Z" fill="var(--accent-deep)" />
        <path d="M50 10 L 50 90" stroke="var(--accent-primary)" strokeWidth="0.3" />
      </svg>
      {/* Small decorative vine at top center */}
      <svg style={{ position: 'absolute', top: '15%', left: '50%', transform: 'translateX(-50%)', width: 120, height: 40, opacity: 0.06 }} viewBox="0 0 120 40" fill="none">
        <path d="M10 20 Q 30 5, 60 20 T 110 20" stroke="var(--accent-deep)" strokeWidth="0.8" fill="none" />
        <circle cx="30" cy="12" r="2" fill="var(--accent-primary)" />
        <circle cx="60" cy="20" r="2" fill="var(--accent-primary)" />
        <circle cx="90" cy="12" r="2" fill="var(--accent-primary)" />
      </svg>

      {/* Logo circle with gold ring */}
      <div style={{
        width: 80, height: 80, borderRadius: '50%',
        background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-deep))',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: '0 8px 32px rgba(124, 179, 66, 0.3), inset 0 1px 0 rgba(255,255,255,0.2)',
        position: 'relative',
      }}>
        <span style={{ fontSize: 32, fontWeight: 700, color: '#fff', textShadow: '0 1px 2px rgba(0,0,0,0.1)' }}>Y</span>
        {/* Gold ring */}
        <div style={{
          position: 'absolute', inset: -6, borderRadius: '50%',
          border: '1px solid rgba(193, 168, 100, 0.3)',
          boxShadow: '0 0 0 1px rgba(193, 168, 100, 0.1)',
        }} />
        <div style={{
          position: 'absolute', inset: -12, borderRadius: '50%',
          border: '1px solid rgba(193, 168, 100, 0.15)',
        }} />
      </div>

      <h2 style={{
        fontSize: 26, fontWeight: 700, color: 'var(--text-primary)',
        letterSpacing: 2, textShadow: '0 1px 0 rgba(255,255,255,0.5)',
      }}>
        {t('main.title')}
      </h2>

      {/* Decorative gradient separator with gold accent */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, width: 200,
      }}>
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, rgba(193, 168, 100, 0.3))' }} />
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'rgba(193, 168, 100, 0.4)' }} />
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(193, 168, 100, 0.3), transparent)' }} />
      </div>

      <p style={{ fontSize: 14, maxWidth: 480, textAlign: 'center', lineHeight: 1.9, color: 'var(--text-secondary)' }}>
        {t('main.desc')}
      </p>

      <div style={{ display: 'flex', gap: 12, marginTop: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
        {actions.map((action) => (
          <button
            key={action.labelKey}
            onClick={() => onNavigate(action.panel)}
            className="btn-secondary herbal-border"
            style={{
              padding: '12px 22px', display: 'flex', alignItems: 'center', gap: 10,
              fontSize: 13, position: 'relative',
            }}
          >
            <div style={{
              width: 26, height: 26, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent-muted), rgba(193, 168, 100, 0.1))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: 'var(--accent-deep)',
              border: '1px solid rgba(193, 168, 100, 0.15)',
            }}>{action.icon}</div>
            {t(action.labelKey)}
          </button>
        ))}
      </div>

      {/* Decorative gold-pressed corner ornaments */}
      <div style={{ position: 'absolute', top: 16, left: 16, width: 40, height: 40, borderTop: '1px solid rgba(193, 168, 100, 0.25)', borderLeft: '1px solid rgba(193, 168, 100, 0.25)', borderRadius: 'var(--radius-sm) 0 0 0' }} />
      <div style={{ position: 'absolute', top: 16, right: 16, width: 40, height: 40, borderTop: '1px solid rgba(193, 168, 100, 0.25)', borderRight: '1px solid rgba(193, 168, 100, 0.25)', borderRadius: '0 var(--radius-sm) 0 0' }} />
      <div style={{ position: 'absolute', bottom: 16, left: 16, width: 40, height: 40, borderBottom: '1px solid rgba(193, 168, 100, 0.25)', borderLeft: '1px solid rgba(193, 168, 100, 0.25)', borderRadius: '0 0 0 var(--radius-sm)' }} />
      <div style={{ position: 'absolute', bottom: 16, right: 16, width: 40, height: 40, borderBottom: '1px solid rgba(193, 168, 100, 0.25)', borderRight: '1px solid rgba(193, 168, 100, 0.25)', borderRadius: '0 0 var(--radius-sm) 0' }} />
    </div>
  );
};
