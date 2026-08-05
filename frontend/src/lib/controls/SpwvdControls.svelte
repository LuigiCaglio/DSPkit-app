<script>
  let { signalCol, loading, runAnalysis } = $props()
  let lagSamples  = $state(null)
  let timeSamples = $state(null)

  function run() {
    runAnalysis('/api/timefreq/spwvd', {
      signal_col: signalCol,
      lag_samples:  lagSamples  || undefined,
      time_samples: timeSamples || undefined,
    })
  }
</script>

<div class="status" style="color:var(--warning)">
  ⚠ SPWVD is O(N²). Signal must be ≤ 2048 samples.
</div>
<div class="field">
  <label>Lag samples (blank=auto)</label>
  <input type="number" bind:value={lagSamples} min="1" placeholder="auto" style="width:90px" />
</div>
<div class="field">
  <label>Time samples (blank=auto)</label>
  <input type="number" bind:value={timeSamples} min="1" placeholder="auto" style="width:90px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run SPWVD'}
</button>
