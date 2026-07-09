/**
 * Trainer Panel — YOLO model training (complete version)
 * Features: conda env scan, system info, package check, advanced params,
 *           real-time progress, system notification, TaskManager sync
 */

import React, { useState, useEffect } from 'react';
import { t } from '../../i18n';
import { useAppStore } from '../../stores/app-store';
import { addTask, updateTask } from './TaskManagerPanel';

interface CondaEnv { name: string; path: string; }

export const TrainerPanel: React.FC = () => {
  const { locale } = useAppStore();

  const [dataYaml, setDataYaml] = useState('');
  const [model, setModel] = useState('yolov8n.pt');
  const [epochs, setEpochs] = useState(100);
  const [imgsz, setImgsz] = useState(640);
  const [batch, setBatch] = useState(-1);
  const [device, setDevice] = useState('auto');
  const [workers, setWorkers] = useState(8);
  const [savePeriod, setSavePeriod] = useState(10);
  const [optimizer, setOptimizer] = useState('auto');
  const [lr0, setLr0] = useState(0.01);
  const [lrf, setLrf] = useState(0.01);
  const [momentum, setMomentum] = useState(0.937);
  const [weightDecay, setWeightDecay] = useState(0.0005);
  const [warmupEpochs, setWarmupEpochs] = useState(3);
  const [augment, setAugment] = useState(true);
  const [exportDir, setExportDir] = useState('');
  const [projectName, setProjectName] = useState('yolo_forge_sp');
  const [resume, setResume] = useState(false);
  const [patience, setPatience] = useState(50);

  const [condaEnvs, setCondaEnvs] = useState<CondaEnv[]>([]);
  const [selectedEnv, setSelectedEnv] = useState('');
  const [scanningEnvs, setScanningEnvs] = useState(false);
  const [systemInfo, setSystemInfo] = useState<any>(null);
  const [envPackages, setEnvPackages] = useState<{ packages: Record<string, string>; missing: string[]; ready: boolean } | null>(null);
  const [trainLogs, setTrainLogs] = useState<string[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    scanCondaEnvs();
    scanSystemInfo();
    if (window.Notification && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  useEffect(() => {
    const removeProgress = (window.electronAPI.yolo as any).onTrainProgress?.((progress: any) => {
      if (progress.task_id) {
        updateTask(progress.task_id, {
          progress: progress.percent || 0,
          steps: [
            { name: locale === 'zh' ? '初始化模型' : 'Init', status: 'completed' },
            { name: locale === 'zh' ? '加载数据集' : 'Load', status: 'completed' },
            { name: `${locale === 'zh' ? '训练中' : 'Training'} (${progress.epoch || 0}/${progress.total_epochs || '?'})`, status: 'running' },
            { name: locale === 'zh' ? '验证' : 'Validation', status: 'pending' },
            { name: locale === 'zh' ? '导出' : 'Export', status: 'pending' },
          ],
        });
      }
      if (progress.log) setTrainLogs(prev => [...prev.slice(-50), progress.log]);
    });

    const removeComplete = (window.electronAPI.yolo as any).onTrainComplete?.((res: any) => {
      if (res.task_id) {
        updateTask(res.task_id, {
          status: res.error ? 'failed' : 'completed',
          progress: 100,
          result: res,
          error: res.error,
          completedAt: Date.now(),
        });
      }
      if (window.Notification) {
        if (res.error) {
          new Notification('YOLO-Forge SP - ' + (locale === 'zh' ? '训练失败' : 'Training Failed'), { body: res.error });
        } else {
          new Notification('YOLO-Forge SP - ' + (locale === 'zh' ? '训练完成' : 'Training Complete'), {
            body: `${model} ${locale === 'zh' ? '训练完成' : 'training finished'}. ${locale === 'zh' ? '结果' : 'Results'}: ${res.results_dir || ''}`,
          });
        }
      }
    });

    return () => {
      removeProgress?.();
      removeComplete?.();
    };
  }, [locale, model]);

  useEffect(() => {
    if (selectedEnv) checkPackages(selectedEnv);
  }, [selectedEnv]);

  const scanCondaEnvs = async () => {
    setScanningEnvs(true);
    try {
      const response = await (window.electronAPI.yolo as any).listCondaEnvs?.();
      if (response?.envs) {
        setCondaEnvs(response.envs);
        if (response.envs.length > 0 && !selectedEnv) {
          const yoloEnv = response.envs.find(e => e.name === 'yolo');
          setSelectedEnv(yoloEnv?.name || response.envs[0].name);
        }
      }
    } catch (err) { console.error('Failed to scan conda envs:', err); }
    finally { setScanningEnvs(false); }
  };

  const scanSystemInfo = async () => {
    try {
      const info = await (window.electronAPI.yolo as any).getSystemInfo?.();
      setSystemInfo(info);
    } catch (err) { console.error('Failed to scan system info:', err); }
  };

  const checkPackages = async (envName: string) => {
    try {
      const result = await (window.electronAPI.yolo as any).checkEnvPackages?.(envName);
      if (result) setEnvPackages(result);
    } catch (err) { console.error('Failed to check packages:', err); }
  };

  const handleBrowseData = async () => {
    const path = await window.electronAPI.fs.openDirectory();
    if (path) setDataYaml(path + '/data.yaml');
  };

  const handleBrowseExport = async () => {
    const path = await window.electronAPI.fs.openDirectory();
    if (path) setExportDir(path);
  };

  const handleTrain = async () => {
    if (!dataYaml) { setError(locale === 'zh' ? '请选择data.yaml' : 'Please select data.yaml'); return; }
    if (!selectedEnv) { setError(locale === 'zh' ? '请选择conda环境' : 'Please select conda env'); return; }
    setIsLoading(true); setError(null);

    const taskId = `train_${Date.now()}`;
    addTask({
      id: taskId, name: `${locale === 'zh' ? '训练' : 'Train'} ${model} (${epochs} ${locale === 'zh' ? '轮' : 'ep'}) [${selectedEnv}]`,
      status: 'running', progress: 0, taskType: 'training',
      steps: [
        { name: locale === 'zh' ? '初始化' : 'Init', status: 'running' },
        { name: locale === 'zh' ? '加载' : 'Load', status: 'pending' },
        { name: locale === 'zh' ? '训练' : 'Training', status: 'pending' },
        { name: locale === 'zh' ? '验证' : 'Validation', status: 'pending' },
        { name: locale === 'zh' ? '导出' : 'Export', status: 'pending' },
      ],
      startedAt: Date.now(),
    });

    try {
      const trainResult = await window.electronAPI.yolo.train({
        data_yaml: dataYaml, model, epochs, imgsz, batch, device, workers,
        save_period: savePeriod, optimizer, lr0, lrf, momentum, weight_decay: weightDecay,
        warmup_epochs: warmupEpochs, augment, project: exportDir || undefined,
        name: projectName, resume, patience, conda_env: selectedEnv, task_id: taskId,
      });
      setResult(trainResult);
      if (trainResult.error) {
        updateTask(taskId, { status: 'failed', error: trainResult.error, completedAt: Date.now() });
        setError(trainResult.error);
      }
    } catch (err: any) {
      setError(err.message);
      updateTask(taskId, { status: 'failed', error: err.message, completedAt: Date.now() });
    } finally { setIsLoading(false); }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
    borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-primary)',
    fontSize: 13, fontFamily: 'var(--font-mono)', outline: 'none', boxSizing: 'border-box',
  };
  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6,
  };

  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>{t('trainer.title')}</h2>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>{t('trainer.desc')}</p>

      {/* Conda Environment */}
      <div style={{ marginBottom: 16, padding: 12, background: 'rgba(94,106,210,0.08)', border: '1px solid rgba(94,106,210,0.3)', borderRadius: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <label style={{ ...labelStyle, marginBottom: 0 }}>{locale === 'zh' ? '训练环境 (conda) *' : 'Training Env (conda) *'}</label>
          <button onClick={scanCondaEnvs} disabled={scanningEnvs} style={{ padding: '4px 10px', border: '1px solid var(--border-primary)', borderRadius: 4, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11 }}>
            {scanningEnvs ? (locale === 'zh' ? '扫描中...' : 'Scanning...') : (locale === 'zh' ? '↻ 重新扫描' : '↻ Rescan')}
          </button>
        </div>
        <select value={selectedEnv} onChange={e => setSelectedEnv(e.target.value)} style={{ ...inputStyle, fontFamily: 'var(--font-sans)', borderColor: selectedEnv ? 'var(--border-primary)' : 'var(--error)' }}>
          <option value="">{locale === 'zh' ? '-- 请选择环境 --' : '-- Select env --'}</option>
          {condaEnvs.map(env => <option key={env.name} value={env.name}>{env.name} {env.name === 'yolo' ? '✓' : ''} — {env.path}</option>)}
        </select>
        {selectedEnv && envPackages && (
          <div style={{ marginTop: 8, fontSize: 11 }}>
            {envPackages.ready ? <span style={{ color: 'var(--success)' }}>✓ {locale === 'zh' ? '环境包完整' : 'Packages OK'}</span>
              : <span style={{ color: 'var(--warning)' }}>⚠ {locale === 'zh' ? '缺少: ' : 'Missing: '}{envPackages.missing.join(', ')}</span>}
            {Object.keys(envPackages.packages).length > 0 && <div style={{ marginTop: 4, color: 'var(--text-tertiary)' }}>{locale === 'zh' ? '已安装: ' : 'Installed: '}{Object.entries(envPackages.packages).map(([k, v]) => `${k}@${v}`).join(', ')}</div>}
          </div>
        )}
      </div>

      {/* System Info */}
      {systemInfo && (
        <div style={{ marginBottom: 16, padding: 12, background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ ...labelStyle, marginBottom: 0 }}>{locale === 'zh' ? '系统信息' : 'System Info'}</label>
            <button onClick={scanSystemInfo} style={{ padding: '4px 10px', border: '1px solid var(--border-primary)', borderRadius: 4, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11 }}>{locale === 'zh' ? '↻ 刷新' : '↻ Refresh'}</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
            <div><strong style={{ color: 'var(--text-secondary)' }}>GPU: </strong>{systemInfo.gpus?.length > 0 ? <span style={{ color: 'var(--success)' }}>{systemInfo.gpus.map((g: any) => `${g.name} (${g.memory})`).join(', ')}</span> : <span style={{ color: 'var(--warning)' }}>{locale === 'zh' ? '未检测到' : 'None'}</span>}</div>
            <div><strong style={{ color: 'var(--text-secondary)' }}>CUDA: </strong>{systemInfo.cuda ? <span style={{ color: 'var(--success)' }}>v{systemInfo.cuda}</span> : <span style={{ color: 'var(--warning)' }}>{locale === 'zh' ? '未检测到' : 'None'}</span>}</div>
          </div>
        </div>
      )}

      {/* Basic params */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div style={{ gridColumn: '1 / -1' }}>
          <label style={labelStyle}>{t('trainer.dataYaml')}</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input type="text" value={dataYaml} onChange={e => setDataYaml(e.target.value)} placeholder="/path/to/data.yaml" style={inputStyle} />
            <button onClick={handleBrowseData} style={{ padding: '8px 16px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13 }}>{t('inspector.browse')}</button>
          </div>
        </div>
        <div>
          <label style={labelStyle}>{t('trainer.model')}</label>
          <select value={model} onChange={e => setModel(e.target.value)} style={{ ...inputStyle, fontFamily: 'var(--font-sans)' }}>
            <option value="yolov8n.pt">YOLOv8 Nano</option><option value="yolov8s.pt">YOLOv8 Small</option>
            <option value="yolov8m.pt">YOLOv8 Medium</option><option value="yolov8l.pt">YOLOv8 Large</option>
            <option value="yolov8x.pt">YOLOv8 XLarge</option><option value="yolo11n.pt">YOLO11 Nano</option>
            <option value="yolo11s.pt">YOLO11 Small</option><option value="yolo11m.pt">YOLO11 Medium</option>
          </select>
        </div>
        <div><label style={labelStyle}>{t('trainer.epochs')}</label><input type="number" value={epochs} onChange={e => setEpochs(Number(e.target.value))} min={1} style={inputStyle} /></div>
        <div><label style={labelStyle}>{t('trainer.imgsz')}</label><select value={imgsz} onChange={e => setImgsz(Number(e.target.value))} style={{ ...inputStyle, fontFamily: 'var(--font-sans)' }}><option value={320}>320</option><option value={416}>416</option><option value={640}>640</option><option value={1280}>1280</option></select></div>
        <div><label style={labelStyle}>Batch (-1 {locale === 'zh' ? '自动' : 'auto'})</label><input type="number" value={batch} onChange={e => setBatch(Number(e.target.value))} min={-1} style={inputStyle} /></div>
        <div><label style={labelStyle}>{t('trainer.device')}</label><select value={device} onChange={e => setDevice(e.target.value)} style={{ ...inputStyle, fontFamily: 'var(--font-sans)' }}><option value="auto">Auto</option><option value="cpu">CPU</option><option value="0">GPU 0</option><option value="1">GPU 1</option><option value="0,1">GPU 0,1</option></select></div>
        <div><label style={labelStyle}>Workers</label><input type="number" value={workers} onChange={e => setWorkers(Number(e.target.value))} min={1} max={32} style={inputStyle} /></div>
        <div><label style={labelStyle}>{locale === 'zh' ? '保存间隔' : 'Save Period'}</label><input type="number" value={savePeriod} onChange={e => setSavePeriod(Number(e.target.value))} min={1} style={inputStyle} /></div>
      </div>

      {/* Export dir */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>{locale === 'zh' ? '导出目录' : 'Export Directory'}</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input type="text" value={exportDir} onChange={e => setExportDir(e.target.value)} placeholder={locale === 'zh' ? '默认: runs/detect' : 'Default: runs/detect'} style={inputStyle} />
          <button onClick={handleBrowseExport} style={{ padding: '8px 16px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13 }}>{t('inspector.browse')}</button>
        </div>
      </div>

      {/* Advanced params */}
      <button onClick={() => setShowAdvanced(!showAdvanced)} style={{ padding: '8px 16px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13, marginBottom: 16 }}>{showAdvanced ? '▼' : '▶'} {locale === 'zh' ? '高级参数' : 'Advanced'}</button>

      {showAdvanced && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16, padding: 16, background: 'var(--bg-tertiary)', borderRadius: 8 }}>
          <div><label style={labelStyle}>Optimizer</label><select value={optimizer} onChange={e => setOptimizer(e.target.value)} style={{ ...inputStyle, fontFamily: 'var(--font-sans)' }}><option value="auto">Auto</option><option value="SGD">SGD</option><option value="Adam">Adam</option><option value="AdamW">AdamW</option><option value="RMSProp">RMSProp</option></select></div>
          <div><label style={labelStyle}>LR0</label><input type="number" value={lr0} onChange={e => setLr0(Number(e.target.value))} step={0.001} min={0} style={inputStyle} /></div>
          <div><label style={labelStyle}>LRF</label><input type="number" value={lrf} onChange={e => setLrf(Number(e.target.value))} step={0.001} min={0} style={inputStyle} /></div>
          <div><label style={labelStyle}>Momentum</label><input type="number" value={momentum} onChange={e => setMomentum(Number(e.target.value))} step={0.001} min={0} max={1} style={inputStyle} /></div>
          <div><label style={labelStyle}>Weight Decay</label><input type="number" value={weightDecay} onChange={e => setWeightDecay(Number(e.target.value))} step={0.0001} min={0} style={inputStyle} /></div>
          <div><label style={labelStyle}>Warmup Epochs</label><input type="number" value={warmupEpochs} onChange={e => setWarmupEpochs(Number(e.target.value))} min={0} style={inputStyle} /></div>
          <div><label style={labelStyle}>Patience</label><input type="number" value={patience} onChange={e => setPatience(Number(e.target.value))} min={1} style={inputStyle} /></div>
          <div><label style={labelStyle}>Project Name</label><input type="text" value={projectName} onChange={e => setProjectName(e.target.value)} style={inputStyle} /></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 22 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}><input type="checkbox" checked={augment} onChange={e => setAugment(e.target.checked)} />{locale === 'zh' ? '数据增强' : 'Augment'}</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}><input type="checkbox" checked={resume} onChange={e => setResume(e.target.checked)} />{locale === 'zh' ? '继续训练' : 'Resume'}</label>
          </div>
        </div>
      )}

      <button onClick={handleTrain} disabled={!dataYaml || isLoading || !selectedEnv} style={{ padding: '12px 32px', border: 'none', borderRadius: 8, background: dataYaml && !isLoading && selectedEnv ? 'var(--accent-primary)' : 'var(--bg-active)', color: dataYaml && !isLoading && selectedEnv ? '#fff' : 'var(--text-tertiary)', cursor: dataYaml && !isLoading && selectedEnv ? 'pointer' : 'default', fontSize: 14, fontWeight: 600 }}>{isLoading ? t('trainer.starting') : t('trainer.start')}</button>

      {/* Training logs */}
      {trainLogs.length > 0 && (
        <div style={{ marginTop: 16, padding: 16, background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: 12 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>{locale === 'zh' ? '训练日志' : 'Training Logs'}</h3>
          <div style={{ background: '#000', padding: 12, borderRadius: 6, fontSize: 11, fontFamily: 'var(--font-mono)', color: '#0F0', maxHeight: 240, overflow: 'auto' }}>
            {trainLogs.map((log, i) => <div key={i} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{log}</div>)}
          </div>
        </div>
      )}

      {result && (
        <div style={{ marginTop: 16, padding: 16, background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: 12 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>{t('trainer.result')}</h3>
          <pre style={{ background: 'var(--bg-primary)', padding: 12, borderRadius: 6, fontSize: 12, overflow: 'auto', maxHeight: 300 }}>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}

      {error && <div style={{ marginTop: 16, padding: 12, background: 'rgba(244,67,54,0.08)', border: '1px solid rgba(244,67,54,0.3)', borderRadius: 8, color: 'var(--error)', fontSize: 13 }}>{error}</div>}
    </div>
  );
};
