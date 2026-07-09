/**
 * Converter Panel — Dataset format conversion
 */

import React, { useState } from 'react';

export const ConverterPanel: React.FC = () => {
  const [profileYaml, setProfileYaml] = useState('');
  const [profilePath, setProfilePath] = useState('');
  const [dryRun, setDryRun] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleConvert = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const convertResult = await window.electronAPI.yolo.convert(
        profileYaml || '',
        dryRun
      );
      setResult(convertResult);
    } catch (err: any) {
      setError(err.message || 'Conversion failed');
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
        Dataset Converter
      </h2>
      <p style={{
        fontSize: 13,
        color: 'var(--text-secondary)',
        marginBottom: 24,
        lineHeight: 1.6,
      }}>
        Convert datasets between formats using declarative YAML profiles.
        Supports YOLO, VOC, COCO, and raw pixel formats. Always preview with dry-run first.
      </p>

      {/* YAML Editor */}
      <div style={{ marginBottom: 16 }}>
        <label style={{
          display: 'block',
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--text-secondary)',
          marginBottom: 6,
        }}>
          Conversion Profile (YAML)
        </label>
        <textarea
          value={profileYaml}
          onChange={(e) => setProfileYaml(e.target.value)}
          placeholder={`# Paste your conversion profile YAML here
# Or use the Agent Chat to generate one automatically
name: my_conversion
output_dir: ./yolo_output
split:
  train: 0.8
  val: 0.2
  test: 0
sources:
  - name: main
    image_dir: /path/to/images
    label_dir: /path/to/labels
    format: yolo`}
          rows={16}
          style={{
            width: '100%',
            padding: 12,
            border: '1px solid var(--border-primary)',
            borderRadius: 8,
            background: 'var(--bg-elevated)',
            color: 'var(--text-primary)',
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            lineHeight: 1.6,
            resize: 'vertical',
            outline: 'none',
          }}
        />
      </div>

      {/* Options */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        marginBottom: 24,
      }}>
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 13,
          color: 'var(--text-secondary)',
          cursor: 'pointer',
        }}>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
          />
          Dry Run (preview only)
        </label>
      </div>

      {/* Convert button */}
      <button
        onClick={handleConvert}
        disabled={!profileYaml || isLoading}
        style={{
          padding: '10px 24px',
          border: 'none',
          borderRadius: 8,
          background: profileYaml && !isLoading
            ? (dryRun ? 'var(--accent-primary)' : 'var(--warning)')
            : 'var(--bg-active)',
          color: profileYaml && !isLoading ? '#fff' : 'var(--text-tertiary)',
          cursor: profileYaml && !isLoading ? 'pointer' : 'default',
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        {isLoading ? 'Converting...' : dryRun ? 'Preview Conversion' : 'Execute Conversion'}
      </button>

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
            {result.status === 'dry_run' ? 'Preview Results' : 'Conversion Results'}
          </h3>
          <pre style={{
            background: 'var(--bg-primary)',
            padding: 12,
            borderRadius: 6,
            fontSize: 12,
            overflow: 'auto',
            maxHeight: 300,
          }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

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
    </div>
  );
};
