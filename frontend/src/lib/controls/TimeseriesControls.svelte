<script>
  import { onMount } from 'svelte'
  let { loading, runAnalysis, autoRun = false} = $props()

  function run() {
    runAnalysis('/api/signal/timeseries', {})
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })
</script>

<div class="status">
  Plots selected signals before and after preprocessing. Click legend items to toggle traces.
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Loading…' : 'Plot time series'}
</button>
