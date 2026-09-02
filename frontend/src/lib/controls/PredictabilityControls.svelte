<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'

  let { loading, runAnalysis, dualSignal, autoRun = false, nSelected = 0 } = $props()

  const kept = paramsFor('predictability', { mode: 'multiple', nperseg: 1024 })
  let mode    = $state(kept.mode)
  let nperseg = $state(kept.nperseg)

  // Both quantities come from the inverse of the cross-spectral matrix, which is
  // only full rank with more Welch averages than channels. The library refuses
  // below that rather than returning confident nonsense; saying so here means
  // the user meets the rule before the run instead of after it.
  let enough = $derived(nSelected >= 3)

  function run() {
    runAnalysis('/api/multisensor/coherence_conditioned', { mode, nperseg })
  }
  onMount(() => { if (autoRun && enough) run() })
  $effect(() => remember(kept, { mode, nperseg }))
</script>

<div class="field">
  <label for="pred-mode">Question</label>
  <select id="pred-mode" bind:value={mode}>
    <option value="multiple">How much of each channel do the others explain?</option>
    <option value="partial">Which pairs are related directly?</option>
  </select>
</div>

<div class="field">
  <label for="pred-nperseg">nperseg</label>
  <input id="pred-nperseg" type="number" bind:value={nperseg} min="64" step="64" style="width:90px" />
</div>

{#if !enough}
  <div class="status" style="max-width:320px">
    Needs at least 3 channels — with two there is nothing to condition out, so
    ordinary coherence on the Cross-Signal tab is the right tool.
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading || !enough}>
  {loading ? 'Running…' : 'Run'}
</button>
