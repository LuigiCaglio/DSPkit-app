<script>
  let { signalColX, signalColY, timeCol, fsManual, loading, runAnalysis, dualSignal } = $props()
  let normalize = $state(true)
  let maxLag    = $state(null)

  function run() {
    runAnalysis('/api/spectral/cross_correlation', {
      signal_col_x: signalColX,
      signal_col_y: signalColY,
      normalize,
      max_lag: maxLag || undefined,
    })
  }
</script>

{#if !dualSignal}
  <div class="status">Requires at least 2 signal columns. Assign Signal Y in the sidebar.</div>
{:else}
  <div class="checkbox-row">
    <input type="checkbox" id="norm-ccf" bind:checked={normalize} />
    <label for="norm-ccf" style="margin:0">Normalize</label>
  </div>
  <div class="field">
    <label>Max lag (s, blank=full)</label>
    <input type="number" bind:value={maxLag} min="0" step="0.01" placeholder="full" style="width:90px" />
  </div>
  <button class="btn btn-primary" onclick={run} disabled={loading}>
    {loading ? 'Running…' : 'Run Cross-correlation'}
  </button>
{/if}
