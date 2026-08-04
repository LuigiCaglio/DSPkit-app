<script>
  let { signalColX, timeCol, fsManual, loading, runAnalysis } = $props()

  function run() {
    runAnalysis('/api/timefreq/wvd', { signal_col: signalColX })
  }
</script>

<div class="status" style="color:var(--warning)">
  ⚠ WVD is O(N²). Signal must be ≤ 2048 samples.
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run WVD'}
</button>
