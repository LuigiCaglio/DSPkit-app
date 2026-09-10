<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { loading, runAnalysis, autoRun = false } = $props()

  const kept = paramsFor('timeseries', { showOriginal: true })
  let showOriginal = $state(kept.showOriginal)

  function run() {
    runAnalysis('/api/signal/timeseries', { include_raw: showOriginal })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })
  $effect(() => remember(kept, { showOriginal }))
</script>

<div class="field">
  <label>
    <input type="checkbox" bind:checked={showOriginal} onchange={run} />
    Show original behind
  </label>
</div>

<div class="status" style="max-width:320px">
  Plots selected signals before and after preprocessing. Click legend items to
  toggle traces. The original is only drawn when preprocessing is on — and it is
  worth turning off on a long record, because it is the larger half of what has
  to be sent, and most of it once the record has been resampled down.
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Loading…' : 'Plot time series'}
</button>
