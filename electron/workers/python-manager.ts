/**
 * Python Worker Manager — Manages the Python subprocess for YOLO operations
 *
 * Communication via stdin/stdout NDJSON protocol
 * Auto-detects Python path (python on Windows, python3 on Unix)
 * Auto-detects worker.py path (dev vs production)
 */

import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';
import { EventEmitter } from 'events';

interface PendingRequest {
  resolve: (result: any) => void;
  reject: (error: Error) => void;
  timeout: NodeJS.Timeout;
}

export class PythonWorkerManager extends EventEmitter {
  private process: ChildProcess | null = null;
  private pending: Map<string, PendingRequest> = new Map();
  private buffer = '';
  private started = false;
  private startPromise: Promise<void> | null = null;

  async start(): Promise<void> {
    if (this.started) return;
    if (this.startPromise) return this.startPromise;

    this.startPromise = this._doStart();
    return this.startPromise;
  }

  private async _doStart(): Promise<void> {
    // Resolve worker.py path — works in both dev and production
    // Dev: dist/electron/workers/python-manager.js → ../../electron/python/worker.py
    // Prod: dist/electron/workers/python-manager.js → ../python/worker.py (extraResources)
    const devPath = path.join(__dirname, '..', '..', '..', 'electron', 'python', 'worker.py');
    const prodPath = path.join(__dirname, '..', 'python', 'worker.py');
    const workerScript = fs.existsSync(devPath) ? devPath : prodPath;

    // Windows uses 'python', Unix uses 'python3'
    const pythonPath = process.env.YOLO_FORGE_PYTHON ??
      (process.platform === 'win32' ? 'python' : 'python3');

    console.log(`[PythonWorker] Script: ${workerScript}`);
    console.log(`[PythonWorker] Python: ${pythonPath}`);
    console.log(`[PythonWorker] Script exists: ${fs.existsSync(workerScript)}`);

    if (!fs.existsSync(workerScript)) {
      console.error('[PythonWorker] worker.py not found!');
      this.started = false;
      return;
    }

    try {
      this.process = spawn(pythonPath, [workerScript], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          PYTHONIOENCODING: 'utf-8',
        },
      });

      this.process.on('error', (err) => {
        console.error('[PythonWorker] Spawn error:', err.message);
        this.started = false;
        this.emit('error', err);
      });

      this.process.stdout?.on('data', (data: Buffer) => {
        this.buffer += data.toString('utf-8');
        this.processBuffer();
      });

      this.process.stderr?.on('data', (data: Buffer) => {
        const msg = data.toString('utf-8').trim();
        if (msg) {
          console.log('[PythonWorker stderr]:', msg);
          this.emit('log', msg);
        }
      });

      this.process.on('exit', (code) => {
        console.log(`[PythonWorker] Exited with code ${code}`);
        this.started = false;
        this.emit('exit', code);
      });

      this.started = true;
      console.log('[PythonWorker] Started successfully');
    } catch (err: any) {
      console.error('[PythonWorker] Failed to start:', err.message);
      this.started = false;
    }
  }

  async execute(command: string, args: any): Promise<any> {
    if (!this.process || !this.started) {
      return this.mockExecute(command, args);
    }

    const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(requestId);
        reject(new Error(`Python worker request timed out: ${command}`));
      }, 120000);

      this.pending.set(requestId, { resolve, reject, timeout });

      const payload = JSON.stringify({ id: requestId, command, args });

      try {
        this.process!.stdin?.write(payload + '\n');
      } catch (err) {
        clearTimeout(timeout);
        this.pending.delete(requestId);
        reject(new Error(`Failed to send command to Python worker: ${err}`));
      }
    });
  }

  stop(): void {
    if (this.process) {
      this.process.kill('SIGTERM');
      this.process = null;
      this.started = false;
    }
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timeout);
      pending.reject(new Error('Python worker stopped'));
    }
    this.pending.clear();
  }

  private processBuffer(): void {
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const response = JSON.parse(line);

        // Handle progress/complete events (training)
        if (response.type === 'progress') {
          this.emit('trainProgress', response);
          continue;
        }
        if (response.type === 'complete') {
          this.emit('trainComplete', response);
          continue;
        }

        // Handle response to request
        const pending = this.pending.get(response.id);
        if (pending) {
          clearTimeout(pending.timeout);
          this.pending.delete(response.id);
          if (response.error) {
            pending.reject(new Error(response.error));
          } else {
            pending.resolve(response.result);
          }
        }
      } catch {
        // Not valid JSON — ignore
      }
    }
  }

  /**
   * Mock execute — returns clear error when Python worker isn't available
   */
  private async mockExecute(command: string, args: any): Promise<any> {
    const errorMsg = `Python worker未运行。操作"${command}"无法执行。` +
      `请确保已安装Python和依赖包(ultralytics, opencv-python, pyyaml, pillow)。` +
      `运行: pip install -r electron/python/requirements.txt`;
    return { error: errorMsg, command, status: 'python_worker_unavailable' };
  }
}
