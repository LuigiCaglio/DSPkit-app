<script>
  let { signalColX, signalColY, timeCol, fsManual, loading, runAnalysis, dualSignal } = $props()
  let window_  = $state('hann')
  let nperseg  = $state(1024)
  let noverlap = $state(null)

  function run() {
    runAnalysis('/api/spectral/csd', {
      signal_col_x: signalColX,
      signal_col_y: signalColY,
      window: window_,
      nperseg,
      noverlap: noverlap || undefined,
    })
  }
</script>

{#if !dualSignal}
  <div class="status">Requires at least 2 signal columns.</div>
{:else}
  <div class="field">
    <label>Window</label>
    <select bind:value={window_}>
      <option>hann</option><option>hamming</option><option>blackman</option><option>flattop</option><option>boxcar</option>
    </select>
  </div>
  <div class="field">
    <label>nperseg</label>
    <input type="number" bind:value={nperseg} min="16" step="1" />
  </div>
  <div class="field">
    <label>noverlap (blank=auto)</label>
    <input type="number" bind:value={noverlap} min="0" placeholder="auto" style="width:80px" />
  </div>
  <button class="btn btn-primary" onclick={run} disabled={loading}>
    {loading ? 'Running…' : 'Run CSD'}
  </button>
{/if}
