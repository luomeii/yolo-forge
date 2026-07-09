/**
 * Write File Tool — Like Claude Code's Write tool
 *
 * Creates or overwrites files. Used by the agent to:
 * - Write conversion profile YAMLs
 * - Save generated reports
 * - Create data.yaml configurations
 */

import { promises as fs } from 'fs';
import path from 'path';
import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class WriteFileTool implements Tool {
  definition: ToolDefinition = {
    name: 'write_file',
    description:
      'Write content to a file on the local filesystem. ' +
      'Creates parent directories if they don\'t exist. ' +
      'Use for saving profiles, reports, and configurations.',
    riskLevel: 'medium',
    isReadOnly: false,
    isDestructive: true,
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute path where the file should be written',
        },
        content: {
          type: 'string',
          description: 'Content to write to the file',
        },
        append: {
          type: 'boolean',
          description: 'If true, append to existing file instead of overwriting',
          default: false,
        },
      },
      required: ['path', 'content'],
    },
  };

  async execute(
    args: { path: string; content: string; append?: boolean },
    _context: ToolExecutionContext
  ): Promise<any> {
    try {
      // Ensure parent directory exists
      const dir = path.dirname(args.path);
      await fs.mkdir(dir, { recursive: true });

      if (args.append) {
        await fs.appendFile(args.path, args.content, 'utf-8');
      } else {
        await fs.writeFile(args.path, args.content, 'utf-8');
      }

      return {
        path: args.path,
        bytes_written: Buffer.byteLength(args.content, 'utf-8'),
        appended: args.append ?? false,
      };
    } catch (error: any) {
      return { error: `Failed to write file: ${error.message}` };
    }
  }
}
