/**
 * Get Template Tool — Retrieve a specific conversion profile template
 */

import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

const TEMPLATES: Record<string, string> = {
  multi_folder_mixed: `# Multi-folder mixed format dataset
name: multi_folder_mixed
output_dir: ./yolo_output
split:
  train: 0.8
  val: 0.15
  test: 0.05
  seed: 42
  stratified: true
copy_strategy: copy
flatten: true
sources:
  - name: folder_a
    image_dir: /path/to/folder_a/images
    label_dir: /path/to/folder_a/labels
    format: yolo
    class_mapping:
      0: person
      1: car
  - name: folder_b
    image_dir: /path/to/folder_b/JPEGImages
    label_dir: /path/to/folder_b/Annotations
    format: voc
    class_mapping:
      person: person
      car: car
  - name: backgrounds
    image_dir: /path/to/backgrounds
    format: none
    background: copy_no_label
`,

  single_folder: `# Single folder YOLO format
name: single_folder
output_dir: ./yolo_output
split:
  train: 0.8
  val: 0.2
  test: 0
  seed: 42
  stratified: true
copy_strategy: symlink
flatten: false
sources:
  - name: main
    image_dir: /path/to/images
    label_dir: /path/to/labels
    format: yolo
`,

  voc_to_yolo: `# Pascal VOC to YOLO conversion
name: voc_to_yolo
output_dir: ./yolo_output
split:
  train: 0.8
  val: 0.2
  test: 0
  seed: 42
copy_strategy: copy
flatten: true
sources:
  - name: voc_data
    image_dir: /path/to/VOCdevkit/JPEGImages
    label_dir: /path/to/VOCdevkit/Annotations
    format: voc
    class_mapping:
      aeroplane: 0
      bicycle: 1
      bird: 2
      boat: 3
      bottle: 4
      bus: 5
      car: 6
      cat: 7
      chair: 8
      cow: 9
`,

  coco_to_yolo: `# COCO JSON to YOLO conversion
name: coco_to_yolo
output_dir: ./yolo_output
split:
  train: 0.8
  val: 0.2
  test: 0
  seed: 42
copy_strategy: copy
flatten: true
sources:
  - name: coco_data
    image_dir: /path/to/coco/images
    format: coco
    annotation_file: /path/to/coco/annotations/instances.json
    class_mapping:
      1: person
      2: bicycle
      3: car
`,

  raw_px_to_yolo: `# Raw pixel coordinates to YOLO format
name: raw_px_to_yolo
output_dir: ./yolo_output
split:
  train: 0.8
  val: 0.2
  test: 0
  seed: 42
copy_strategy: copy
flatten: true
sources:
  - name: raw_data
    image_dir: /path/to/images
    label_dir: /path/to/labels
    format: raw_px
    class_mapping:
      0: defect
      1: scratch
`,
};

export class GetTemplateTool implements Tool {
  definition: ToolDefinition = {
    name: 'get_template',
    description:
      'Get the YAML content of a specific built-in conversion profile template. ' +
      'Use list_templates to see available template names.',
    riskLevel: 'low',
    isReadOnly: true,
    isDestructive: false,
    parameters: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Template name (e.g., "multi_folder_mixed", "voc_to_yolo")',
          enum: ['multi_folder_mixed', 'single_folder', 'voc_to_yolo', 'coco_to_yolo', 'raw_px_to_yolo'],
        },
      },
      required: ['name'],
    },
  };

  async execute(args: { name: string }, _context: ToolExecutionContext): Promise<any> {
    const template = TEMPLATES[args.name];
    if (!template) {
      return { error: `Template not found: ${args.name}. Available: ${Object.keys(TEMPLATES).join(', ')}` };
    }
    return {
      name: args.name,
      yaml: template,
    };
  }
}
