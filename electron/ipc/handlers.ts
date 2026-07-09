/**
 * IPC Handlers — Bridge between Electron main process and renderer
 *
 * All agent operations flow through these handlers.
 * Following the Electron security model: contextIsolation=true, nodeIntegration=false
 */

import { BrowserWindow, ipcMain, dialog, shell } from 'electron';
import { AgentOrchestrator } from '../agent/orchestrator';
import { PythonWorkerManager } from '../workers/python-manager';
import { Store } from '../store';

export function registerIpcHandlers(
  mainWindow: BrowserWindow,
  orchestrator: AgentOrchestrator,
  pythonManager: PythonWorkerManager,
  store: Store
): void {
  // ─── Agent Operations ───

  ipcMain.handle('agent:sendMessage', async (_event, message: string, sessionId?: string) => {
    const sid = sessionId ?? `session_${Date.now()}`;
    const events = await orchestrator.run(message, sid);
    return { sessionId: sid, events };
  });

  ipcMain.on('agent:sendMessageStream', (_event, message: string, sessionId: string, channel: string) => {
    const sid = sessionId ?? `session_${Date.now()}`;
    const controller = new AbortController();

    (async () => {
      try {
        for await (const event of orchestrator.runAgentLoop(message, sid, controller.signal)) {
          if (mainWindow.isDestroyed()) break;

          switch (event.type) {
            case 'text_delta':
              mainWindow.webContents.send(`${channel}:token`, event.text);
              break;
            case 'tool_call':
              mainWindow.webContents.send(`${channel}:toolCall`, event);
              break;
            case 'tool_result':
              mainWindow.webContents.send(`${channel}:toolResult`, event);
              break;
            case 'permission_request':
              mainWindow.webContents.send(`${channel}:permission`, event);
              break;
            case 'agent_complete':
              mainWindow.webContents.send(`${channel}:complete`, event);
              break;
            case 'llm_error':
            case 'tool_error':
              mainWindow.webContents.send(`${channel}:error`, event);
              break;
          }
        }
      } catch (error: any) {
        if (!mainWindow.isDestroyed()) {
          mainWindow.webContents.send(`${channel}:error`, { error: error.message });
        }
      }
    })();
  });

  ipcMain.handle('agent:stop', async (_event, sessionId: string) => {
    orchestrator.stop(sessionId);
    return { stopped: true };
  });

  ipcMain.handle('agent:getHistory', async (_event, sessionId: string) => {
    return { messages: [] };
  });

  ipcMain.handle('agent:listSessions', async () => {
    return orchestrator.listSessions();
  });

  ipcMain.handle('agent:createSession', async () => {
    return orchestrator.createSession();
  });

  ipcMain.handle('agent:deleteSession', async (_event, sessionId: string) => {
    await orchestrator.deleteSession(sessionId);
    return { deleted: true };
  });

  // ─── Permission Responses (Codex-style: allow_once / allow_always / deny) ───

  ipcMain.on('agent:permissionResponse', (_event, toolCallId: string, choice: string, toolName?: string, args?: string) => {
    console.log(`[IPC] permissionResponse: toolCallId=${toolCallId}, choice=${choice}, toolName=${toolName}`);
    orchestrator.respondPermission(toolCallId, choice, toolName, args);
  });

  // ─── Configuration ───

  ipcMain.handle('config:get', async (_event, key: string) => {
    return store.get(key);
  });

  ipcMain.handle('config:set', async (_event, key: string, value: any) => {
    await store.set(key, value);
    if (key === 'agent') {
      orchestrator.updateProviderConfig(value);
    }
    return { saved: true };
  });

  ipcMain.handle('config:getAll', async () => {
    return store.getAll();
  });

  ipcMain.handle('config:testConnection', async () => {
    try {
      const agentConfig = await store.get('agent');
      if (!agentConfig?.apiKey) {
        return { success: false, message: 'API key not configured' };
      }
      // Test by making a minimal API call
      const provider = agentConfig.provider || 'openai';
      if (provider === 'openai') {
        const OpenAI = (await import('openai')).default;
        const client = new OpenAI({
          apiKey: agentConfig.apiKey,
          baseURL: agentConfig.baseUrl || undefined,
        });
        await client.chat.completions.create({
          model: agentConfig.model || 'gpt-4o-mini',
          messages: [{ role: 'user', content: 'Hi' }],
          max_tokens: 5,
        });
        return { success: true, message: `Connected to OpenAI (${agentConfig.model || 'gpt-4o-mini'})` };
      } else {
        const Anthropic = (await import('@anthropic-ai/sdk')).default;
        const client = new Anthropic({
          apiKey: agentConfig.apiKey,
        });
        await client.messages.create({
          model: agentConfig.model || 'claude-sonnet-4-20250514',
          max_tokens: 5,
          messages: [{ role: 'user', content: 'Hi' }],
        });
        return { success: true, message: `Connected to Anthropic (${agentConfig.model || 'claude-sonnet-4-20250514'})` };
      }
    } catch (error: any) {
      return { success: false, message: error.message || 'Connection failed' };
    }
  });

  // ─── YOLO Operations ───

  ipcMain.handle('yolo:inspect', async (_event, path: string, sampleSize?: number) => {
    return pythonManager.execute('inspect', { path, sample_size: sampleSize ?? 5 });
  });

  ipcMain.handle('yolo:convert', async (_event, profileYaml: string, dryRun?: boolean) => {
    return pythonManager.execute('convert', { profile_yaml: profileYaml, dry_run: dryRun ?? true });
  });

  ipcMain.handle('yolo:train', async (_event, config: any) => {
    return pythonManager.execute('train', config);
  });

  ipcMain.handle('yolo:stopTrain', async () => {
    return pythonManager.execute('stop_train', {});
  });

  ipcMain.handle('yolo:review', async (_event, imageDir: string, labelDir: string) => {
    return pythonManager.execute('review', { image_dir: imageDir, label_dir: labelDir });
  });

  // Conda environment scanning
  ipcMain.handle('yolo:listCondaEnvs', async () => {
    try {
      const { exec } = await import('child_process');
      return new Promise((resolve) => {
        exec('conda env list', { timeout: 10000 }, (error, stdout) => {
          if (error) { resolve({ error: error.message, envs: [] }); return; }
          const envs: any[] = [];
          for (const line of stdout.split('\n')) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) continue;
            const parts = trimmed.split(/\s+/);
            if (parts.length >= 2) envs.push({ name: parts[0], path: parts[1] });
          }
          resolve({ envs });
        });
      });
    } catch (error: any) {
      return { error: error.message, envs: [] };
    }
  });

  // System info scanning (GPU, CUDA)
  ipcMain.handle('yolo:getSystemInfo', async () => {
    try {
      const { exec } = await import('child_process');
      const info: any = { platform: process.platform, gpus: [], cuda: null };

      await new Promise<void>((resolve) => {
        exec('nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader', { timeout: 10000 }, (error, stdout) => {
          if (!error && stdout.trim()) {
            info.gpus = stdout.trim().split('\n').map((line) => {
              const parts = line.split(',').map(s => s.trim());
              return { name: parts[0], driver: parts[1], memory: parts[2] };
            });
          }
          resolve();
        });
      });

      await new Promise<void>((resolve) => {
        exec('nvcc --version', { timeout: 10000 }, (error, stdout) => {
          if (!error && stdout) {
            const match = stdout.match(/release (\d+\.\d+)/);
            if (match) info.cuda = match[1];
          }
          resolve();
        });
      });

      return info;
    } catch (error: any) {
      return { error: error.message, gpus: [], cuda: null };
    }
  });

  // Check if a conda env has required training packages
  ipcMain.handle('yolo:checkEnvPackages', async (_event, envName: string) => {
    try {
      const { exec } = await import('child_process');
      return new Promise((resolve) => {
        exec(`conda run -n ${envName} pip list`, { timeout: 30000 }, (error, stdout) => {
          if (error) { resolve({ error: error.message, packages: {}, missing: [], ready: false }); return; }
          const required = ['torch', 'ultralytics', 'opencv-python', 'numpy', 'pillow'];
          const installed: Record<string, string> = {};
          for (const line of stdout.split('\n')) {
            const parts = line.trim().split(/\s+/);
            if (parts.length >= 2) {
              const pkgName = parts[0].toLowerCase();
              const version = parts[1];
              for (const req of required) {
                if (pkgName === req.toLowerCase() || pkgName.startsWith(req.toLowerCase().replace('-', '_'))) {
                  installed[req] = version;
                }
              }
            }
          }
          const missing = required.filter(r => !installed[r]);
          resolve({ packages: installed, missing, ready: missing.length === 0 });
        });
      });
    } catch (error: any) {
      return { error: error.message, packages: {}, missing: [], ready: false };
    }
  });

  // ─── File System (sandboxed) ───

  ipcMain.handle('fs:openDirectory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
      title: 'Select Directory',
    });
    return result.canceled ? null : result.filePaths[0];
  });

  ipcMain.handle('fs:readFile', async (_event, filePath: string) => {
    const { promises: fs } = await import('fs');
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return { content };
    } catch (error: any) {
      return { error: error.message };
    }
  });

  ipcMain.handle('fs:writeFile', async (_event, filePath: string, content: string) => {
    const { promises: fs } = await import('fs');
    try {
      const dir = await import('path');
      await fs.mkdir(dir.dirname(filePath), { recursive: true });
      await fs.writeFile(filePath, content, 'utf-8');
      return { success: true };
    } catch (error: any) {
      return { error: error.message };
    }
  });

  ipcMain.handle('fs:listFiles', async (_event, dirPath: string, pattern?: string) => {
    const { promises: fs } = await import('fs');
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      const files = entries
        .filter((e: any) => e.isFile())
        .map((e: any) => e.name);
      return { files };
    } catch (error: any) {
      return { error: error.message };
    }
  });

  // ─── System ───

  ipcMain.handle('system:getVersion', () => {
    return '1.0.0-sp';
  });
}
