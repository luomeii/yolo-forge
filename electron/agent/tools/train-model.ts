/**
 * Train Model Tool — YOLO training via Ultralytics
 *
 * Delegates to Python Worker. When Python Worker is unavailable,
 * falls back to shell-based training with conda env activation.
 * All training tasks sync to TaskManager for visualization.
 */

import { exec } from 'child_process';
import { Tool, ToolExecutionContext } from './registry';
import { ToolDefinition } from '../types';

export class TrainModelTool implements Tool {
  definition: ToolDefinition = {
    name: 'train_model',
    description:
      '启动YOLO模型训练（基于Ultralytics）。训练异步运行，进度同步到任务管理面板。' +
      '必须指定conda_env参数选择训练环境。训练前请先询问用户的数据集路径、模型、参数和导出目录。',
    riskLevel: 'medium',
    isReadOnly: false,
    isDestructive: false,
    parameters: {
      type: 'object',
      properties: {
        data_yaml: { type: 'string', description: 'data.yaml文件的完整路径（必填）' },
        conda_env: { type: 'string', description: '训练用的conda环境名（必填，如yolo）' },
        model: { type: 'string', description: '模型: yolov8n.pt/yolov8s.pt/yolov8m.pt/yolov8l.pt/yolov8x.pt/yolo11n.pt等', default: 'yolov8n.pt' },
        epochs: { type: 'number', description: '训练轮数（默认100）', default: 100 },
        imgsz: { type: 'number', description: '图像尺寸: 320/416/640/1280（默认640）', default: 640 },
        batch: { type: 'number', description: '批大小，-1自动（默认-1）', default: -1 },
        device: { type: 'string', description: '设备: auto/cpu/0/1/0,1（默认auto）', default: 'auto' },
        workers: { type: 'number', description: '数据加载线程（默认8）', default: 8 },
        save_period: { type: 'number', description: '每N轮保存（默认10）', default: 10 },
        optimizer: { type: 'string', description: '优化器: auto/SGD/Adam/AdamW/RMSProp', default: 'auto' },
        lr0: { type: 'number', description: '初始学习率（默认0.01）', default: 0.01 },
        lrf: { type: 'number', description: '最终学习率系数（默认0.01）', default: 0.01 },
        momentum: { type: 'number', description: '动量（默认0.937）', default: 0.937 },
        weight_decay: { type: 'number', description: '权重衰减（默认0.0005）', default: 0.0005 },
        warmup_epochs: { type: 'number', description: '预热轮数（默认3）', default: 3 },
        patience: { type: 'number', description: '早停耐心（默认50）', default: 50 },
        augment: { type: 'boolean', description: '数据增强（默认true）', default: true },
        project: { type: 'string', description: '导出目录' },
        name: { type: 'string', description: '项目名（默认yolo_forge_sp）', default: 'yolo_forge_sp' },
        resume: { type: 'boolean', description: '继续训练（默认false）', default: false },
      },
      required: ['data_yaml', 'conda_env'],
    },
  };

  private pythonWorker: any;

  constructor(pythonWorker: any) {
    this.pythonWorker = pythonWorker;
  }

  /**
   * Emit progress event via PythonWorkerManager's EventEmitter
   * so main.ts can forward to renderer for TaskManager sync
   */
  private emitProgress(taskId: string, percent: number, log: string, epoch?: number, totalEpochs?: number): void {
    if (this.pythonWorker?.emit) {
      this.pythonWorker.emit('trainProgress', { task_id: taskId, percent, log, epoch, total_epochs: totalEpochs });
    }
  }

  private emitComplete(taskId: string, result: any): void {
    if (this.pythonWorker?.emit) {
      this.pythonWorker.emit('trainComplete', { task_id: taskId, ...result });
    }
  }

