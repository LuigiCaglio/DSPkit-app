<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { loading, runAnalysis, autoRun = false} = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('autocorrelation', {
    normalize: true,
    maxLag: null,
  })
  let normalize = $state(kept.normalize)
  let maxLag = $state(kept.maxLag)
  function run() {
    runAnalysis('/api/spectral/autocorrelation', {
      normalize,
      max_lag: maxLag || undefined,
    })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, { normalize, maxLag }))
</script>

<div class="checkbox-row">
  <input type="checkbox" id="norm-acf" bind:checked={normalize} />
  <label for="norm-acf" style="margin:0">Normalize</label>
</div>
<div class="field">
  <label>Max lag (s, blank=full)</label>
  <input type="number" bind:value={maxLag} min="0" step="0.01" placeholder="full" style="width:90px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run ACF'}
</button>
