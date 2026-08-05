<script>
  import { onMount } from 'svelte'
  let { signalCol, loading, runAnalysis, autoRun = false} = $props()
  let segment_duration = $state(null)
  let excess           = $state(true)

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
