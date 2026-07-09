/**
 * Permission Manager — Codex CLI / Claude Code aligned
 *
 * Three user-facing permission choices (like Codex):
 *   - "allow_once":     Allow this single call only
 *   - "allow_always":   Allow this tool/category forever (no more prompts)
 *   - "deny":           Deny this call (and stop the current task)
 *
 * Safe-by-default command allowlist (Codex pattern):
 *   Read-only commands like `ls`, `cat`, `pwd`, `git status`, `conda env list`
 *   are auto-allowed WITHOUT any prompt — they cannot modify state.
 */

import { ToolDefinition } from '../types';

export enum PermissionDecision {
  ALLOW = 'allow',
  ASK = 'ask',
  DENY = 'deny',
}

// User choice granularity (Codex-style)
export enum PermissionChoice {
  ALLOW_ONCE = 'allow_once',
  ALLOW_ALWAYS = 'allow_always',
  DENY = 'deny',
}

interface PermissionRequest {
  toolName: string;
  arguments: string;
  toolCallId: string;
  resolve: (decision: PermissionDecision) => void;
}

// Safe read-only shell commands — auto-allowed without prompt
const SAFE_COMMAND_PREFIXES = [
  'ls', 'dir', 'pwd', 'echo', 'cat', 'head', 'tail', 'less', 'more',
  'wc', 'grep', 'egrep', 'fgrep', 'rg', 'find', 'fd', 'file', 'stat',
  'tree', 'du', 'df', 'free', 'top', 'ps', 'whoami', 'hostname',
  'uname', 'uptime', 'date', 'cal', 'env', 'printenv',
  'git status', 'git log', 'git diff', 'git show', 'git branch',
  'git remote', 'git stash list', 'git tag',
  'python --version', 'python3 --version', 'node --version', 'npm --version',
  'pip --version', 'pip list', 'pip3 list', 'conda list', 'conda info',
  'conda env list', 'conda env',
  'nvidia-smi', 'which', 'where', 'type',
];

// Commands that are NEVER auto-allowed (always prompt)
const DANGEROUS_PATTERNS = [
  /\brm\s+-rf?\b/i,
  /\bmkfs\b/i,
  /\bdd\b.*\bof=/i,
  /\bshutdown\b/i,
  /\breboot\b/i,
  /\bformat\b/i,
  /:\(\)\s*\{.*\};:/,
  /\b>\s*\/dev\/sda/i,
];

export class PermissionManager {
  // Persistent rules: toolName → ALLOW_ALWAYS
  private alwaysAllowTools: Set<string> = new Set();
  private alwaysDenyTools: Set<string> = new Set();

  // Per-command-pattern rules for shell tool
  private alwaysAllowCommands: Set<string> = new Set();

  // Pending permission requests waiting for user response
  private pendingRequests: Map<string, PermissionRequest> = new Map();

  /**
   * Check whether a tool call is permitted
   */
  async checkPermission(
    toolName: string,
    args: string,
    toolDef: ToolDefinition
  ): Promise<{ decision: PermissionDecision; reason?: string }> {
    // ── 1. Check always-deny rules ──
    if (this.alwaysDenyTools.has(toolName)) {
      return { decision: PermissionDecision.DENY, reason: `Tool "${toolName}" is blocked` };
    }

    // ── 2. Check always-allow rules (whole tool) ──
    if (this.alwaysAllowTools.has(toolName)) {
      return { decision: PermissionDecision.ALLOW };
    }

    // ── 3. For shell tool: inspect command content ──
    if (toolName === 'shell') {
      const command = this.extractShellCommand(args);

      // Check for dangerous patterns — ALWAYS ask
      if (command && DANGEROUS_PATTERNS.some(p => p.test(command))) {
        return { decision: PermissionDecision.ASK, reason: 'Dangerous command detected' };
      }

      // Check always-allow command patterns
      if (command) {
        const cmdPrefix = this.getCommandPrefix(command);
        if (this.alwaysAllowCommands.has(cmdPrefix)) {
          return { decision: PermissionDecision.ALLOW };
        }

        // Check safe command allowlist — auto-allow WITHOUT prompt (Codex pattern)
        if (this.isSafeReadCommand(command)) {
          return { decision: PermissionDecision.ALLOW };
        }
      }
    }

    // ── 4. Read-only low-risk tools: auto-allow ──
    if (toolDef.isReadOnly && toolDef.riskLevel === 'low') {
      return { decision: PermissionDecision.ALLOW };
    }

    // ── 5. Default: ask ──
    return { decision: PermissionDecision.ASK };
  }

