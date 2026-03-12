<script>
  let { open = $bindable(false) } = $props()

  let activePanel = $state('settings')

  // Settings state
  let plotBg     = $state('#13151f')
  let gridColor  = $state('#2d3148')
  let traceColors = $state('#6366f1, #f59e0b, #10b981, #f87171, #a78bfa, #06b6d4')
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
        <div class="rs-section-title">Plot colors</div>
        <div class="rs-field">
          <label>Background</label>
          <div style="display:flex;align-items:center;gap:8px">
            <input type="color" bind:value={plotBg} style="width:32px;height:24px;padding:0;border:1px solid #374151;border-radius:4px;background:none;cursor:pointer" />
            <span style="font-size:11px;color:#6b7280">{plotBg}</span>
          </div>
        </div>
        <div class="rs-field">
          <label>Grid</label>
          <div style="display:flex;align-items:center;gap:8px">
            <input type="color" bind:value={gridColor} style="width:32px;height:24px;padding:0;border:1px solid #374151;border-radius:4px;background:none;cursor:pointer" />
            <span style="font-size:11px;color:#6b7280">{gridColor}</span>
          </div>
        </div>
        <div class="rs-field">
          <label>Trace colors (comma-separated)</label>
          <input type="text" bind:value={traceColors} style="font-size:11px" />
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
