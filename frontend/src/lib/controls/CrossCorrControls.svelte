<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  import ChannelScope from '../ChannelScope.svelte'
  let {
    columnNames = [], selected = [],
    focusChannel = $bindable(null), pairX = $bindable(null), pairY = $bindable(null),
    loading, runAnalysis, runPairOverlay, dualSignal, autoRun = false,
  } = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('cross_correlation', {
    vsAll: false,
    normalize: true,
    maxLag: null,
  })
  let vsAll = $state(kept.vsAll)
  let normalize = $state(kept.normalize)
  let maxLag = $state(kept.maxLag)
  function run() {
    const params = { normalize, max_lag: maxLag || undefined }
    if (vsAll) runPairOverlay('/api/spectral/cross_correlation', params, pairX)
    else runAnalysis('/api/spectral/cross_correlation',
                     { ...params, signal_col_x: pairX, signal_col_y: pairY })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, { vsAll, normalize, maxLag }))
</script>

<!-- Own scope: 'vs all' turns the Y picker into a whole set. -->
<ChannelScope
  kind={vsAll ? 'ref' : 'pair'}
  {columnNames}
  {selected}
  bind:focus={focusChannel}
  bind:pairX
  bind:pairY
/>
<div class="checkbox-row">
  <input type="checkbox" id="vsall-CrossCorrControls" bind:checked={vsAll}
         disabled={selected.length < 2} />
  <label for="vsall-CrossCorrControls" style="margin:0"
         title="Cross-correlate the reference against every other selected channel, on one plot">
    vs all selected
  </label>
</div>

{#if !dualSignal}
  <div class="status" style="max-width:230px">With one channel selected this is the autocorrelation (X = Y).</div>
{/if}
<div class="checkbox-row">
  <input type="checkbox" id="norm-ccf" bind:checked={normalize} />
  <label for="norm-ccf" style="margin:0">Normalize</label>
</div>
<div class="field">
  <label>Max lag (s, blank=full)</label>
  <input type="number" bind:value={maxLag} min="0" step="0.01" placeholder="full" style="width:90px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run Cross-correlation'}
</button>
