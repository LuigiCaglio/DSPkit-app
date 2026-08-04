<script>
  import {
    THEMES, SERIES_DARK, SERIES_LIGHT,
    themeState, themeById, setTheme, setCustom, plotTheme,
  } from './theme.svelte.js'

  let { open = $bindable(false) } = $props()

  let activePanel = $state('settings')

  // Live view of the resolved colours, so the swatches follow theme + overrides.
  let colors = $derived.by(() => { const _ = themeState.id, __ = themeState.custom; return plotTheme() })
  let seriesText = $state('')

  // Keep the free-text field in sync when a preset is picked.
  $effect(() => {
    const _ = themeState.id
    if (!themeState.custom?.series) seriesText = plotTheme().series.join(', ')
  })

  function applySeriesText(v) {
    seriesText = v
    const list = v.split(',').map(c => c.trim()).filter(Boolean)
    setCustom({ series: list.length ? list : undefined })
  }

  /** First three slots of the mode's palette, as a preview of the theme. */
  function previewSwatches(theme) {
    return (theme.mode === 'light' ? SERIES_LIGHT : SERIES_DARK).slice(0, 3)
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
          {#each THEMES as t}
            <button
              class="theme-btn"
              class:active={themeState.id === t.id && !themeState.custom}
              onclick={() => setTheme(t.id)}
              title={t.name}
            >
              <div class="theme-preview"
                   style="background:{t.tokens.plotBg};border-color:{t.tokens.plotGrid}">
                {#each previewSwatches(t) as c}
                  <div class="theme-dot" style="background:{c}"></div>
                {/each}
              </div>
              <span class="theme-label">{t.name}</span>
            </button>
          {/each}
        </div>

        <div class="rs-section-title" style="margin-top:14px">Customize plot</div>
        <div class="rs-field">
          <label for="cust-bg">Background</label>
          <div class="swatch-row">
            <input id="cust-bg" class="swatch-input" type="color"
                   value={colors.bg}
                   oninput={(e) => setCustom({ plotBg: e.currentTarget.value })} />
            <span class="swatch-value">{colors.bg}</span>
          </div>
        </div>
        <div class="rs-field">
          <label for="cust-grid">Grid</label>
          <div class="swatch-row">
            <input id="cust-grid" class="swatch-input" type="color"
                   value={colors.grid}
                   oninput={(e) => setCustom({ plotGrid: e.currentTarget.value })} />
            <span class="swatch-value">{colors.grid}</span>
          </div>
        </div>
        <div class="rs-field">
          <label for="cust-series">Series colours (comma-separated)</label>
          <input id="cust-series" type="text" style="font-size:11px"
                 value={seriesText}
                 oninput={(e) => applySeriesText(e.currentTarget.value)} />
        </div>
        <div class="swatch-strip">
          {#each colors.series as c}
            <div class="swatch-chip" style="background:{c}"></div>
          {/each}
        </div>

        {#if themeState.custom}
          <button class="btn-ghost" style="margin-top:8px"
                  onclick={() => setTheme(themeState.id)}>
            Reset to {themeById(themeState.id).name}
          </button>
          <div class="detect-note">
            Custom colours are not checked for contrast or colour-vision separation.
            The five presets are.
          </div>
        {/if}
      </div>
    {:else}
      <div class="rs-panel">
        <div class="rs-section-title">DSPkit</div>
        <p class="rs-text">
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
        <div class="rs-list">
          <div>Spectral analysis (FFT, PSD, CSD)</div>
          <div>Time-frequency (STFT, CWT, WVD)</div>
          <div>Signal decomposition (EMD, HHT)</div>
          <div>Peak detection &amp; harmonics</div>
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
    border-radius: var(--radius);
    padding: 4px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    transition: border-color var(--transition);
  }
  .theme-btn:hover { border-color: var(--border-light); }
  .theme-btn.active { border-color: var(--accent); }
  .theme-preview {
    width: 100%;
    aspect-ratio: 1.4;
    border-radius: var(--radius-sm);
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
    color: var(--text-secondary);
  }
</style>
