<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { loading, runAnalysis, dualSignal, autoRun = false} = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('multisensor', {
    mode: 'correlation',
    window_: 'hann',
    nperseg: 1024,
  })
  let mode = $state(kept.mode)
  let window_ = $state(kept.window_)
  let nperseg = $state(kept.nperseg)
  function run() {
    if (mode === 'correlation') {
      runAnalysis('/api/multisensor/correlation', {})
    } else {
      runAnalysis('/api/multisensor/coherence_matrix', { window: window_, nperseg })
    }
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun && dualSignal) run() })

  $effect(() => remember(kept, { mode, window_, nperseg }))
</script>

<div class="field">
  <label>Analysis</label>
  <select bind:value={mode}>
    <option value="correlation">Correlation matrix</option>
    <option value="coherence">Coherence matrix</option>
  </select>
</div>
{#if mode === 'coherence'}
  <div class="field">
    <label>Window</label>
    <select bind:value={window_}>
      <option>hann</option><option>hamming</option><option>blackman</option><option>flattop</option><option>boxcar</option>
    </select>
  </div>
  <div class="field">
    <label>nperseg</label>
    <input type="number" bind:value={nperseg} min="16" step="1" />
  </div>
{/if}
<button class="btn btn-primary" onclick={run} disabled={loading || !dualSignal}>
  {loading ? 'Running…' : 'Run'}
</button>
{#if !dualSignal}
  <div class="status" style="max-width:250px">
    These are matrices <em>between</em> sensors, so they need at least 2 channels.
    Select another in the sidebar.
  </div>
{/if}
