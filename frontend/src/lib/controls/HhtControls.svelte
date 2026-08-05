<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  let { signalCol, loading, runAnalysis } = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('hht', {
    maxImfs: null,
    maxSifting: 10,
    nBins: 512,
  })
  let maxImfs = $state(kept.maxImfs)
  let maxSifting = $state(kept.maxSifting)
  let nBins = $state(kept.nBins)
  function run() {
    runAnalysis('/api/emd/hht', {
      signal_col:  signalCol,
      max_imfs:    maxImfs    || undefined,
      max_sifting: maxSifting,
      n_bins:      nBins,
    })
  }

  $effect(() => remember(kept, { maxImfs, maxSifting, nBins }))
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
