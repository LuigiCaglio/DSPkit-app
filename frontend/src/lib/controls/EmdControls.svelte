<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  let { signalCol, loading, runAnalysis } = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('emd', {
    maxImfs: null,
    maxSifting: 10,
  })
  let maxImfs = $state(kept.maxImfs)
  let maxSifting = $state(kept.maxSifting)
  function run() {
    runAnalysis('/api/emd/decompose', {
      signal_col: signalCol,
      max_imfs:    maxImfs    || undefined,
      max_sifting: maxSifting,
    })
  }

  $effect(() => remember(kept, { maxImfs, maxSifting }))
</script>

<div class="status" style="color:var(--warning)">⚠ EMD is slow for signals > 5000 samples.</div>
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