  /**
   * Wait for user decision on a permission request
   */
  waitForUserDecision(toolCallId: string): Promise<PermissionDecision> {
    return new Promise((resolve) => {
      this.pendingRequests.set(toolCallId, {
        toolName: '',
        arguments: '',
        toolCallId,
        resolve,
      });
    });
  }

  /**
   * Resolve a pending permission request with a user choice
   * (Codex-style: allow_once / allow_always / deny)
   */
  resolveUserDecision(toolCallId: string, choice: PermissionChoice, toolName?: string, args?: string): void {
    const request = this.pendingRequests.get(toolCallId);
    if (!request) {
      console.log(`[PermissionManager] No pending request for ${toolCallId}`);
      return;
    }

    const actualToolName = toolName || request.toolName;

    if (choice === PermissionChoice.ALLOW_ALWAYS) {
      if (actualToolName === 'shell' && args) {
        const cmd = this.extractShellCommand(args);
        const prefix = this.getCommandPrefix(cmd);
        this.alwaysAllowCommands.add(prefix);
        console.log(`[PermissionManager] Always allow shell command prefix: ${prefix}`);
      } else {
        this.alwaysAllowTools.add(actualToolName);
        console.log(`[PermissionManager] Always allow tool: ${actualToolName}`);
      }
      request.resolve(PermissionDecision.ALLOW);
    } else if (choice === PermissionChoice.DENY) {
      request.resolve(PermissionDecision.DENY);
    } else {
      // ALLOW_ONCE
      request.resolve(PermissionDecision.ALLOW);
    }

    this.pendingRequests.delete(toolCallId);
  }

  // ─── Helper Methods ───

  private extractShellCommand(args: string): string {
    try {
      const parsed = JSON.parse(args);
      return parsed.command || '';
    } catch {
      return '';
    }
  }

  private getCommandPrefix(command: string): string {
    if (!command) return '';
    const trimmed = command.trim();
    const parts = trimmed.split(/\s+/);
    if (parts.length >= 2 && parts[0] === 'git') {
      return `${parts[0]} ${parts[1]}`;
    }
    if (parts.length >= 2 && parts[0] === 'conda') {
      return `${parts[0]} ${parts[1]}`;
    }
    return parts[0] || '';
  }

  private isSafeReadCommand(command: string): boolean {
    if (!command) return false;
    const trimmed = command.trim().toLowerCase();
    const cmd = trimmed.replace(/^sudo\s+/, '');

    return SAFE_COMMAND_PREFIXES.some(prefix => {
      const p = prefix.toLowerCase();
      return cmd === p || cmd.startsWith(p + ' ') || cmd.startsWith(p + '\t');
    });
  }

  // ─── Public API for UI ───

  setToolAlwaysAllow(toolName: string): void {
    this.alwaysAllowTools.add(toolName);
  }

  setToolAlwaysDeny(toolName: string): void {
    this.alwaysDenyTools.add(toolName);
  }

  resetRules(): void {
    this.alwaysAllowTools.clear();
    this.alwaysDenyTools.clear();
    this.alwaysAllowCommands.clear();
  }

  getAlwaysAllowTools(): string[] {
    return Array.from(this.alwaysAllowTools);
  }

  getAlwaysAllowCommands(): string[] {
    return Array.from(this.alwaysAllowCommands);
  }

  /**
   * Cleanup pending request (called on timeout/dispose)
   */
  cleanupPendingRequest(toolCallId: string): void {
    this.pendingRequests.delete(toolCallId);
  }
}
