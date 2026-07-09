/**
 * Convert Dataset Tool — YAML profile-driven conversion engine
 *
 * Converts datasets between formats using declarative YAML profiles.
 * Supports: YOLO, VOC, COCO, raw_px → YOLO output format.
 * Includes train/val/test split, class remapping, and background handling.
 */

import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class ConvertDatasetTool implements Tool {
  definition: ToolDefinition = {
    name: 'convert_dataset',
    description:
      'Convert a dataset using a YAML profile specification. ' +
      'The profile defines sources, label formats, class mappings, split ratios, and output structure. ' +
      'IMPORTANT: Always use dry_run=true first to preview changes before executing.',
    riskLevel: 'high',
    isReadOnly: false,
    isDestructive: true,
    parameters: {
      type: 'object',
      properties: {
        profile_yaml: {
          type: 'string',
          description: 'YAML string defining the conversion profile. See list_templates for examples.',
        },
        profile_path: {
          type: 'string',
          description: 'Path to a YAML profile file on disk (alternative to profile_yaml)',
        },
        dry_run: {
          type: 'boolean',
          description: 'If true, preview the conversion without writing any files. STRONGLY RECOMMENDED before actual conversion.',
          default: true,
        },
        output_dir: {
          type: 'string',
          description: 'Override the output directory specified in the profile',
        },
      },
    },
  };

  private pythonWorker: any;

  constructor(pythonWorker: any) {
    this.pythonWorker = pythonWorker;
  }

  async execute(
    args: { profile_yaml?: string; profile_path?: string; dry_run?: boolean; output_dir?: string },
    context: ToolExecutionContext
  ): Promise<any> {
    if (!args.profile_yaml && !args.profile_path) {
      return { error: 'Either profile_yaml or profile_path must be provided' };
    }

    const result = await this.pythonWorker.execute('convert', {
      profile_yaml: args.profile_yaml,
      profile_path: args.profile_path,
      dry_run: args.dry_run ?? true,
      output_dir: args.output_dir,
    });
    return result;
  }
}
