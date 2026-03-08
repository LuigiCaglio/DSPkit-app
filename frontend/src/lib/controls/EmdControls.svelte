<script>
  let { signalColX, timeCol, fsManual, loading, runAnalysis } = $props()
  let maxImfs    = $state(null)
  let maxSifting = $state(10)

  function run() {
    runAnalysis('/api/emd/decompose', {
      signal_col: signalColX,
      max_imfs:    maxImfs    || undefined,
      max_sifting: maxSifting,
    })
  }
</script>

<div class="status" style="color:#fbbf24">⚠ EMD is slow for signals > 5000 samples.</div>
<div class="field">
  <label>Max IMFs (blank=all)</label>
  <input type="number" bind:value={maxImfs} min="1" placeholder="all" style="width:80px" />
</div>
<div class="field">
  <label>Max sifting iterations</label>
  <input type="number" bind:value={maxSifting} min="1" step="1" style="width:80px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run EMD'}
</button>
