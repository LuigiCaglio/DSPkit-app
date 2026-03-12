<script>
  let { signalColX, timeCol, fsManual, loading, runAnalysis } = $props()
  let segment_duration = $state(null)
  let excess           = $state(true)

  function run() {
    runAnalysis('/api/indicators', {
      signal_col: signalColX,
      segment_duration: segment_duration || undefined,
      excess,
    })
  }
</script>

<div class="field">
  <label>Segment duration (s, blank=auto)</label>
  <input type="number" bind:value={segment_duration} min="0.01" step="0.1" placeholder="auto" style="width:80px" />
</div>
<div class="field">
  <label><input type="checkbox" bind:checked={excess} /> Excess kurtosis</label>
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run Indicators'}
</button>
