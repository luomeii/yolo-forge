/**
 * Read File Tool — Like Claude Code's Read tool
 *
 * Reads file contents from disk. Essential for the agent to understand
 * dataset configurations, YAML profiles, and training outputs.
 */

import { promises as fs } from 'fs';
import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class ReadFileTool implements Tool {
  definition: ToolDefinition = {
    name: 'read_file',
    description:
      'Read the contents of a file from the local filesystem. ' +
      'Use this to inspect YAML profiles, data.yaml, training configs, ' +
      'or any other text file. Returns file content with line numbers.',
    riskLevel: 'low',
    isReadOnly: true,
    isDestructive: false,
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute path to the file to read',
        },
        start_line: {
          type: 'number',
          description: 'Starting line number (1-based, default: 1)',
          default: 1,
        },
        end_line: {
          type: 'number',
          description: 'Ending line number (inclusive, default: end of file)',
        },
      },
      required: ['path'],
    },
  };

  async execute(
    args: { path: string; start_line?: number; end_line?: number },
    _context: ToolExecutionContext
  ): Promise<any> {
    try {
      const content = await fs.readFile(args.path, 'utf-8');
      const lines = content.split('\n');
      const start = (args.start_line ?? 1) - 1;
      const end = args.end_line ?? lines.length;
      const selectedLines = lines.slice(start, end);

      const numberedContent = selectedLines
        .map((line, i) => `${start + i + 1}: ${line}`)
        .join('\n');

      return {
        path: args.path,
        content: numberedContent,
        total_lines: lines.length,
        displayed_lines: selectedLines.length,
      };
    } catch (error: any) {
      return { error: `Failed to read file: ${error.message}` };
    }
  }
}
