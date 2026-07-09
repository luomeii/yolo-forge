/**
 * Inspector Panel — Dataset structure scanning
 */

import React, { useState } from 'react';
import { useAppStore } from '../../stores/app-store';

export const InspectorPanel: React.FC = () => {
  const [datasetPath, setDatasetPath] = useState('');
  const [sampleSize, setSampleSize] = useState(5);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleBrowse = async () => {
    const path = await window.electronAPI.fs.openDirectory();
    if (path) setDatasetPath(path);
  };

  const handleInspect = async () => {
    if (!datasetPath) return;
    setIsLoading(true);
    setError(null);

    try {
      const inspectResult = await window.electronAPI.yolo.inspect(datasetPath, sampleSize);
      setResult(inspectResult);
      useAppStore.getState().setInspectionResult(inspectResult);
    } catch (err: any) {
      setError(err.message || 'Inspection failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 800 }}>
      <h2 style={{
        fontSize: 18,
        fontWeight: 700,
        color: 'var(--text-primary)',
        marginBottom: 8,
      }}>
        Dataset Inspector
      </h2>
      <p style={{
        fontSize: 13,
        color: 'var(--text-secondary)',
        marginBottom: 24,
        lineHeight: 1.6,
      }}>
        Scan a dataset directory to detect its structure, label formats, class distributions,
        and potential issues. This is the recommended first step before any conversion or training.
      </p>

      {/* Path input */}
      <div style={{ marginBottom: 16 }}>
        <label style={{
          display: 'block',
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--text-secondary)',
          marginBottom: 6,
        }}>
          Dataset Root Directory
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            value={datasetPath}
            onChange={(e) => setDatasetPath(e.target.value)}
            placeholder="/path/to/your/dataset"
            style={{
              flex: 1,
              padding: '8px 12px',
              border: '1px solid var(--border-primary)',
              borderRadius: 8,
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              fontSize: 13,
              fontFamily: 'var(--font-mono)',
              outline: 'none',
            }}
          />
          <button
            onClick={handleBrowse}
            style={{
              padding: '8px 16px',
              border: '1px solid var(--border-primary)',
              borderRadius: 8,
              background: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            Browse
          </button>
        </div>
      </div>

      {/* Sample size */}
      <div style={{ marginBottom: 24 }}>
        <label style={{
          display: 'block',
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--text-secondary)',
          marginBottom: 6,
        }}>
          Sample Size (labels per folder)
        </label>
        <input
          type="number"
          value={sampleSize}
          onChange={(e) => setSampleSize(Number(e.target.value))}
          min={1}
          max={50}
          style={{
            width: 80,
            padding: '8px 12px',
            border: '1px solid var(--border-primary)',
            borderRadius: 8,
            background: 'var(--bg-elevated)',
            color: 'var(--text-primary)',
            fontSize: 13,
            outline: 'none',
          }}
        />
      </div>

      {/* Inspect button */}
      <button
        onClick={handleInspect}
        disabled={!datasetPath || isLoading}
        style={{
          padding: '10px 24px',
          border: 'none',
          borderRadius: 8,
          background: datasetPath && !isLoading ? 'var(--accent-primary)' : 'var(--bg-active)',
          color: datasetPath && !isLoading ? '#fff' : 'var(--text-tertiary)',
          cursor: datasetPath && !isLoading ? 'pointer' : 'default',
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        {isLoading ? 'Inspecting...' : 'Inspect Dataset'}
      </button>

      {/* Error */}
      {error && (
        <div style={{
          marginTop: 16,
          padding: 12,
          background: 'rgba(244, 67, 54, 0.08)',
          border: '1px solid rgba(244, 67, 54, 0.3)',
          borderRadius: 8,
          color: 'var(--error)',
          fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{
          marginTop: 24,
          padding: 16,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-primary)',
          borderRadius: 12,
        }}>
          <h3 style={{
            fontSize: 15,
            fontWeight: 600,
            color: 'var(--text-primary)',
            marginBottom: 12,
          }}>
            Inspection Results
          </h3>

          {result.summary && (
            <p style={{
              fontSize: 13,
              color: 'var(--text-secondary)',
              marginBottom: 16,
              lineHeight: 1.6,
            }}>
              {result.summary}
            </p>
          )}

          {result.folders && result.folders.map((folder: any, idx: number) => (
            <div key={idx} style={{
              padding: 12,
              marginBottom: 8,
              background: 'var(--bg-tertiary)',
              borderRadius: 8,
              border: '1px solid var(--border-primary)',
            }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 8,
              }}>
                <span style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                }}>
                  {folder.name}
                </span>
                <span style={{
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontSize: 11,
                  background: 'var(--accent-muted)',
                  color: 'var(--accent-primary)',
                  fontWeight: 600,
                }}>
                  {folder.detected_format || 'unknown'}
                </span>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 8,
                fontSize: 12,
                color: 'var(--text-secondary)',
              }}>
                <span>Images: {folder.image_count ?? 0}</span>
                <span>Labels: {folder.label_count ?? 0}</span>
                {folder.is_background && (
                  <span style={{ color: 'var(--warning)' }}>Background folder</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
