<script>
  let { signalColX, timeCol, fsManual, loading, runAnalysis } = $props()
  let maxImfs    = $state(null)
  let maxSifting = $state(10)
  let nBins      = $state(512)

  function run() {
    runAnalysis('/api/emd/hht', {
      signal_col:  signalColX,
      max_imfs:    maxImfs    || undefined,
      max_sifting: maxSifting,
      n_bins:      nBins,
    })
  }
</script>

<div class="status" style="color:var(--warning)">⚠ HHT runs EMD first — slow for signals > 5000 samples.</div>
<div class="field">
  <label>Max IMFs (blank=all)</label>
  <input type="number" bind:value={maxImfs} min="1" placeholder="all" style="width:80px" />
</div>
<div class="field">
  <label>Max sifting iterations</label>
  <input type="number" bind:value={maxSifting} min="1" step="1" style="width:80px" />
</div>
<div class="field">
  <label>Marginal spectrum bins</label>
  <input type="number" bind:value={nBins} min="64" step="64" style="width:80px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run HHT'}
</button>
