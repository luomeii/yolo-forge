/**
 * Reviewer Panel — YOLO Label Visualization & Editing
 * State lifted to Zustand store, persists across panel switches.
 * Auto-save on every change. J/L for prev/next, A toggles mode, F resets.
 */

import React, { useState, useRef, useEffect } from 'react';
import { useAppStore } from '../../stores/app-store';

interface BBox {
  id: string;
  classId: number;
  cx: number; cy: number; w: number; h: number;
}

interface HistoryEntry {
  action: 'add' | 'delete';
  box?: BBox;
}

const BOX_COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2'];

export const ReviewerPanel: React.FC = () => {
  const { locale, reviewerState, setReviewerState } = useAppStore();

  const [boxes, setBoxes] = useState<BBox[]>([]);
  const [currentClass, setCurrentClass] = useState(0);
  const [mode, setMode] = useState<'edit' | 'review'>('edit');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageNaturalSize, setImageNaturalSize] = useState({ w: 0, h: 0 });
  const [imageSrc, setImageSrc] = useState('');
  const [loadingImage, setLoadingImage] = useState(false);
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
  const [drawCurrent, setDrawCurrent] = useState<{ x: number; y: number } | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number } | null>(null);
  const [showClassEditor, setShowClassEditor] = useState(false);
  const [editingClassId, setEditingClassId] = useState<number | null>(null);
  const [editClassName, setEditClassName] = useState('');
  const [newClassName, setNewClassName] = useState('');
  const [autoSavedAt, setAutoSavedAt] = useState<number | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const { imageDir, labelDir, classes, started, images, currentIndex } = reviewerState;

  const browseImageDir = async () => {
    const path = await window.electronAPI.fs.openDirectory();
    if (path) setReviewerState({ imageDir: path });
  };

  const browseLabelDir = async () => {
    const path = await window.electronAPI.fs.openDirectory();
    if (path) setReviewerState({ labelDir: path });
  };

  const startReview = async () => {
    if (!imageDir) {
      alert(locale === 'zh' ? '请先选择图像目录' : 'Please select images directory');
      return;
    }
    const result = await window.electronAPI.fs.listFiles(imageDir);
    if (result.files) {
      const imgs = result.files.filter((f: string) => /\.(jpg|jpeg|png|bmp|tif|tiff|webp)$/i.test(f)).sort();
      if (imgs.length === 0) {
        alert(locale === 'zh' ? '图像目录中没有图像文件' : 'No image files found');
        return;
      }
      setReviewerState({ images: imgs, currentIndex: 0, started: true });
    }
  };

  const exitReview = () => {
    setReviewerState({ started: false, images: [], currentIndex: 0 });
    setImageSrc('');
    setImageLoaded(false);
    setBoxes([]);
  };

  const autoSave = async (boxesToSave: BBox[]) => {
    if (images.length === 0 || !labelDir) return;
    const imgName = images[currentIndex];
    if (!imgName) return;
    const labelName = imgName.replace(/\.[^.]+$/, '.txt');
    const labelPath = `${labelDir}/${labelName}`.replace(/\\/g, '/');
    const content = boxesToSave.map(b => `${b.classId} ${b.cx.toFixed(6)} ${b.cy.toFixed(6)} ${b.w.toFixed(6)} ${b.h.toFixed(6)}`).join('\n');
    try {
      await window.electronAPI.fs.writeFile(labelPath, content + '\n');
      setAutoSavedAt(Date.now());
    } catch (err) {
      console.error('Auto-save failed:', err);
    }
  };

  useEffect(() => {
    if (!started) return;
    const updateSize = () => {
      if (containerRef.current) {
        setContainerSize({ w: containerRef.current.clientWidth, h: containerRef.current.clientHeight });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, [started]);

  useEffect(() => {
    if (!started || images.length === 0 || !imageDir) return;
    const imgName = images[currentIndex];
    if (!imgName) return;
    setLoadingImage(true);
    setImageLoaded(false);
    const imgPath = `${imageDir}/${imgName}`.replace(/\\/g, '/');
    setImageSrc(`file:///${imgPath.replace(/^\//, '')}`);
    const labelName = imgName.replace(/\.[^.]+$/, '.txt');
    const labelPath = `${labelDir}/${labelName}`.replace(/\\/g, '/');
    window.electronAPI.fs.readFile(labelPath).then((result: any) => {
      if (result.content) {
        const parsed: BBox[] = result.content.split('\n').filter((line: string) => line.trim()).map((line: string, idx: number) => {
          const parts = line.trim().split(/\s+/);
          return { id: `box_${idx}_${Date.now()}`, classId: parseInt(parts[0]) || 0, cx: parseFloat(parts[1]) || 0, cy: parseFloat(parts[2]) || 0, w: parseFloat(parts[3]) || 0, h: parseFloat(parts[4]) || 0 };
        });
        setBoxes(parsed);
      } else { setBoxes([]); }
    }).catch(() => setBoxes([]));
    setHistory([]); setSelectedBoxId(null); setZoom(1); setPan({ x: 0, y: 0 });
  }, [currentIndex, images, imageDir, labelDir, started]);

  const getDisplayDims = () => {
    if (!imageNaturalSize.w || !imageNaturalSize.h || !containerSize.w || !containerSize.h) return { drawW: 0, drawH: 0, offsetX: 0, offsetY: 0 };
    const fitScale = Math.min(containerSize.w / imageNaturalSize.w, containerSize.h / imageNaturalSize.h);
    const scale = fitScale * zoom;
    const drawW = imageNaturalSize.w * scale;
    const drawH = imageNaturalSize.h * scale;
    const offsetX = (containerSize.w - drawW) / 2 + pan.x;
    const offsetY = (containerSize.h - drawH) / 2 + pan.y;
    return { drawW, drawH, offsetX, offsetY };
  };

  const getContainerPos = (e: React.MouseEvent) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    const pos = getContainerPos(e);
    if (e.button === 1) { setIsPanning(true); setPanStart({ x: pos.x - pan.x, y: pos.y - pan.y }); return; }
    if (mode !== 'edit') return;
    const { drawW, drawH, offsetX, offsetY } = getDisplayDims();
    for (const box of boxes) {
      const bx = offsetX + (box.cx - box.w / 2) * drawW;
      const by = offsetY + (box.cy - box.h / 2) * drawH;
      const bw = box.w * drawW; const bh = box.h * drawH;
      if (pos.x >= bx && pos.x <= bx + bw && pos.y >= by && pos.y <= by + bh) { setSelectedBoxId(box.id); return; }
    }
    setSelectedBoxId(null); setIsDrawing(true); setDrawStart(pos); setDrawCurrent(pos);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const pos = getContainerPos(e);
    if (isPanning && panStart) { setPan({ x: pos.x - panStart.x, y: pos.y - panStart.y }); return; }
    if (isDrawing) setDrawCurrent(pos);
  };

  const handleMouseUp = () => {
    if (isPanning) { setIsPanning(false); setPanStart(null); return; }
    if (!isDrawing || !drawStart || !drawCurrent) { setIsDrawing(false); setDrawStart(null); setDrawCurrent(null); return; }
    const { drawW, drawH, offsetX, offsetY } = getDisplayDims();
    if (drawW <= 0 || drawH <= 0) { setIsDrawing(false); setDrawStart(null); setDrawCurrent(null); return; }
    const x1 = Math.min(drawStart.x, drawCurrent.x); const y1 = Math.min(drawStart.y, drawCurrent.y);
    const x2 = Math.max(drawStart.x, drawCurrent.x); const y2 = Math.max(drawStart.y, drawCurrent.y);
    if (x2 - x1 < 5 || y2 - y1 < 5) { setIsDrawing(false); setDrawStart(null); setDrawCurrent(null); return; }
    const cx = ((x1 + x2) / 2 - offsetX) / drawW;
    const cy = ((y1 + y2) / 2 - offsetY) / drawH;
    const w = (x2 - x1) / drawW; const h = (y2 - y1) / drawH;
    const newBox: BBox = { id: `box_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, classId: currentClass, cx: Math.max(0, Math.min(1, cx)), cy: Math.max(0, Math.min(1, cy)), w: Math.max(0.001, Math.min(1, w)), h: Math.max(0.001, Math.min(1, h)) };
    const newBoxes = [...boxes, newBox];
    setBoxes(newBoxes); setHistory([...history, { action: 'add', box: newBox }]);
    autoSave(newBoxes);
    setIsDrawing(false); setDrawStart(null); setDrawCurrent(null);
  };

  const handleWheel = (e: React.WheelEvent) => {
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.max(0.1, Math.min(20, z * delta)));
  };

  const deleteSelectedBox = () => {
    if (!selectedBoxId) return;
    const box = boxes.find(b => b.id === selectedBoxId);
    const newBoxes = boxes.filter(b => b.id !== selectedBoxId);
    setBoxes(newBoxes);
    if (box) setHistory([...history, { action: 'delete', box }]);
    setSelectedBoxId(null);
    autoSave(newBoxes);
  };

  const undoLast = () => {
    if (history.length === 0) return;
    const last = history[history.length - 1];
    let newBoxes = [...boxes];
    if (last.action === 'add' && last.box) { newBoxes = boxes.filter(b => b.id !== last.box!.id); }
    else if (last.action === 'delete' && last.box) { newBoxes = [...boxes, last.box]; }
    setBoxes(newBoxes); setHistory(history.slice(0, -1));
    autoSave(newBoxes);
  };

  const addNewClass = () => {
    if (!newClassName.trim()) return;
    if (classes.includes(newClassName.trim())) { alert(locale === 'zh' ? '类别已存在' : 'Class already exists'); return; }
    setReviewerState({ classes: [...classes, newClassName.trim()] });
    setNewClassName('');
  };

  const renameClass = (id: number, newName: string) => {
    if (!newName.trim()) return;
    const newClasses = [...classes]; newClasses[id] = newName.trim();
    setReviewerState({ classes: newClasses }); setEditingClassId(null);
  };

  const deleteClass = (id: number) => {
    if (boxes.some(b => b.classId === id)) { alert(locale === 'zh' ? '该类别正在使用，不能删除' : 'Class is in use'); return; }
    if (classes.length <= 1) { alert(locale === 'zh' ? '至少保留一个类别' : 'Keep at least one'); return; }
    setReviewerState({ classes: classes.filter((_, i) => i !== id) });
    if (currentClass >= classes.length - 1) setCurrentClass(classes.length - 2);
  };

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
      if (!started) return;
      if (e.key === 'a' || e.key === 'A') { setMode(m => m === 'edit' ? 'review' : 'edit'); }
      else if (e.key === 'f' || e.key === 'F') { e.preventDefault(); setZoom(1); setPan({ x: 0, y: 0 }); }
      else if (e.key === 'j' || e.key === 'J') { if (currentIndex > 0) setReviewerState({ currentIndex: currentIndex - 1 }); }
      else if (e.key === 'l' || e.key === 'L') { if (currentIndex < images.length - 1) setReviewerState({ currentIndex: currentIndex + 1 }); }
      else if (e.key === 'n' || e.key === 'N') { setShowClassEditor(!showClassEditor); }
      else if (e.key >= '0' && e.key <= '9') { const cid = parseInt(e.key); if (cid < classes.length) setCurrentClass(cid); }
      else if (e.key === 'd' || e.key === 'D') { deleteSelectedBox(); }
      else if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undoLast(); }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [boxes, selectedBoxId, history, currentIndex, images, classes, started, locale, showClassEditor, setReviewerState, currentClass]);

  if (!started) {
    return (
      <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
          {locale === 'zh' ? '标签审查' : 'Label Reviewer'}
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>
          {locale === 'zh' ? '选择图像和标签目录，可视化标注框。支持补框、删除、翻页、缩放、撤销。补框后自动保存。' : 'Select image and label directories. Auto-save on every change.'}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 600 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{locale === 'zh' ? '图像目录 *' : 'Images Directory *'}</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={imageDir} readOnly placeholder={locale === 'zh' ? '点击浏览选择' : 'Click Browse'} style={{ flex: 1, padding: '8px 12px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-mono)' }} />
              <button onClick={browseImageDir} style={{ padding: '8px 16px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13 }}>{locale === 'zh' ? '浏览' : 'Browse'}</button>
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{locale === 'zh' ? '标签目录 *' : 'Labels Directory *'}</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={labelDir} readOnly placeholder={locale === 'zh' ? '点击浏览选择' : 'Click Browse'} style={{ flex: 1, padding: '8px 12px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-mono)' }} />
              <button onClick={browseLabelDir} style={{ padding: '8px 16px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13 }}>{locale === 'zh' ? '浏览' : 'Browse'}</button>
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{locale === 'zh' ? '类别列表 (逗号分隔)' : 'Classes (comma-separated)'}</label>
            <input value={classes.join(', ')} onChange={e => { const list = e.target.value.split(',').map(s => s.trim()).filter(Boolean); setReviewerState({ classes: list.length > 0 ? list : ['defect', 'scratch', 'oil'] }); }} style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)', borderRadius: 8, background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 13, boxSizing: 'border-box' }} />
          </div>
          <button onClick={startReview} disabled={!imageDir} style={{ padding: '12px 24px', border: 'none', borderRadius: 8, background: imageDir ? 'var(--accent-primary)' : 'var(--bg-active)', color: imageDir ? '#fff' : 'var(--text-tertiary)', cursor: imageDir ? 'pointer' : 'default', fontSize: 14, fontWeight: 600, marginTop: 8 }}>{locale === 'zh' ? '▶ 开始审查' : '▶ Start Review'}</button>
        </div>
      </div>
    );
  }

  const { drawW, drawH, offsetX, offsetY } = getDisplayDims();
  const btnStyle: React.CSSProperties = { padding: '4px 10px', border: '1px solid var(--border-primary)', borderRadius: 4, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12 };
  const activeBtnStyle: React.CSSProperties = { ...btnStyle, background: 'var(--accent-muted)', color: 'var(--accent-primary)', borderColor: 'var(--accent-primary)' };

  return (
    <div style={{ padding: 16, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, padding: '8px 12px', background: 'var(--bg-tertiary)', borderRadius: 8, flexWrap: 'wrap' }}>
        <button onClick={() => setReviewerState({ currentIndex: Math.max(0, currentIndex - 1) })} disabled={currentIndex === 0} style={btnStyle}>◀</button>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)', minWidth: 80, textAlign: 'center' }}>{currentIndex + 1} / {images.length}</span>
        <button onClick={() => setReviewerState({ currentIndex: Math.min(images.length - 1, currentIndex + 1) })} disabled={currentIndex >= images.length - 1} style={btnStyle}>▶</button>
        <div style={{ width: 1, height: 24, background: 'var(--border-primary)', margin: '0 8px' }} />
        <button onClick={() => setMode('edit')} style={mode === 'edit' ? activeBtnStyle : btnStyle}>{locale === 'zh' ? '编辑' : 'Edit'}</button>
        <button onClick={() => setMode('review')} style={mode === 'review' ? activeBtnStyle : btnStyle}>{locale === 'zh' ? '审查' : 'Review'}</button>
        <div style={{ width: 1, height: 24, background: 'var(--border-primary)', margin: '0 8px' }} />
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{locale === 'zh' ? '类别' : 'Class'}:</span>
        <select value={currentClass} onChange={e => setCurrentClass(Number(e.target.value))} style={{ padding: '4px 8px', border: '1px solid var(--border-primary)', borderRadius: 4, background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 12 }}>
          {classes.map((c, i) => <option key={i} value={i}>{i}: {c}</option>)}
        </select>
        <button onClick={() => setShowClassEditor(!showClassEditor)} style={btnStyle}>{locale === 'zh' ? '管理类别' : 'Classes'}</button>
        <div style={{ flex: 1 }} />
        {autoSavedAt && (Date.now() - autoSavedAt < 3000) && <span style={{ fontSize: 11, color: 'var(--success)' }}>✓ {locale === 'zh' ? '已自动保存' : 'Auto-saved'}</span>}
        <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} style={btnStyle}>F</button>
        <button onClick={exitReview} style={btnStyle}>{locale === 'zh' ? '退出' : 'Exit'}</button>
      </div>

      {showClassEditor && (
        <div style={{ marginBottom: 8, padding: 12, background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>{locale === 'zh' ? '类别管理' : 'Class Management'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
            {classes.map((c, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ width: 24, height: 16, background: BOX_COLORS[i % BOX_COLORS.length], borderRadius: 3, fontSize: 10, color: '#000', textAlign: 'center', lineHeight: '16px', fontWeight: 600 }}>{i}</span>
                {editingClassId === i ? (
                  <>
                    <input value={editClassName} onChange={e => setEditClassName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') renameClass(i, editClassName); }} style={{ flex: 1, padding: '4px 8px', border: '1px solid var(--accent-primary)', borderRadius: 4, background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 12 }} autoFocus />
                    <button onClick={() => renameClass(i, editClassName)} style={{ ...btnStyle, padding: '2px 8px' }}>✓</button>
                    <button onClick={() => setEditingClassId(null)} style={{ ...btnStyle, padding: '2px 8px' }}>✗</button>
                  </>
                ) : (
                  <>
                    <span style={{ flex: 1, fontSize: 12, color: 'var(--text-primary)' }}>{c}</span>
                    <button onClick={() => { setEditingClassId(i); setEditClassName(c); }} style={{ ...btnStyle, padding: '2px 8px' }}>{locale === 'zh' ? '改名' : 'Rename'}</button>
                    <button onClick={() => deleteClass(i)} style={{ ...btnStyle, padding: '2px 8px', color: 'var(--error)' }}>×</button>
                  </>
                )}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input value={newClassName} onChange={e => setNewClassName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addNewClass(); }} placeholder={locale === 'zh' ? '新类别名称' : 'New class name'} style={{ flex: 1, padding: '4px 8px', border: '1px solid var(--border-primary)', borderRadius: 4, background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 12 }} />
            <button onClick={addNewClass} style={{ ...btnStyle, background: 'var(--accent-primary)', color: '#fff', border: 'none' }}>{locale === 'zh' ? '+ 添加' : '+ Add'}</button>
          </div>
        </div>
      )}

      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8, padding: '0 4px' }}>
        {locale === 'zh' ? '拖拽=画框(自动保存) | 滚轮=缩放 | 中键=平移 | A=切换模式 | F=归正 | N=类别管理 | 0-9=类别 | D=删除 | Ctrl+Z=撤销 | J/L=翻页' : 'drag=draw | wheel=zoom | middle=pan | A=mode | F=fit | N=classes | 0-9=class | D=delete | Ctrl+Z=undo | J/L=nav'}
        {' | '}
        <span style={{ color: mode === 'edit' ? 'var(--accent-primary)' : 'var(--success)', fontWeight: 600 }}>{locale === 'zh' ? `当前: ${mode === 'edit' ? '编辑' : '审查'}模式` : `Mode: ${mode}`}</span>
      </div>

      <div ref={containerRef} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp} onWheel={handleWheel} style={{ flex: 1, background: '#000', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border-primary)', position: 'relative', cursor: mode === 'edit' ? 'crosshair' : 'default' }}>
        {imageSrc && <img src={imageSrc} onLoad={(e) => { const t = e.target as HTMLImageElement; setImageNaturalSize({ w: t.naturalWidth, h: t.naturalHeight }); setImageLoaded(true); setLoadingImage(false); }} onError={() => { setLoadingImage(false); setImageLoaded(false); }} style={{ position: 'absolute', left: offsetX, top: offsetY, width: drawW, height: drawH, pointerEvents: 'none', userSelect: 'none' }} />}
        {imageLoaded && drawW > 0 && (
          <svg width={containerSize.w} height={containerSize.h} style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}>
            {boxes.map((box) => {
              const bx = offsetX + (box.cx - box.w / 2) * drawW; const by = offsetY + (box.cy - box.h / 2) * drawH;
              const bw = box.w * drawW; const bh = box.h * drawH;
              const isSelected = box.id === selectedBoxId; const color = BOX_COLORS[box.classId % BOX_COLORS.length];
              return (
                <g key={box.id}>
                  <rect x={bx} y={by} width={bw} height={bh} fill="none" stroke={isSelected ? '#FFFFFF' : color} strokeWidth={isSelected ? 3 : 2} />
                  <rect x={bx} y={Math.max(0, by - 18)} width={Math.min(100, bw)} height={18} fill={color} />
                  <text x={bx + 4} y={Math.max(12, by - 5)} fill="#000" fontSize="12" fontFamily="monospace">{box.classId}:{classes[box.classId] || '?'}</text>
                </g>
              );
            })}
            {isDrawing && drawStart && drawCurrent && <rect x={Math.min(drawStart.x, drawCurrent.x)} y={Math.min(drawStart.y, drawCurrent.y)} width={Math.abs(drawCurrent.x - drawStart.x)} height={Math.abs(drawCurrent.y - drawStart.y)} fill="none" stroke="#FFFF00" strokeWidth={2} strokeDasharray="5,5" />}
          </svg>
        )}
        {(loadingImage || (!imageLoaded && imageSrc)) && <div style={{ position: 'absolute', top: 12, left: 12, padding: '6px 12px', background: 'rgba(0,0,0,0.7)', borderRadius: 6, color: 'var(--text-secondary)', fontSize: 12 }}>{locale === 'zh' ? '加载中...' : 'Loading...'}</div>}
      </div>
    </div>
  );
};
