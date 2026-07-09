/**
 * Shell Tool — Like Codex CLI's shell tool
 *
 * Improvements:
 * - Default timeout reduced to 15 seconds (prevents hanging)
 * - AbortSignal support (Stop button works)
 * - Better error messages
 * - Output truncation with clear indicators
 */

import { exec } from 'child_process';
import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class ShellTool implements Tool {
  definition: ToolDefinition = {
    name: 'shell',
    description:
      '执行Shell命令并返回输出。用于文件操作、运行脚本、检查GPU状态等。' +
      '注意：扫描数据集请优先使用inspect_dataset工具（一次性返回完整结构），' +
      '不要用shell命令逐个目录探索。' +
      '警告：此工具可执行任意命令，请谨慎使用。',
    riskLevel: 'high',
    isReadOnly: false,
    isDestructive: true,
    parameters: {
      type: 'object',
      properties: {
        command: {
          type: 'string',
          description: '要执行的Shell命令',
        },
        timeout: {
          type: 'number',
          description: '超时时间(毫秒)，默认15000（15秒）',
          default: 15000,
        },
        cwd: {
          type: 'string',
          description: '工作目录',
        },
      },
      required: ['command'],
    },
  };

  async execute(
    args: { command: string; timeout?: number; cwd?: string },
    context: ToolExecutionContext
  ): Promise<any> {
    const cwd = args.cwd || context.workingDirectory || process.cwd();
    const timeout = Math.min(args.timeout ?? 15000, 60000); // Max 60s

    return new Promise((resolve) => {
      const child = exec(
        args.command,
        {
          cwd,
          timeout,
          maxBuffer: 1024 * 1024 * 5,
          encoding: 'utf-8',
          env: {
            ...process.env,
            PYTHONIOENCODING: 'utf-8',
            LANG: 'en_US.UTF-8',
            CHCP: '65001',
          },
          shell: process.platform === 'win32' ? 'cmd.exe' : undefined,
        },
        (error, stdout, stderr) => {
          // Ensure output is string
          const stdoutStr = typeof stdout === 'string' ? stdout : Buffer.from(stdout || '').toString('utf-8');
          const stderrStr = typeof stderr === 'string' ? stderr : Buffer.from(stderr || '').toString('utf-8');
          if (error) {
            const isTimeout = error.killed || error.signal === 'SIGTERM';
            resolve({
              exit_code: typeof error.code === 'number' ? error.code : 1,
              stdout: stdoutStr.substring(0, 5000),
              stderr: stderrStr.substring(0, 3000),
              error: isTimeout ? `Command timed out after ${timeout}ms` : error.message,
            });
          } else {
            resolve({
              exit_code: 0,
              stdout: stdoutStr.substring(0, 8000),
              stderr: stderrStr.substring(0, 2000),
              truncated: stdoutStr.length > 8000,
            });
          }
        }
      );

      // Support AbortSignal — kill process if abort triggered
      if (context.abortSignal) {
        const onAbort = () => {
          try { child.kill('SIGTERM'); } catch {}
        };
        context.abortSignal.addEventListener('abort', onAbort, { once: true });
        child.on('exit', () => {
          context.abortSignal.removeEventListener('abort', onAbort);
        });
      }
    });
  }
}
