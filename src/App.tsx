/**
 * App — Main Application Component
 * With resizable dividers between panels
 */

import React, { useEffect, useState } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { MainPanel } from './components/layout/MainPanel';
import { ChatPanel } from './components/chat/ChatPanel';
import { StatusBar } from './components/layout/StatusBar';
import { TitleBar } from './components/layout/TitleBar';
import { ResizableDivider } from './components/layout/ResizableDivider';
import { useAppStore } from './stores/app-store';
import { addTask, updateTask } from './components/panels/TaskManagerPanel';

export const App: React.FC = () => {
  const { createSession, sessions, updateAgentConfig, setLocale, locale, loadSessions, setActiveSession } = useAppStore();
  const [chatWidth, setChatWidth] = useState(420);

  useEffect(() => {
    // Load saved agent config
    window.electronAPI.config.get('agent').then((saved: any) => {
      if (saved && saved.apiKey) {
        updateAgentConfig(saved);
        window.electronAPI.config.set('agent', saved).catch(() => {});
      }
    }).catch(() => {});

    // Load saved locale
    window.electronAPI.config.get('locale').then((savedLocale: any) => {
      if (savedLocale === 'zh' || savedLocale === 'en') setLocale(savedLocale);
    }).catch(() => {});

    // Load saved sessions from disk — only load sessions with messages, max 5
    window.electronAPI.agent.listSessions().then((savedSessions: any[]) => {
      // Only load sessions that have actual messages
      const withMessages = (savedSessions || [])
        .filter((s: any) => s.messageCount && s.messageCount > 0)
        .slice(0, 5);

      if (withMessages.length > 0) {
        const loaded = withMessages.map((s: any, i: number) => ({
          id: s.id,
          name: s.name || `Session ${i + 1}`,
          messages: [],
          workingDirectory: s.workingDirectory,
          createdAt: s.createdAt,
          updatedAt: s.updatedAt,
        }));
        loadSessions(loaded);
        setActiveSession(loaded[0].id);
      } else {
        // No sessions with messages — create exactly ONE fresh session
        createSession();
      }
    }).catch(() => {
      // If listSessions fails, create one fresh session
      if (sessions.length === 0) createSession();
    });

    // Global training event listeners
    const removeProgress = (window.electronAPI.yolo as any).onTrainProgress?.((progress: any) => {
      if (progress.task_id) {
        updateTask(progress.task_id, {
          status: 'running',
          progress: progress.percent || 0,
          taskType: 'training',
          steps: [
            { name: locale === 'zh' ? '初始化' : 'Init', status: 'completed' },
            { name: locale === 'zh' ? '加载' : 'Load', status: 'completed' },
            { name: `${locale === 'zh' ? '训练' : 'Training'} (${progress.epoch || 0}/${progress.total_epochs || '?'})`, status: 'running', detail: progress.log },
            { name: locale === 'zh' ? '验证' : 'Validation', status: 'pending' },
            { name: locale === 'zh' ? '导出' : 'Export', status: 'pending' },
          ],
        });
      }
    });

    const removeComplete = (window.electronAPI.yolo as any).onTrainComplete?.((result: any) => {
      if (result.task_id) {
        updateTask(result.task_id, {
          status: result.error ? 'failed' : 'completed',
          progress: 100,
          result,
          error: result.error,
          completedAt: Date.now(),
        });
      }
      if (window.Notification) {
        if (result.error) {
          new Notification('YOLO-Forge SP', { body: `${locale === 'zh' ? '训练失败' : 'Failed'}: ${result.error}` });
        } else {
          new Notification('YOLO-Forge SP', { body: `${locale === 'zh' ? '训练完成' : 'Complete'}: ${result.results_dir || ''}` });
        }
      }
    });

    return () => { removeProgress?.(); removeComplete?.(); };
  }, []);

  const handleChatResize = (delta: number) => {
    setChatWidth(w => Math.max(380, Math.min(700, w - delta)));
  };

  return (
    <div className="app-container floral-bg" style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      width: '100vw',
      background: 'var(--bg-primary)',
    }}>
      <TitleBar />
      <div className="app-body" style={{
        display: 'flex',
        flex: 1,
        overflow: 'hidden',
      }}>
        <Sidebar />
        <MainPanel />
        <ResizableDivider onResize={handleChatResize} />
        <div style={{ flex: `0 0 ${chatWidth}px`, display: 'flex', minHeight: 0 }}>
          <ChatPanel />
        </div>
      </div>
      <StatusBar />
    </div>
  );
};
