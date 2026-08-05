<script>
  let { preproc, onchange = null } = $props()
  let open = $state(true)

  // filtfilt runs the filter forwards and backwards, so the order you asked for
  // is doubled and the -3 dB point sits inside the nominal cutoff. Say so
  // rather than let the number on screen quietly mean something else.
  let effOrder = $derived(preproc.zeroPhase ? 2 : 1)

  const ORDERS = [2, 3, 4, 5, 6, 8]

  /** Re-run the current analysis when a setting actually changes. */
  const touched = () => onchange?.()
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
        <input type="checkbox" id="win-en" bind:checked={preproc.windowEnabled} onchange={touched} />
        <label for="win-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Window</label>
        {#if preproc.windowEnabled}
          <select bind:value={preproc.winUnit} onchange={touched} style="margin-left:auto;min-width:80px;font-size:11px;padding:3px 5px">
            <option value="samples">samples</option>
            <option value="time">seconds</option>
          </select>
        {/if}
      </div>
      {#if preproc.windowEnabled}
        <div style="display:flex;gap:6px;align-items:center">
          <input type="number" bind:value={preproc.winStart} onchange={touched} placeholder="start" min="0" step="1" style="width:72px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:12px">→</span>
          <input type="number" bind:value={preproc.winEnd} onchange={touched} placeholder="end" min="0" step="1" style="width:72px;font-size:12px" />
        </div>
      {/if}
    </div>

    <!-- Detrend — before the filters, so a DC offset or drift can't make a
         high-pass ring at the edges of the record. -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="dt-en" bind:checked={preproc.detrendEnabled} onchange={touched} />
        <label for="dt-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Detrend</label>
      </div>
      {#if preproc.detrendEnabled}
        <select bind:value={preproc.detrendOrder} onchange={touched}
                style="width:100%;font-size:12px">
          <option value={0}>Remove mean (DC)</option>
          <option value={1}>Remove linear trend</option>
          <option value={2}>Remove quadratic trend</option>
          <option value={3}>Remove cubic trend</option>
        </select>
      {/if}
    </div>

    <!-- High-pass -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="hp-en" bind:checked={preproc.hpEnabled} onchange={touched} />
        <label for="hp-en" style="margin:0;font-size:12px;color:var(--text-secondary)">High-pass filter</label>
      </div>
      {#if preproc.hpEnabled}
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" bind:value={preproc.hpCutoff} onchange={touched}
                 min="0.01" step="1" style="width:72px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:11px">Hz</span>
          <select bind:value={preproc.hpOrder} onchange={touched}
                  style="margin-left:auto;font-size:11px;padding:3px 5px" title="Filter order">
            {#each ORDERS as o}<option value={o}>order {o}</option>{/each}
          </select>
        </div>
      {/if}
    </div>

    <!-- Low-pass -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="lp-en" bind:checked={preproc.lpEnabled} onchange={touched} />
        <label for="lp-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Low-pass filter</label>
      </div>
      {#if preproc.lpEnabled}
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" bind:value={preproc.lpCutoff} onchange={touched}
                 min="0.01" step="1" style="width:72px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:11px">Hz</span>
          <select bind:value={preproc.lpOrder} onchange={touched}
                  style="margin-left:auto;font-size:11px;padding:3px 5px" title="Filter order">
            {#each ORDERS as o}<option value={o}>order {o}</option>{/each}
          </select>
        </div>
      {/if}
    </div>

    <!-- Notch — mains hum is 50 Hz here, 60 Hz in the Americas. -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="notch-en" bind:checked={preproc.notchEnabled} onchange={touched} />
        <label for="notch-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Notch</label>
      </div>
      {#if preproc.notchEnabled}
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" bind:value={preproc.notchFreq} onchange={touched}
                 min="0.01" step="1" style="width:72px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:11px">Hz</span>
          <input type="number" bind:value={preproc.notchQ} onchange={touched}
                 min="1" step="1" style="width:56px;font-size:12px;margin-left:auto"
                 title="Q — higher is a narrower notch" />
          <span style="color:var(--text-muted);font-size:11px">Q</span>
        </div>
      {/if}
    </div>

    <!-- Filtering mode, shared by every filter above -->
    <div>
      <div class="checkbox-row" style="margin-bottom:3px">
        <input type="checkbox" id="zp-en" bind:checked={preproc.zeroPhase} onchange={touched} />
        <label for="zp-en" style="margin:0;font-size:12px;color:var(--text-secondary)">
          Zero-phase (filtfilt)
        </label>
      </div>
      <div style="font-size:10.5px;color:var(--text-muted);line-height:1.4">
        {#if preproc.zeroPhase}
          No phase distortion or time shift — right for offline analysis.
          Applied twice, so the effective order is
          {preproc.hpEnabled ? preproc.hpOrder * effOrder : preproc.lpOrder * effOrder}
          and −3 dB sits inside the cutoff.
        {:else}
          Causal (single pass) — matches real-time behaviour, but delays the
          signal and distorts phase.
        {/if}
      </div>
    </div>

    <!-- Resample -->
    <div>
      <div class="checkbox-row" style="margin-bottom:5px">
        <input type="checkbox" id="rs-en" bind:checked={preproc.resampleEnabled} onchange={touched} />
        <label for="rs-en" style="margin:0;font-size:12px;color:var(--text-secondary)">Resample</label>
      </div>
      {#if preproc.resampleEnabled}
        <div style="display:flex;align-items:center;gap:6px">
          <input type="number" bind:value={preproc.targetFs} onchange={touched} min="1" step="1" style="width:80px;font-size:12px" />
          <span style="color:var(--text-muted);font-size:11px">Hz</span>
        </div>
      {/if}
    </div>

  </div>
{/if}
