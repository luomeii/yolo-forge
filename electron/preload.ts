/**
 * Preload Script — Secure IPC bridge between Renderer and Main process
 *
 * Following Codex/Claude Code pattern:
 * - Expose only structured IPC channels via contextBridge
 * - No direct Node.js access from renderer
 * - All agent/tool operations go through IPC
 */

import { contextBridge, ipcRenderer } from 'electron';

const electronAPI = {
  // ─── Agent Operations ───
  agent: {
    sendMessage: (message: string, sessionId?: string) =>
      ipcRenderer.invoke('agent:sendMessage', message, sessionId),

    sendMessageStream: (message: string, sessionId?: string) => {
      const channel = `agent:stream:${Date.now()}`;
      ipcRenderer.send('agent:sendMessageStream', message, sessionId, channel);
      return {
        onToken: (callback: (token: string) => void) => {
          ipcRenderer.on(`${channel}:token`, (_event, token) => callback(token));
        },
        onToolCall: (callback: (toolCall: any) => void) => {
          ipcRenderer.on(`${channel}:toolCall`, (_event, toolCall) => callback(toolCall));
        },
        onToolResult: (callback: (result: any) => void) => {
          ipcRenderer.on(`${channel}:toolResult`, (_event, result) => callback(result));
        },
        onPermissionRequest: (callback: (request: any) => void) => {
          ipcRenderer.on(`${channel}:permission`, (_event, request) => callback(request));
        },
        onComplete: (callback: (response: any) => void) => {
          ipcRenderer.on(`${channel}:complete`, (_event, response) => callback(response));
        },
        onError: (callback: (error: any) => void) => {
          ipcRenderer.on(`${channel}:error`, (_event, error) => callback(error));
        },
        dispose: () => {
          ipcRenderer.removeAllListeners(`${channel}:token`);
          ipcRenderer.removeAllListeners(`${channel}:toolCall`);
          ipcRenderer.removeAllListeners(`${channel}:toolResult`);
          ipcRenderer.removeAllListeners(`${channel}:permission`);
          ipcRenderer.removeAllListeners(`${channel}:complete`);
          ipcRenderer.removeAllListeners(`${channel}:error`);
        },
      };
    },

    stop: (sessionId: string) =>
      ipcRenderer.invoke('agent:stop', sessionId),

    getHistory: (sessionId: string) =>
      ipcRenderer.invoke('agent:getHistory', sessionId),

    listSessions: () =>
      ipcRenderer.invoke('agent:listSessions'),

    createSession: () =>
      ipcRenderer.invoke('agent:createSession'),

    deleteSession: (sessionId: string) =>
      ipcRenderer.invoke('agent:deleteSession', sessionId),

    // Permission response — Codex-style: allow_once / allow_always / deny
    respondPermission: (toolCallId: string, choice: string, toolName?: string, args?: string) =>
      ipcRenderer.send('agent:permissionResponse', toolCallId, choice, toolName, args),
  },

  // ─── Configuration ───
  config: {
    get: (key: string) =>
      ipcRenderer.invoke('config:get', key),

    set: (key: string, value: any) =>
      ipcRenderer.invoke('config:set', key, value),

    getAll: () =>
      ipcRenderer.invoke('config:getAll'),

    testConnection: () =>
      ipcRenderer.invoke('config:testConnection'),
  },

  // ─── YOLO Operations (via Python Worker) ───
  yolo: {
    inspect: (path: string, sampleSize?: number) =>
      ipcRenderer.invoke('yolo:inspect', path, sampleSize),

    convert: (profileYaml: string, dryRun?: boolean) =>
      ipcRenderer.invoke('yolo:convert', profileYaml, dryRun),

    train: (config: any) =>
      ipcRenderer.invoke('yolo:train', config),

    trainProgress: (callback: (progress: any) => void) => {
      ipcRenderer.on('yolo:trainProgress', (_event, progress) => callback(progress));
      return () => ipcRenderer.removeAllListeners('yolo:trainProgress');
    },

    stopTrain: () =>
      ipcRenderer.invoke('yolo:stopTrain'),

    review: (imageDir: string, labelDir: string) =>
      ipcRenderer.invoke('yolo:review', imageDir, labelDir),

    // Conda environment scanning
    listCondaEnvs: () =>
      ipcRenderer.invoke('yolo:listCondaEnvs'),

    // System info scanning (GPU, CUDA)
    getSystemInfo: () =>
      ipcRenderer.invoke('yolo:getSystemInfo'),

    // Check if a conda env has required training packages
    checkEnvPackages: (envName: string) =>
      ipcRenderer.invoke('yolo:checkEnvPackages', envName),

    // Training progress events (real-time)
    onTrainProgress: (callback: (progress: any) => void) => {
      const handler = (_event: any, progress: any) => callback(progress);
      ipcRenderer.on('yolo:trainProgress', handler);
      return () => ipcRenderer.removeListener('yolo:trainProgress', handler);
    },

    // Training completion notification
    onTrainComplete: (callback: (result: any) => void) => {
      const handler = (_event: any, result: any) => callback(result);
      ipcRenderer.on('yolo:trainComplete', handler);
      return () => ipcRenderer.removeListener('yolo:trainComplete', handler);
    },
  },

  // ─── File System (sandboxed) ───
  fs: {
    openDirectory: () =>
      ipcRenderer.invoke('fs:openDirectory'),

    readFile: (filePath: string) =>
      ipcRenderer.invoke('fs:readFile', filePath),

    writeFile: (filePath: string, content: string) =>
      ipcRenderer.invoke('fs:writeFile', filePath, content),

    listFiles: (dirPath: string, pattern?: string) =>
      ipcRenderer.invoke('fs:listFiles', dirPath, pattern),
  },

  // ─── System ───
  system: {
    getVersion: () => ipcRenderer.invoke('system:getVersion'),
    getPlatform: () => process.platform,
  },
};

contextBridge.exposeInMainWorld('electronAPI', electronAPI);

export type ElectronAPI = typeof electronAPI;
