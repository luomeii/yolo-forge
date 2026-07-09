/**
 * Settings Panel — Complete LLM configuration with i18n
 * 
 * Features:
 * - Language switcher (zh/en)
 * - OpenAI config: model dropdown + custom input, context length, max tokens
 * - Anthropic config: same
 * - Custom endpoint URL support
 * - Connection test
 */

import React, { useState, useEffect } from 'react';
import { useAppStore } from '../../stores/app-store';
import { t, availableLocales, openaiModels, anthropicModels } from '../../i18n';

export const SettingsPanel: React.FC = () => {
  const { agentConfig, updateAgentConfig, locale, setLocale } = useAppStore();
  const [localConfig, setLocalConfig] = useState(agentConfig);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [saved, setSaved] = useState(false);
  const [showModelDropdown, setShowModelDropdown] = useState(false);

  // Force re-render on locale change
  const _ = locale;

  useEffect(() => {
    setLocalConfig(agentConfig);
  }, [agentConfig]);

  const models = localConfig.provider === 'openai' ? openaiModels : anthropicModels;

  const handleSave = async () => {
    updateAgentConfig(localConfig);
    try {
      await window.electronAPI.config.set('agent', localConfig);
      await window.electronAPI.config.set('locale', locale);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message });
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      await window.electronAPI.config.set('agent', localConfig);
      const result = await window.electronAPI.config.testConnection();
      setTestResult(result);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setTesting(false);
    }
  };

  const selectModel = (modelId: string) => {
    const modelInfo = models.find(m => m.id === modelId);
    const update: any = { model: modelId };
    if (modelInfo) {
      update.maxTokens = Math.min(localConfig.maxTokens || 4096, modelInfo.maxOutput);
    }
    setLocalConfig({ ...localConfig, ...update });
    setShowModelDropdown(false);
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid var(--border-primary)',
    borderRadius: 8,
    background: 'var(--bg-elevated)',
    color: 'var(--text-primary)',
    fontSize: 13,
    fontFamily: 'var(--font-mono)',
    outline: 'none',
    boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: 6,
  };

  return (
    <div style={{ padding: 24, maxWidth: 720 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
        {t('settings.title')}
      </h2>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>
        {t('settings.desc')}
      </p>

      {/* ─── Language ─── */}
      <div style={{ marginBottom: 28, padding: 16, background: 'var(--bg-tertiary)', borderRadius: 12, border: '1px solid var(--border-primary)' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
          {t('settings.general')}
        </h3>
        <div>
          <label style={labelStyle}>{t('settings.language')}</label>
          <div style={{ display: 'flex', gap: 8 }}>
            {availableLocales.map((loc) => (
              <button
                key={loc.value}
                onClick={() => setLocale(loc.value)}
                style={{
                  flex: 1,
                  padding: 10,
                  border: `2px solid ${locale === loc.value ? 'var(--accent-primary)' : 'var(--border-primary)'}`,
                  borderRadius: 8,
                  background: locale === loc.value ? 'var(--accent-muted)' : 'var(--bg-elevated)',
                  color: locale === loc.value ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                {loc.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ─── LLM Config ─── */}
      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
          {t('settings.llmConfig')}
        </h3>

        {/* Provider Selection */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
          {(['openai', 'anthropic'] as const).map((provider) => (
            <button
              key={provider}
              onClick={() => {
                const defaultModel = provider === 'openai' ? 'gpt-4o' : 'claude-sonnet-4-20250514';
                setLocalConfig({ ...localConfig, provider, model: defaultModel });
              }}
              style={{
                flex: 1,
                padding: 16,
                border: `2px solid ${localConfig.provider === provider ? 'var(--accent-primary)' : 'var(--border-primary)'}`,
                borderRadius: 12,
                background: localConfig.provider === provider ? 'var(--accent-muted)' : 'var(--bg-elevated)',
                color: localConfig.provider === provider ? 'var(--accent-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 700 }}>
                {provider === 'openai' ? 'OpenAI' : 'Anthropic'}
              </div>
              <div style={{ fontSize: 11, marginTop: 4, opacity: 0.7 }}>
                {provider === 'openai' ? 'GPT-4o, GPT-4.1, o3...' : 'Claude Sonnet 4, Opus 4...'}
              </div>
            </button>
          ))}
        </div>

        {/* API Key */}
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>{t('settings.apiKey')}</label>
          <input
            type="password"
            value={localConfig.apiKey}
            onChange={(e) => setLocalConfig({ ...localConfig, apiKey: e.target.value })}
            placeholder={localConfig.provider === 'openai' ? 'sk-...' : 'sk-ant-...'}
            style={inputStyle}
          />
        </div>

        {/* Base URL */}
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>{t('settings.baseUrl')}</label>
          <input
            type="text"
            value={localConfig.baseUrl || ''}
            onChange={(e) => setLocalConfig({ ...localConfig, baseUrl: e.target.value })}
            placeholder={localConfig.provider === 'openai' ? 'https://api.openai.com/v1' : 'https://api.anthropic.com'}
            style={inputStyle}
          />
        </div>

        {/* Model Selection — Dropdown + Custom Input */}
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>{t('settings.model')}</label>
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              value={localConfig.model}
              onChange={(e) => setLocalConfig({ ...localConfig, model: e.target.value })}
              placeholder={t('settings.customModel')}
              style={{ ...inputStyle, paddingRight: 40 }}
            />
            <button
              onClick={() => setShowModelDropdown(!showModelDropdown)}
              style={{
                position: 'absolute',
                right: 4,
                top: 4,
                bottom: 4,
                padding: '0 10px',
                border: 'none',
                borderRadius: 6,
                background: 'var(--bg-active)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: 11,
                whiteSpace: 'nowrap',
              }}
            >
              {t('settings.orSelect')} ▾
            </button>

            {showModelDropdown && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                zIndex: 100,
                marginTop: 4,
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-primary)',
                borderRadius: 8,
                maxHeight: 280,
                overflowY: 'auto',
                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
              }}>
                {models.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => selectModel(m.id)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: 'none',
                      background: localConfig.model === m.id ? 'var(--accent-muted)' : 'transparent',
                      color: localConfig.model === m.id ? 'var(--accent-primary)' : 'var(--text-primary)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 13,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>{m.name}</span>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                      {m.context >= 1000000 ? `${(m.context / 1000000).toFixed(0)}M` : `${m.context / 1000}K`} ctx
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Context Length & Max Tokens */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>{t('settings.contextLength')}</label>
            <select
              value={localConfig.contextLength || (models.find(m => m.id === localConfig.model)?.context ?? 128000)}
              onChange={(e) => setLocalConfig({ ...localConfig, contextLength: Number(e.target.value) } as any)}
              style={{ ...inputStyle, fontFamily: 'var(--font-sans)' }}
            >
              {[8192, 16384, 32768, 65536, 128000, 200000, 1048576].map(v => (
                <option key={v} value={v}>
                  {v >= 1048576 ? `${(v / 1048576).toFixed(0)}M` : `${v / 1000}K`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>{t('settings.maxTokens')}</label>
            <select
              value={localConfig.maxTokens}
              onChange={(e) => setLocalConfig({ ...localConfig, maxTokens: Number(e.target.value) })}
              style={{ ...inputStyle, fontFamily: 'var(--font-sans)' }}
            >
              {[1024, 2048, 4096, 8192, 16384, 32768, 64000, 100000].map(v => (
                <option key={v} value={v}>
                  {v >= 1000 ? `${v / 1000}K` : v}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Temperature */}
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>{t('settings.temperature')}</label>
          <input
            type="number"
            value={localConfig.temperature}
            onChange={(e) => setLocalConfig({ ...localConfig, temperature: Number(e.target.value) })}
            min={0} max={2} step={0.1}
            style={{ ...inputStyle, width: 120 }}
          />
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 12 }}>
        <button onClick={handleSave} style={{
          padding: '10px 24px', border: 'none', borderRadius: 8,
          background: 'var(--accent-primary)', color: '#fff', cursor: 'pointer',
          fontSize: 14, fontWeight: 600,
        }}>
          {saved ? '✓ ' + t('settings.saved') : t('settings.save')}
        </button>
        <button onClick={handleTest} disabled={testing || !localConfig.apiKey} style={{
          padding: '10px 24px', border: '1px solid var(--border-primary)', borderRadius: 8,
          background: 'var(--bg-elevated)',
          color: testing || !localConfig.apiKey ? 'var(--text-tertiary)' : 'var(--text-secondary)',
          cursor: testing || !localConfig.apiKey ? 'default' : 'pointer',
          fontSize: 14,
        }}>
          {testing ? t('settings.testing') : t('settings.test')}
        </button>
      </div>

      {/* Test Result */}
      {testResult && (
        <div style={{
          marginTop: 16, padding: 12,
          background: testResult.success ? 'rgba(76,175,80,0.08)' : 'rgba(244,67,54,0.08)',
          border: `1px solid ${testResult.success ? 'rgba(76,175,80,0.3)' : 'rgba(244,67,54,0.3)'}`,
          borderRadius: 8,
          color: testResult.success ? 'var(--success)' : 'var(--error)',
          fontSize: 13,
        }}>
          {testResult.message}
        </div>
      )}
    </div>
  );
};
