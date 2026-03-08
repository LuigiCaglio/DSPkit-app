<script>
  let { signalColX, timeCol, fsManual, loading, runAnalysis } = $props()

  function run() {
    runAnalysis('/api/instantaneous', { signal_col: signalColX })
  }
</script>

<div class="status">Computes envelope, instantaneous phase, and instantaneous frequency via Hilbert transform.</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run Instantaneous'}
</button>
