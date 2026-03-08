<script>
  let { signalColX, signalColY, dualSignal, timeCol, fsManual, loading, runAnalysis } = $props()
  let normalize = $state(true)
  let maxLag    = $state(null)

  function run() {
    runAnalysis('/api/spectral/autocorrelation', {
      signal_col: signalColX,
      ...(dualSignal ? { signal_col_y: signalColY } : {}),
      normalize,
      max_lag: maxLag || undefined,
    })
  }
</script>

<div class="checkbox-row">
  <input type="checkbox" id="norm-acf" bind:checked={normalize} />
  <label for="norm-acf" style="margin:0">Normalize</label>
</div>
<div class="field">
  <label>Max lag (s, blank=full)</label>
  <input type="number" bind:value={maxLag} min="0" step="0.01" placeholder="full" style="width:90px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run ACF'}
</button>
