/**
 * Zustand Store — Global application state
 */

import { create } from 'zustand';
import { Locale, setLocale as setI18nLocale } from '../i18n';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  toolCalls?: any[];
  toolCallId?: string;
  isError?: boolean;
  timestamp: number;
  isStreaming?: boolean;
}

export interface Session {
  id: string;
  name: string;
  messages: ChatMessage[];
  workingDirectory?: string;
  createdAt: number;
  updatedAt: number;
}

export interface AgentConfig {
  provider: 'openai' | 'anthropic';
  model: string;
  apiKey: string;
  baseUrl?: string;
  temperature: number;
  maxTokens: number;
  contextLength?: number;
}

export interface AppState {
  // ─── Sessions ───
  sessions: Session[];
  activeSessionId: string | null;
  createSession: () => string;
  deleteSession: (id: string) => void;
  setActiveSession: (id: string) => void;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => void;
  clearMessages: (sessionId: string) => void;
  loadSessions: (sessions: Session[]) => void;
  renameSession: (id: string, name: string) => void;

  // ─── Agent State ───
  isAgentRunning: boolean;
  currentToolCall: any | null;
  permissionRequest: any | null;
  setAgentRunning: (running: boolean) => void;
  setCurrentToolCall: (toolCall: any | null) => void;
  setPermissionRequest: (request: any | null) => void;

  // ─── UI State ───
  activePanel: 'chat' | 'inspector' | 'converter' | 'trainer' | 'reviewer' | 'tasks' | 'settings';
  sidebarCollapsed: boolean;
  setActivePanel: (panel: AppState['activePanel']) => void;
  toggleSidebar: () => void;

  // ─── Config ───
  agentConfig: AgentConfig;
  updateAgentConfig: (config: Partial<AgentConfig>) => void;

  // ─── Language ───
  locale: Locale;
  setLocale: (locale: Locale) => void;

  // ─── YOLO State ───
  inspectionResult: any | null;
  trainingJob: any | null;
  setInspectionResult: (result: any) => void;
  setTrainingJob: (job: any) => void;

  // ─── Reviewer State (persists across panel switches) ───
  reviewerState: {
    imageDir: string;
    labelDir: string;
    classes: string[];
    started: boolean;
    images: string[];
    currentIndex: number;
  };
  setReviewerState: (state: Partial<AppState['reviewerState']>) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  // ─── Sessions ───
  sessions: [],
  activeSessionId: null,

  createSession: () => {
    const id = `session_${Date.now()}`;
    const session: Session = {
      id,
      name: `Session ${get().sessions.length + 1}`,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSessionId: id,
    }));
    return id;
  },

  deleteSession: (id) => {
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
      activeSessionId: state.activeSessionId === id
        ? (state.sessions.find((s) => s.id !== id)?.id ?? null)
        : state.activeSessionId,
    }));
  },

  setActiveSession: (id) => set({ activeSessionId: id }),

  addMessage: (sessionId, message) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? { ...s, messages: [...s.messages, message], updatedAt: Date.now() }
          : s
      ),
    }));
  },

  updateMessage: (sessionId, messageId, updates) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.id === messageId ? { ...m, ...updates } : m
              ),
            }
          : s
      ),
    }));
  },

  clearMessages: (sessionId) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId ? { ...s, messages: [], updatedAt: Date.now() } : s
      ),
    }));
  },

  loadSessions: (loadedSessions) => {
    set((state) => {
      // Merge: keep existing sessions, add loaded ones that don't exist
      const existingIds = new Set(state.sessions.map(s => s.id));
      const newOnes = loadedSessions.filter(s => !existingIds.has(s.id));
      const allSessions = [...state.sessions, ...newOnes];
      return {
        sessions: allSessions,
        activeSessionId: state.activeSessionId ?? allSessions[0]?.id ?? null,
      };
    });
  },

  renameSession: (id, name) => {
    set((state) => ({
      sessions: state.sessions.map(s =>
        s.id === id ? { ...s, name, updatedAt: Date.now() } : s
      ),
    }));
  },

  // ─── Agent State ───
  isAgentRunning: false,
  currentToolCall: null,
  permissionRequest: null,

  setAgentRunning: (running) => set({ isAgentRunning: running }),
  setCurrentToolCall: (toolCall) => set({ currentToolCall: toolCall }),
  setPermissionRequest: (request) => set({ permissionRequest: request }),

  // ─── UI State ───
  activePanel: 'chat',
  sidebarCollapsed: false,

  setActivePanel: (panel) => set({ activePanel: panel }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  // ─── Config ───
  agentConfig: {
    provider: 'openai',
    model: 'gpt-4o',
    apiKey: '',
    baseUrl: '',
    temperature: 0.3,
    maxTokens: 4096,
  },

  updateAgentConfig: (config) =>
    set((state) => ({
      agentConfig: { ...state.agentConfig, ...config },
    })),

  locale: 'zh',
  setLocale: (locale) => {
    setI18nLocale(locale);
    set({ locale });
  },

  // ─── YOLO State ───
  inspectionResult: null,
  trainingJob: null,

  setInspectionResult: (result) => set({ inspectionResult: result }),
  setTrainingJob: (job) => set({ trainingJob: job }),

  // ─── Reviewer State ───
  reviewerState: {
    imageDir: '',
    labelDir: '',
    classes: ['defect', 'scratch', 'oil', 'face', 'line', 'person', 'car', 'dog'],
    started: false,
    images: [],
    currentIndex: 0,
  },
  setReviewerState: (newState) =>
    set((state) => ({ reviewerState: { ...state.reviewerState, ...newState } })),
}));
