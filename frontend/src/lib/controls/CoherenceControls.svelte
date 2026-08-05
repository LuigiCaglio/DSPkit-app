<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { pairX, pairY, loading, runAnalysis, dualSignal, autoRun = false} = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('coherence', {
    window_: 'hann',
    nperseg: 1024,
    noverlap: null,
  })
  let window_ = $state(kept.window_)
  let nperseg = $state(kept.nperseg)
  let noverlap = $state(kept.noverlap)
  function run() {
    runAnalysis('/api/spectral/coherence', {
      signal_col_x: pairX,
      signal_col_y: pairY,
      window: window_,
      nperseg,
      noverlap: noverlap || undefined,
    })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, { window_, nperseg, noverlap }))
</script>

{#if !dualSignal}
  <div class="status" style="max-width:230px">With one channel selected coherence is 1 everywhere (X = Y). Select a second channel to compare.</div>
{/if}
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
<div class="field">
  <label>noverlap (blank=auto)</label>
  <input type="number" bind:value={noverlap} min="0" placeholder="auto" style="width:80px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run Coherence'}
</button>
