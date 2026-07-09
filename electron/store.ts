/**
 * Store — Persistent configuration storage
 *
 * Uses electron-store pattern for JSON-based config persistence
 * at ~/.yolo-forge-sp/config.json
 */

import { promises as fs } from 'fs';
import path from 'path';
import os from 'os';

const CONFIG_DIR = path.join(os.homedir(), '.yolo-forge-sp');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

const DEFAULT_CONFIG: Record<string, any> = {
  agent: {
    provider: 'openai',
    model: 'gpt-4o',
    apiKey: '',
    baseUrl: '',
    temperature: 0.3,
    maxTokens: 4096,
    maxIterations: 25,
    compactionThreshold: 80000,
  },
  ui: {
    theme: 'dark',
    fontSize: 14,
    sidebarWidth: 280,
    chatWidth: 400,
  },
  yolo: {
    defaultDatasetDir: '',
    defaultOutputDir: './yolo_output',
    defaultModel: 'yolov8n.pt',
    autoInspect: true,
  },
  permissions: {
    autoMode: false,
    rules: {},
  },
};

export class Store {
  private config: Record<string, any> = {};
  private initialized = false;

  async init(): Promise<void> {
    if (this.initialized) return;

    try {
      await fs.mkdir(CONFIG_DIR, { recursive: true });

      try {
        const data = await fs.readFile(CONFIG_FILE, 'utf-8');
        this.config = { ...DEFAULT_CONFIG, ...JSON.parse(data) };
      } catch {
        // Config file doesn't exist yet — use defaults
        this.config = { ...DEFAULT_CONFIG };
        await this.save();
      }

      // Set file permissions to owner-only (Unix)
      if (process.platform !== 'win32') {
        await fs.chmod(CONFIG_FILE, 0o600);
      }

      this.initialized = true;
    } catch (error) {
      console.error('Failed to initialize store:', error);
      this.config = { ...DEFAULT_CONFIG };
      this.initialized = true;
    }
  }

  async get(key: string): Promise<any> {
    return this.config[key];
  }

  async set(key: string, value: any): Promise<void> {
    this.config[key] = value;
    await this.save();
  }

  async getAll(): Promise<Record<string, any>> {
    return { ...this.config };
  }

  async reset(): Promise<void> {
    this.config = { ...DEFAULT_CONFIG };
    await this.save();
  }

  private async save(): Promise<void> {
    await fs.writeFile(CONFIG_FILE, JSON.stringify(this.config, null, 2), 'utf-8');
  }
}
