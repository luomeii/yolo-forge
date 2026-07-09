/**
 * Task Manager Panel — Visualize parallel multi-agent tasks
 */

import React, { useState, useEffect } from 'react';
import { useAppStore } from '../../stores/app-store';

export interface AgentTask {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  steps: TaskStep[];
  result?: any;
  error?: string;
  startedAt: number;
  completedAt?: number;
  taskType?: 'training' | 'conversion' | 'inspection' | 'other';
}

interface TaskStep {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  detail?: string;
}

let taskStore: AgentTask[] = [];
const taskListeners: Set<() => void> = new Set();

export function addTask(task: AgentTask) {
  taskStore = [...taskStore, task];
  taskListeners.forEach(l => l());
}

export function updateTask(id: string, updates: Partial<AgentTask>) {
  taskStore = taskStore.map(t => t.id === id ? { ...t, ...updates } : t);
  taskListeners.forEach(l => l());
}

export function removeTask(id: string) {
  taskStore = taskStore.filter(t => t.id !== id);
  taskListeners.forEach(l => l());
}

export function stopTask(id: string) {
  try { window.electronAPI.yolo.stopTrain(); } catch {}
  updateTask(id, { status: 'cancelled', completedAt: Date.now() });
}

export const TaskManagerPanel: React.FC = () => {
  const { locale } = useAppStore();
  const [, forceUpdate] = useState({});

  useEffect(() => {
    const listener = () => forceUpdate({});
    taskListeners.add(listener);
    return () => { taskListeners.delete(listener); };
  }, []);

  const tasks = taskStore;
  const statusColors: Record<string, string> = { pending: 'var(--text-tertiary)', running: 'var(--accent-primary)', completed: 'var(--success)', failed: 'var(--error)', cancelled: 'var(--warning)' };
  const statusLabels: Record<string, { zh: string; en: string }> = { pending: { zh: '等待中', en: 'Pending' }, running: { zh: '运行中', en: 'Running' }, completed: { zh: '已完成', en: 'Completed' }, failed: { zh: '失败', en: 'Failed' }, cancelled: { zh: '已取消', en: 'Cancelled' } };
  const typeLabels: Record<string, { zh: string; en: string }> = { training: { zh: '训练', en: 'Training' }, conversion: { zh: '转换', en: 'Conversion' }, inspection: { zh: '检测', en: 'Inspection' }, other: { zh: '其他', en: 'Other' } };

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
        {locale === 'zh' ? '任务管理' : 'Task Manager'}
      </h2>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>
        {locale === 'zh' ? '查看和管理智能体并行编排的任务。训练任务会自动同步显示在这里。' : 'View and manage agent-orchestrated tasks. Training tasks sync here automatically.'}
      </p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        {(['running', 'completed', 'failed', 'pending'] as const).map(status => {
          const count = tasks.filter(t => t.status === status).length;
          return (
            <div key={status} style={{ flex: 1, padding: 16, background: 'var(--bg-elevated)', borderRadius: 10, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: statusColors[status] }}>{count}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{statusLabels[status][locale === 'zh' ? 'zh' : 'en']}</div>
            </div>
          );
        })}
      </div>

      {tasks.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-tertiary)', background: 'var(--bg-elevated)', borderRadius: 12, border: '1px solid var(--border-primary)' }}>
          <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}></div>
          <div style={{ fontSize: 14 }}>{locale === 'zh' ? '暂无任务。让智能体执行多步任务时将显示在这里。' : 'No tasks yet. Tasks will appear here when the agent executes operations.'}</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {tasks.map(task => (
            <div key={task.id} style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 10, border: '1px solid var(--border-primary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: statusColors[task.status], animation: task.status === 'running' ? 'pulse 1.5s infinite' : 'none' }} />
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', flex: 1 }}>{task.name}</span>
                {task.taskType && <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>{typeLabels[task.taskType]?.[locale === 'zh' ? 'zh' : 'en'] || task.taskType}</span>}
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: `${statusColors[task.status]}20`, color: statusColors[task.status] }}>{statusLabels[task.status][locale === 'zh' ? 'zh' : 'en']}</span>
                <button onClick={() => removeTask(task.id)} style={{ padding: '4px 8px', border: '1px solid var(--border-primary)', borderRadius: 4, background: 'transparent', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 11 }}>×</button>
                {task.status === 'running' && <button onClick={() => stopTask(task.id)} style={{ padding: '4px 10px', border: '1px solid rgba(244,67,54,0.3)', borderRadius: 4, background: 'rgba(244,67,54,0.1)', color: 'var(--error)', cursor: 'pointer', fontSize: 11 }}>{locale === 'zh' ? '停止' : 'Stop'}</button>}
              </div>
              {task.status === 'running' && <div style={{ height: 4, background: 'var(--bg-tertiary)', borderRadius: 2, marginBottom: 12, overflow: 'hidden' }}><div style={{ height: '100%', width: `${task.progress}%`, background: 'var(--accent-primary)', transition: 'width 0.3s ease' }} /></div>}
              {task.steps.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {task.steps.map((step, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                      <span style={{ color: statusColors[step.status], fontSize: 14 }}>{step.status === 'completed' ? '✓' : step.status === 'running' ? '●' : step.status === 'failed' ? '✗' : '○'}</span>
                      <span>{step.name}</span>
                      {step.detail && <span style={{ color: 'var(--text-tertiary)', fontSize: 11 }}>— {step.detail}</span>}
                    </div>
                  ))}
                </div>
              )}
              {task.error && <div style={{ marginTop: 8, padding: 8, fontSize: 12, background: 'rgba(244,67,54,0.08)', borderRadius: 6, color: 'var(--error)' }}>{task.error}</div>}
              {task.result && <div style={{ marginTop: 8, padding: 8, fontSize: 12, background: 'rgba(76,175,80,0.08)', borderRadius: 6, color: 'var(--success)' }}>{typeof task.result === 'string' ? task.result : JSON.stringify(task.result).substring(0, 200)}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
