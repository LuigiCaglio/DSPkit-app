<script>
  let { preproc } = $props()
  let open = $state(true)
</script>

<hr />
<div style="padding: 0 12px">
  <button
    class="sidebar-btn"
    style="padding:6px 0;width:100%;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--text-muted);display:flex;justify-content:space-between"
    onclick={() => open = !open}
  >
    Preprocessing
    <span>{open ? '▲' : '▼'}</span>
  </button>
</div>

{#if open}
  <div class="parse-opts" style="gap:10px">

    <!-- Window -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="win-en" bind:checked={preproc.windowEnabled} />
        <label for="win-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Window</label>
        {#if preproc.windowEnabled}
          <select bind:value={preproc.winUnit} style="margin-left:auto;min-width:80px;font-size:11px;padding:3px 5px">
            <option value="samples">samples</option>
            <option value="time">seconds</option>
          </select>
        {/if}
      </div>
      {#if preproc.windowEnabled}
        <div style="display:flex;gap:6px;align-items:center">
          <input type="number" bind:value={preproc.winStart} placeholder="start" min="0" step="1" style="width:72px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:12px">→</span>
          <input type="number" bind:value={preproc.winEnd} placeholder="end" min="0" step="1" style="width:72px;font-size:12px" />
        </div>
      {/if}
    </div>

    <!-- High-pass -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="hp-en" bind:checked={preproc.hpEnabled} />
        <label for="hp-en" style="margin:0;font-size:12px;color:var(--text-secondary)">High-pass filter</label>
      </div>
      {#if preproc.hpEnabled}
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" bind:value={preproc.hpCutoff} min="0.01" step="1" style="width:80px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:11px">Hz</span>
        </div>
      {/if}
    </div>

    <!-- Low-pass -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="lp-en" bind:checked={preproc.lpEnabled} />
        <label for="lp-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Low-pass filter</label>
      </div>
      {#if preproc.lpEnabled}
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" bind:value={preproc.lpCutoff} min="0.01" step="1" style="width:80px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:11px">Hz</span>
        </div>
      {/if}
    </div>

    <!-- Resample -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="rs-en" bind:checked={preproc.resampleEnabled} />
        <label for="rs-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Resample</label>
      </div>
      {#if preproc.resampleEnabled}
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" bind:value={preproc.targetFs} min="1" step="1" style="width:80px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:11px">Hz</span>
        </div>
      {/if}
    </div>

  </div>
{/if}
