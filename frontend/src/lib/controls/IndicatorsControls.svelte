<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { signalCol, loading, runAnalysis, autoRun = false} = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('indicators', {
    segment_duration: null,
    excess: true,
  })
  let segment_duration = $state(kept.segment_duration)
  let excess = $state(kept.excess)
  function run() {
    runAnalysis('/api/indicators', {
      signal_col: signalCol,
      segment_duration: segment_duration || undefined,
      excess,
    })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, { segment_duration, excess }))
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