  async execute(args: any, context: ToolExecutionContext): Promise<any> {
    if (!args.conda_env) {
      return { error: 'conda_env参数必填，请询问用户使用哪个conda环境' };
    }
    if (!args.data_yaml) {
      return { error: 'data_yaml参数必填' };
    }

    const taskId = args.task_id || `agent_train_${Date.now()}`;

    // Try Python worker first
    const result = await this.pythonWorker.execute('train', {
      data_yaml: args.data_yaml,
      conda_env: args.conda_env,
      model: args.model ?? 'yolov8n.pt',
      epochs: args.epochs ?? 100,
      imgsz: args.imgsz ?? 640,
      batch: args.batch ?? -1,
      device: args.device ?? 'auto',
      workers: args.workers ?? 8,
      save_period: args.save_period ?? 10,
      optimizer: args.optimizer ?? 'auto',
      lr0: args.lr0 ?? 0.01,
      lrf: args.lrf ?? 0.01,
      momentum: args.momentum ?? 0.937,
      weight_decay: args.weight_decay ?? 0.0005,
      warmup_epochs: args.warmup_epochs ?? 3,
      patience: args.patience ?? 50,
      augment: args.augment ?? true,
      project: args.project,
      name: args.name ?? 'yolo_forge_sp',
      resume: args.resume ?? false,
      task_id: taskId,
    });

    // If Python worker unavailable, fall back to shell-based training
    if (result && result.status === 'python_worker_unavailable') {
      console.log('[TrainModel] Python worker unavailable, falling back to shell training');
      return await this.shellFallbackTrain(args, taskId);
    }

    return result;
  }

  /**
   * Shell-based fallback training when Python worker is unavailable.
   * Uses conda run to execute training in the specified environment.
   * Emits progress events for TaskManager sync.
   */
  private async shellFallbackTrain(args: any, taskId: string): Promise<any> {
    const model = args.model ?? 'yolov8n.pt';
    const epochs = args.epochs ?? 100;
    const imgsz = args.imgsz ?? 640;
    const batch = args.batch ?? -1;
    const device = args.device ?? 'auto';
    const project = args.project ?? 'runs/detect';
    const name = args.name ?? 'yolo_forge_sp';

    // Emit start
    this.emitProgress(taskId, 0, `Starting training: ${model}, ${epochs} epochs, device=${device}`, 0, epochs);

    const yoloCmd = `yolo detect train model=${model} data="${args.data_yaml}" epochs=${epochs} imgsz=${imgsz} batch=${batch} device=${device} project="${project}" name="${name}"`;
    const cmd = `conda run -n ${args.conda_env} ${yoloCmd}`;

    console.log(`[TrainModel] Shell fallback command: ${cmd}`);

    return new Promise((resolve) => {
      const { spawn } = require('child_process');
      const child = spawn(cmd, { shell: true, env: { ...process.env, PYTHONUNBUFFERED: '1' } });

      let stdout = '';
      let stderr = '';

      child.stdout?.on('data', (data: Buffer) => {
        const text = data.toString('utf-8');
        stdout += text;
        // Parse epoch progress from Ultralytics output
        const epochMatch = text.match(/Epoch\s+(\d+)\/(\d+)/);
        if (epochMatch) {
          const epoch = parseInt(epochMatch[1]);
          const total = parseInt(epochMatch[2]);
          const percent = Math.round((epoch / total) * 100);
          this.emitProgress(taskId, percent, `Epoch ${epoch}/${total}`, epoch, total);
        }
      });

      child.stderr?.on('data', (data: Buffer) => {
        stderr += data.toString('utf-8');
      });

      // Timeout 10 min
      const timeout = setTimeout(() => {
        try { child.kill('SIGTERM'); } catch {}
      }, 600000);

      child.on('exit', (code: number) => {
        clearTimeout(timeout);
        if (code === 0 || stdout.includes('training complete') || stdout.includes('Results saved')) {
          this.emitProgress(taskId, 100, 'Training complete!', epochs, epochs);
          const result = {
            status: 'completed',
            model, epochs,
            results_dir: `${project}/${name}`,
            task_id: taskId,
            note: 'Training completed via shell fallback',
          };
          this.emitComplete(taskId, result);
          resolve(result);
        } else {
          const result = {
            status: 'failed',
            error: `Training exited with code ${code}`,
            stdout: stdout.substring(0, 5000),
            stderr: stderr.substring(0, 3000),
            task_id: taskId,
          };
          this.emitComplete(taskId, result);
          resolve(result);
        }
      });
    });
  }
}
