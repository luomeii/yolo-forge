/**
 * Type declarations for the Electron API bridge
 */

export interface ElectronAPI {
  agent: {
    sendMessage: (message: string, sessionId?: string) => Promise<any>;
    sendMessageStream: (message: string, sessionId?: string) => {
      onToken: (callback: (token: string) => void) => void;
      onToolCall: (callback: (toolCall: any) => void) => void;
      onToolResult: (callback: (result: any) => void) => void;
      onPermissionRequest: (callback: (request: any) => void) => void;
      onComplete: (callback: (response: any) => void) => void;
      onError: (callback: (error: any) => void) => void;
      dispose: () => void;
    };
    stop: (sessionId: string) => Promise<any>;
    getHistory: (sessionId: string) => Promise<any>;
    listSessions: () => Promise<any>;
    createSession: () => Promise<any>;
    deleteSession: (sessionId: string) => Promise<any>;
    respondPermission: (toolCallId: string, choice: string, toolName?: string, args?: string) => void;
  };
  config: {
    get: (key: string) => Promise<any>;
    set: (key: string, value: any) => Promise<any>;
    getAll: () => Promise<any>;
    testConnection: () => Promise<any>;
    fetchModels: (config: any) => Promise<any>;
  };
  yolo: {
    inspect: (path: string, sampleSize?: number) => Promise<any>;
    convert: (profileYaml: string, dryRun?: boolean) => Promise<any>;
    train: (config: any) => Promise<any>;
    trainProgress: (callback: (progress: any) => void) => () => void;
    stopTrain: () => Promise<any>;
    review: (imageDir: string, labelDir: string) => Promise<any>;
    listCondaEnvs: () => Promise<{ envs: Array<{ name: string; path: string }>; error?: string }>;
    getSystemInfo: () => Promise<{ gpus: Array<{ name: string; driver: string; memory: string }>; cuda: string | null; error?: string }>;
    checkEnvPackages: (envName: string) => Promise<{ packages: Record<string, string>; missing: string[]; ready: boolean; error?: string }>;
    onTrainProgress: (callback: (progress: any) => void) => () => void;
    onTrainComplete: (callback: (result: any) => void) => () => void;
  };
  fs: {
    openDirectory: () => Promise<string | null>;
    readFile: (filePath: string) => Promise<any>;
    writeFile: (filePath: string, content: string) => Promise<any>;
    listFiles: (dirPath: string, pattern?: string) => Promise<any>;
  };
  system: {
    getVersion: () => Promise<string>;
    getPlatform: () => string;
  };
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

export {};
