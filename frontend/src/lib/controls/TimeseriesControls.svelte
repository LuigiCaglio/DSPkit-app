<script>
  let { signalColX, signalColY, dualSignal, timeCol, fsManual, loading, runAnalysis } = $props()

  function run() {
    runAnalysis('/api/signal/timeseries', {
      signal_col:   signalColX,
      ...(dualSignal ? { signal_col_y: signalColY } : {}),
    })
  }
</script>

<div class="status">
  Plots the signal(s) before and after preprocessing. Click legend items to toggle traces.
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Loading…' : 'Plot time series'}
</button>
