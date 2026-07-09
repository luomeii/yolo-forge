/**
 * Session Manager — Multi-session conversation persistence
 *
 * Following Claude Code's session model:
 * - Multiple named sessions
 * - Persistent storage in ~/.yolo-forge-sp/sessions/
 * - Session metadata (working directory, created/updated timestamps)
 * - Auto-trim for excessively long sessions
 * - LiveSession wrapper with addMessage method
 */

import { promises as fs } from 'fs';
import path from 'path';
import os from 'os';
import { Session, SessionMessage } from '../types';

const SESSIONS_DIR = path.join(os.homedir(), '.yolo-forge-sp', 'sessions');
const MAX_MESSAGES_PER_SESSION = 200;

interface SessionMeta {
  id: string;
  name: string;
  workingDirectory?: string;
  messageCount: number;
  createdAt: number;
  updatedAt: number;
}

/**
 * LiveSession — A mutable session object with convenience methods
 * Wraps the plain Session data with addMessage() for the agent loop
 */
export class LiveSession {
  id: string;
  messages: SessionMessage[];
  workingDirectory?: string;
  createdAt: number;
  updatedAt: number;
  metadata?: Record<string, any>;

  constructor(data: Session) {
    this.id = data.id;
    this.messages = data.messages;
    this.workingDirectory = data.workingDirectory;
    this.createdAt = data.createdAt;
    this.updatedAt = data.updatedAt;
    this.metadata = data.metadata;
  }

  addMessage(msg: Omit<SessionMessage, 'timestamp'> & { timestamp?: number }): void {
    this.messages.push({
      ...msg,
      timestamp: msg.timestamp ?? Date.now(),
    });
    this.updatedAt = Date.now();
  }

  toSession(): Session {
    return {
      id: this.id,
      messages: this.messages,
      workingDirectory: this.workingDirectory,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
      metadata: this.metadata,
    };
  }
}

export class SessionManager {
  private sessions: Map<string, LiveSession> = new Map();

  constructor() {
    this.ensureSessionsDir();
  }

  private async ensureSessionsDir(): Promise<void> {
    try {
      await fs.mkdir(SESSIONS_DIR, { recursive: true });
    } catch {
      // Directory may already exist
    }
  }

  /**
   * Get or create a live session
   */
  getOrCreate(sessionId: string): LiveSession {
    let session = this.sessions.get(sessionId);
    if (!session) {
      session = new LiveSession({
        id: sessionId,
        messages: [],
        workingDirectory: process.cwd(),
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });
      this.sessions.set(sessionId, session);
    }
    return session;
  }

  /**
   * Create a new session
   */
  async create(name?: string): Promise<Session> {
    const id = `session_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    const sessionData: Session = {
      id,
      messages: [],
      workingDirectory: process.cwd(),
      createdAt: Date.now(),
      updatedAt: Date.now(),
      metadata: name ? { name } : undefined,
    };

    const liveSession = new LiveSession(sessionData);
    this.sessions.set(id, liveSession);
    await this.saveSession(liveSession);
    return sessionData;
  }

  /**
   * Save session to disk
   */
  async saveSession(session: LiveSession): Promise<void> {
    session.updatedAt = Date.now();

    // Auto-trim if too many messages
    if (session.messages.length > MAX_MESSAGES_PER_SESSION) {
      const systemMsgs = session.messages.filter((m) => m.role === 'system');
      const nonSystemMsgs = session.messages.filter((m) => m.role !== 'system');
      const trimmed = nonSystemMsgs.slice(-MAX_MESSAGES_PER_SESSION + systemMsgs.length);
      session.messages = [...systemMsgs.slice(-2), ...trimmed];
    }

    const filePath = path.join(SESSIONS_DIR, `${session.id}.json`);
    await fs.writeFile(filePath, JSON.stringify(session.toSession(), null, 2), 'utf-8');
  }

  /**
   * Load a session from disk
   */
  async loadSession(sessionId: string): Promise<LiveSession | null> {
    try {
      const filePath = path.join(SESSIONS_DIR, `${sessionId}.json`);
      const data = await fs.readFile(filePath, 'utf-8');
      const session = JSON.parse(data) as Session;
      const liveSession = new LiveSession(session);
      this.sessions.set(sessionId, liveSession);
      return liveSession;
    } catch {
      return null;
    }
  }

  /**
   * List all sessions — auto-deletes empty sessions
   */
  async listSessions(): Promise<SessionMeta[]> {
    try {
      const files = await fs.readdir(SESSIONS_DIR);
      const metas: SessionMeta[] = [];

      for (const file of files) {
        if (!file.endsWith('.json')) continue;
        try {
          const filePath = path.join(SESSIONS_DIR, file);
          const data = await fs.readFile(filePath, 'utf-8');
          const session = JSON.parse(data) as Session;

          // Auto-delete empty sessions (no messages)
          if (session.messages.length === 0) {
            await fs.unlink(filePath).catch(() => {});
            continue;
          }

          metas.push({
            id: session.id,
            name: session.metadata?.name ?? `Session ${metas.length + 1}`,
            workingDirectory: session.workingDirectory,
            messageCount: session.messages.length,
            createdAt: session.createdAt,
            updatedAt: session.updatedAt,
          });
        } catch {
          // Skip corrupted files
        }
      }

      return metas.sort((a, b) => b.updatedAt - a.updatedAt);
    } catch {
      return [];
    }
  }

  /**
   * Delete a session
   */
  async deleteSession(sessionId: string): Promise<void> {
    this.sessions.delete(sessionId);
    try {
      const filePath = path.join(SESSIONS_DIR, `${sessionId}.json`);
      await fs.unlink(filePath);
    } catch {
      // File may not exist
    }
  }
}
