/**
 * Title Bar — minimal, clean header with subtle branding
 */

import React from 'react';

export const TitleBar: React.FC = () => {
  return (
    <div style={{
      height: 'var(--header-height)',
      minHeight: 48,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-elevated)',
      borderBottom: '1px solid var(--border-primary)',
      WebkitAppRegion: 'drag' as any,
      userSelect: 'none',
      position: 'relative',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: 'var(--accent-primary)',
        }} />
        <span style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text-secondary)',
          letterSpacing: '0.5px',
        }}>
          YOLO-Forge SP
        </span>
      </div>
    </div>
  );
};
