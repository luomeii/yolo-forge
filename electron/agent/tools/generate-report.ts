/**
 * Generate Report Tool — Training report generation via LLM
 */

import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class GenerateReportTool implements Tool {
  definition: ToolDefinition = {
    name: 'generate_report',
    description:
      'Generate a training analysis report from Ultralytics training output. ' +
      'Reads results.csv and other metrics, then produces a markdown report ' +
      'with key findings, metric trends, and recommendations.',
    riskLevel: 'low',
    isReadOnly: true,
    isDestructive: false,
    parameters: {
      type: 'object',
      properties: {
        training_output_dir: {
          type: 'string',
          description: 'Path to the Ultralytics training output directory containing results.csv',
        },
        format: {
          type: 'string',
          description: 'Output format for the report',
          enum: ['markdown', 'json'],
          default: 'markdown',
        },
      },
      required: ['training_output_dir'],
    },
  };

  private pythonWorker: any;

  constructor(pythonWorker: any) {
    this.pythonWorker = pythonWorker;
  }

  async execute(
    args: { training_output_dir: string; format?: string },
    context: ToolExecutionContext
  ): Promise<any> {
    const result = await this.pythonWorker.execute('report', {
      training_output_dir: args.training_output_dir,
      format: args.format ?? 'markdown',
    });
    return result;
  }
}
