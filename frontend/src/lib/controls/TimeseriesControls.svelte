<script>
  let { timeCol, fsManual, loading, runAnalysis } = $props()

  function run() {
    runAnalysis('/api/signal/timeseries', {})
  }
</script>

<div class="status">
  Plots selected signals before and after preprocessing. Click legend items to toggle traces.
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Loading…' : 'Plot time series'}
</button>
