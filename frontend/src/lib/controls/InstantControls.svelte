<script>
  import { onMount } from 'svelte'
  let { signalCol, loading, runAnalysis, autoRun = false} = $props()

  function run() {
    runAnalysis('/api/instantaneous', { signal_col: signalCol })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })
</script>

<div class="status">Computes envelope, instantaneous phase, and instantaneous frequency via Hilbert transform.</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run Instantaneous'}
</button>
