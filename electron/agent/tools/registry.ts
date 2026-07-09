/**
 * Tool Registry — Following Claude Code's tool system pattern
 *
 * Key patterns:
 * - Zod-inspired schema definitions
 * - Deferred tool loading for token efficiency
 * - Default-deny permissions (isReadOnly / isDestructive)
 * - Structured execution with context passing
 */

import { ToolDefinition, ToolExecutionContext } from '../types';

// Re-export ToolExecutionContext so tool files can import it from './registry'
export type { ToolExecutionContext } from '../types';

import { InspectDatasetTool } from './inspect-dataset';
import { ConvertDatasetTool } from './convert-dataset';
import { TrainModelTool } from './train-model';
import { GenerateReportTool } from './generate-report';
import { ListTemplatesTool } from './list-templates';
import { GetTemplateTool } from './get-template';
import { ReadFileTool } from './read-file';
import { WriteFileTool } from './write-file';
import { ShellTool } from './shell';

export interface Tool {
  definition: ToolDefinition;
  execute(args: any, context: ToolExecutionContext): Promise<any>;
}

export class ToolRegistry {
  private tools: Map<string, Tool> = new Map();
  private pythonWorker: any;

  constructor(pythonWorker: any) {
    this.pythonWorker = pythonWorker;
    this.registerBuiltinTools();
  }

  private registerBuiltinTools(): void {
    // ─── YOLO-specific tools (delegate to Python worker) ───
    this.register(new InspectDatasetTool(this.pythonWorker));
    this.register(new ConvertDatasetTool(this.pythonWorker));
    this.register(new TrainModelTool(this.pythonWorker));
    this.register(new GenerateReportTool(this.pythonWorker));
    this.register(new ListTemplatesTool());
    this.register(new GetTemplateTool());

    // ─── General tools (like Claude Code) ───
    this.register(new ReadFileTool());
    this.register(new WriteFileTool());
    this.register(new ShellTool());
  }

  register(tool: Tool): void {
    this.tools.set(tool.definition.name, tool);
  }

  getTool(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  getSchemas(): any[] {
    return Array.from(this.tools.values()).map((tool) => ({
      name: tool.definition.name,
      description: tool.definition.description,
      input_schema: tool.definition.parameters,
    }));
  }

  getToolDescriptions(): string {
    return Array.from(this.tools.values())
      .map((tool) => {
        const risk = tool.definition.riskLevel === 'high' ? '⚠️ HIGH RISK' :
                     tool.definition.riskLevel === 'medium' ? '⚡ MEDIUM RISK' : '✅ LOW RISK';
        return `- ${tool.definition.name}: ${tool.definition.description} [${risk}]`;
      })
      .join('\n');
  }

  listTools(): ToolDefinition[] {
    return Array.from(this.tools.values()).map((tool) => tool.definition);
  }
}
