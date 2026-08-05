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
  const kept = paramsFor('csd', {
    vsAll: false,
    window_: 'hann',
    nperseg: 1024,
    noverlap: null,
  })
  let vsAll = $state(kept.vsAll)
  let window_ = $state(kept.window_)
  let nperseg = $state(kept.nperseg)
  let noverlap = $state(kept.noverlap)
  function run() {
    const params = { window: window_, nperseg, noverlap: noverlap || undefined }
    if (vsAll) runPairOverlay('/api/spectral/csd', params, pairX)
    else runAnalysis('/api/spectral/csd',
                     { ...params, signal_col_x: pairX, signal_col_y: pairY })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, { vsAll, window_, nperseg, noverlap }))
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
  <input type="checkbox" id="vsall-CsdControls" bind:checked={vsAll}
         disabled={selected.length < 2} />
  <label for="vsall-CsdControls" style="margin:0"
         title="Cross-spectrum of the reference against every other selected channel, on one plot">
    vs all selected
  </label>
</div>

{#if !dualSignal}
  <div class="status" style="max-width:230px">With one channel selected this is the power spectral density (X = Y).</div>
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
  {loading ? 'Running…' : 'Run CSD'}
</button>
