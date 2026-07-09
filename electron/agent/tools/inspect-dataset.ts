/**
 * Inspect Dataset Tool — Delegates to Python worker
 *
 * Scans a dataset directory and returns structured information about:
 * - Folder structure (images/labels subdirectories)
 * - Label format detection (YOLO, VOC, COCO, raw_px)
 * - Class distribution
 * - Background image detection
 */

import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class InspectDatasetTool implements Tool {
  definition: ToolDefinition = {
    name: 'inspect_dataset',
    description:
      '扫描数据集目录，一次性返回完整结构分析。包括：子文件夹列表、每个文件夹的图片数/标签数/标签格式/类别分布。' +
      '这是扫描数据集的首选工具，不要用shell命令逐个探索。' +
      '在任何转换或训练前，先用这个工具了解数据集结构。',
    riskLevel: 'low',
    isReadOnly: true,
    isDestructive: false,
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: '数据集根目录的绝对路径',
        },
        sample_size: {
          type: 'number',
          description: '每个子文件夹采样标签文件数（默认5）',
          default: 5,
        },
        deep_scan: {
          type: 'boolean',
          description: '是否递归扫描所有子目录（默认false）',
          default: false,
        },
      },
      required: ['path'],
    },
  };

  private pythonWorker: any;

  constructor(pythonWorker: any) {
    this.pythonWorker = pythonWorker;
  }

  async execute(args: { path: string; sample_size?: number; deep_scan?: boolean }, context: ToolExecutionContext): Promise<any> {
    const result = await this.pythonWorker.execute('inspect', {
      path: args.path,
      sample_size: args.sample_size ?? 5,
      deep_scan: args.deep_scan ?? false,
    });
    return result;
  }
}
