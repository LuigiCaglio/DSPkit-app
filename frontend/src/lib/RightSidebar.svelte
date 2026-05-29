<script>
  let { open = $bindable(false) } = $props()

  let activePanel = $state('settings')

  // Theme presets
  const themes = [
    { name: 'Midnight',  bg: '#13151f', grid: '#2d3148', traces: '#6366f1, #f59e0b, #10b981, #f87171, #a78bfa, #06b6d4' },
    { name: 'Ocean',     bg: '#0a192f', grid: '#1e3a5f', traces: '#64ffda, #f77f00, #ccd6f6, #ff6b6b, #ffd166, #48bfe3' },
    { name: 'Charcoal',  bg: '#1e1e1e', grid: '#3a3a3a', traces: '#569cd6, #dcdcaa, #4ec9b0, #ce9178, #c586c0, #9cdcfe' },
    { name: 'Light',     bg: '#ffffff', grid: '#e0e0e0', traces: '#2563eb, #dc2626, #059669, #d97706, #7c3aed, #0891b2' },
    { name: 'Neon',      bg: '#0d0d0d', grid: '#1a1a2e', traces: '#ff006e, #00f5d4, #fee440, #8338ec, #fb5607, #3a86ff' },
  ]

  // Settings state
  let plotBg     = $state(themes[0].bg)
  let gridColor  = $state(themes[0].grid)
  let traceColors = $state(themes[0].traces)
  let activeTheme = $state('Midnight')

  function applyTheme(t) {
    plotBg = t.bg
    gridColor = t.grid
    traceColors = t.traces
    activeTheme = t.name
  }
</script>

{#if open}
  <aside class="right-sidebar">
    <div class="right-sidebar-tabs">
      <button class="rs-tab" class:active={activePanel === 'settings'}
              onclick={() => activePanel = 'settings'}>Settings</button>
      <button class="rs-tab" class:active={activePanel === 'about'}
              onclick={() => activePanel = 'about'}>About</button>
    </div>

    {#if activePanel === 'settings'}
      <div class="rs-panel">
        <div class="rs-section-title">Theme</div>
        <div class="theme-grid">
          {#each themes as t}
            <button
              class="theme-btn" class:active={activeTheme === t.name}
              onclick={() => applyTheme(t)}
              title={t.name}
            >
              <div class="theme-preview" style="background:{t.bg};border-color:{t.grid}">
                {#each t.traces.split(',').slice(0, 3).map(c => c.trim()) as c}
                  <div class="theme-dot" style="background:{c}"></div>
                {/each}
              </div>
              <span class="theme-label">{t.name}</span>
            </button>
          {/each}
        </div>

        <div class="rs-section-title" style="margin-top:14px">Customize</div>
        <div class="rs-field">
          <label>Background</label>
          <div style="display:flex;align-items:center;gap:8px">
            <input type="color" bind:value={plotBg} oninput={() => activeTheme = 'Custom'} style="width:32px;height:24px;padding:0;border:1px solid #374151;border-radius:4px;background:none;cursor:pointer" />
            <span style="font-size:11px;color:#6b7280">{plotBg}</span>
          </div>
        </div>
        <div class="rs-field">
          <label>Grid</label>
          <div style="display:flex;align-items:center;gap:8px">
            <input type="color" bind:value={gridColor} oninput={() => activeTheme = 'Custom'} style="width:32px;height:24px;padding:0;border:1px solid #374151;border-radius:4px;background:none;cursor:pointer" />
            <span style="font-size:11px;color:#6b7280">{gridColor}</span>
          </div>
        </div>
        <div class="rs-field">
          <label>Trace colors (comma-separated)</label>
          <input type="text" bind:value={traceColors} oninput={() => activeTheme = 'Custom'} style="font-size:11px" />
        </div>
        <div style="display:flex;gap:4px;margin-top:4px;flex-wrap:wrap">
          {#each traceColors.split(',').map(c => c.trim()).filter(Boolean) as c}
            <div style="width:18px;height:18px;border-radius:3px;background:{c};border:1px solid #374151"></div>
          {/each}
        </div>
      </div>
    {:else}
      <div class="rs-panel">
        <div class="rs-section-title">DSPkit</div>
        <p style="font-size:12px;color:#94a3b8;line-height:1.5">
          A digital signal processing toolkit for structural health monitoring and vibration analysis.
        </p>
        <div class="rs-info-row">
          <span class="rs-info-label">Frontend</span>
          <span class="rs-info-value">Svelte 5 + Vite</span>
        </div>
        <div class="rs-info-row">
          <span class="rs-info-label">Backend</span>
          <span class="rs-info-value">FastAPI + DSPkit</span>
        </div>
        <div class="rs-info-row">
          <span class="rs-info-label">Charts</span>
          <span class="rs-info-value">Plotly.js</span>
        </div>
        <hr style="margin:10px 0" />
        <div class="rs-section-title">Modules</div>
        <div style="font-size:11px;color:#94a3b8;line-height:1.8">
          <div>Spectral analysis (FFT, PSD, CSD)</div>
          <div>Time-frequency (STFT, CWT, WVD)</div>
          <div>Signal decomposition (EMD, HHT)</div>
          <div>Peak detection & harmonics</div>
          <div>SHM indicators</div>
          <div>Multi-sensor correlation</div>
          <div>Frequency Domain Decomposition</div>
          <div>Statistical analysis</div>
        </div>
      </div>
    {/if}
  </aside>
{/if}

<style>
  .theme-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    margin-top: 6px;
  }
  .theme-btn {
    background: none;
    border: 2px solid transparent;
    border-radius: 6px;
    padding: 4px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    transition: border-color 0.15s;
  }
  .theme-btn:hover {
    border-color: #4b5563;
  }
  .theme-btn.active {
    border-color: #6366f1;
  }
  .theme-preview {
    width: 100%;
    aspect-ratio: 1.4;
    border-radius: 4px;
    border: 1px solid;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
  }
  .theme-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .theme-label {
    font-size: 10px;
    color: #94a3b8;
  }
</style>
