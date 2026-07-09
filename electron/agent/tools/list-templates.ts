/**
 * List Templates Tool — List built-in conversion profile templates
 */

import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

const BUILTIN_TEMPLATES = [
  'multi_folder_mixed',
  'single_folder',
  'voc_to_yolo',
  'coco_to_yolo',
  'raw_px_to_yolo',
];

export class ListTemplatesTool implements Tool {
  definition: ToolDefinition = {
    name: 'list_templates',
    description: 'List all built-in conversion profile template names. Use get_template to retrieve a specific template.',
    riskLevel: 'low',
    isReadOnly: true,
    isDestructive: false,
    parameters: {
      type: 'object',
      properties: {},
    },
  };

  async execute(_args: {}, _context: ToolExecutionContext): Promise<any> {
    return {
      templates: BUILTIN_TEMPLATES,
      count: BUILTIN_TEMPLATES.length,
    };
  }
}
