/**
 * Sidebar — Left navigation with text labels
 * Supports i18n + all panels including Reviewer and TaskManager
 */

import React from 'react';
import { useAppStore } from '../../stores/app-store';
import { t } from '../../i18n';

interface NavItem {
  id: string;
  labelKey: string;
  icon: string;
  panel: any;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', labelKey: 'nav.chat', icon: 'C', panel: 'chat' },
  { id: 'inspector', labelKey: 'nav.inspector', icon: 'I', panel: 'inspector' },
  { id: 'converter', labelKey: 'nav.converter', icon: 'F', panel: 'converter' },
  { id: 'trainer', labelKey: 'nav.trainer', icon: 'T', panel: 'trainer' },
  { id: 'reviewer', labelKey: 'nav.reviewer', icon: 'R', panel: 'reviewer' },
  { id: 'tasks', labelKey: 'nav.tasks', icon: 'M', panel: 'tasks' },
  { id: 'settings', labelKey: 'nav.settings', icon: 'S', panel: 'settings' },
];

export const Sidebar: React.FC = () => {
  const activePanel = useAppStore((s) => s.activePanel);
  const setActivePanel = useAppStore((s) => s.setActivePanel);
  const locale = useAppStore((s) => s.locale);

  console.log(`Sidebar render, locale=${locale}, active=${activePanel}`);

  return (
    <div style={{
      width: 72, minWidth: 72, height: '100%',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-primary)',
      paddingTop: 12, gap: 4, overflowY: 'auto',
    }}>
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          onClick={() => setActivePanel(item.panel)}
          title={t(item.labelKey)}
          style={{
            width: 56, height: 56,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
            border: 'none', borderRadius: 'var(--radius-md)', cursor: 'pointer', transition: 'all 0.2s ease',
            background: activePanel === item.panel ? 'var(--accent-muted)' : 'transparent',
          }}
          onMouseEnter={(e) => { if (activePanel !== item.panel) { e.currentTarget.style.background = 'var(--bg-hover)'; } }}
          onMouseLeave={(e) => { if (activePanel !== item.panel) { e.currentTarget.style.background = 'transparent'; } }}
        >
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 700,
            background: activePanel === item.panel ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
            color: activePanel === item.panel ? '#fff' : 'var(--text-secondary)',
            transition: 'all 0.2s ease',
          }}>{item.icon}</div>
          <span style={{ fontSize: 9, lineHeight: 1, color: activePanel === item.panel ? 'var(--accent-deep)' : 'var(--text-tertiary)' }}>{t(item.labelKey)}</span>
        </button>
      ))}
      <div style={{ flex: 1 }} />
    </div>
  );
};
