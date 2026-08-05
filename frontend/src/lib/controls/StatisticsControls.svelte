<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  import ChannelScope from '../ChannelScope.svelte'

  // The only control whose channel arity changes with its own mode, so it
  // renders its own scope picker rather than letting AnalysisPanel guess.
  let {
    columnNames = [], selected = [],
    focusChannel = $bindable(null), pairX = $bindable(null), pairY = $bindable(null),
    loading, runAnalysis, dualSignal, autoRun = false,} = $props()

  // Settings persist across tab switches; see paramStore.

  const kept = paramsFor('statistics', {

    mode: 'pdf',

    bins: 50,

    bandwidth: null,

    percentile: 99,

  })

  let mode = $state(kept.mode)
  let bins = $state(kept.bins)
  let bandwidth = $state(kept.bandwidth)
  let percentile = $state(kept.percentile)
  const SCOPE_BY_MODE = {
    pdf:         'single',
    joint:       'pair',
    covariance:  'multi',
    mahalanobis: 'multi',
  }
  let scope = $derived(SCOPE_BY_MODE[mode])

  function run() {
    if (mode === 'pdf') {
      runAnalysis('/api/statistics/pdf', {
        signal_col: focusChannel,
        bins,
        bandwidth: bandwidth || undefined,
      })
    } else if (mode === 'joint') {
      runAnalysis('/api/statistics/joint', {
        signal_col_x: pairX,
        signal_col_y: pairY,
        bins,
      })
    } else if (mode === 'covariance') {
      runAnalysis('/api/statistics/covariance', {})
    } else if (mode === 'mahalanobis') {
      runAnalysis('/api/statistics/mahalanobis', { percentile })
    }
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })


  $effect(() => remember(kept, { mode, bins, bandwidth, percentile }))
</script>

<div class="field">
  <label>Analysis</label>
  <select bind:value={mode}>
    <option value="pdf">PDF / Histogram</option>
    <!-- Joint works against a single channel (X = Y); the two matrix methods
         are between-channel by definition and stay gated. -->
    <option value="joint">Joint distribution</option>
    <option value="covariance" disabled={!dualSignal}>Covariance matrix</option>
    <option value="mahalanobis" disabled={!dualSignal}>Mahalanobis distance</option>
  </select>
</div>

{#if !dualSignal && (mode === 'covariance' || mode === 'mahalanobis')}
  <div class="status" style="max-width:250px">
    Needs at least 2 channels — both describe how channels vary together.
  </div>
{/if}

<ChannelScope
  kind={scope}
  {columnNames}
  {selected}
  bind:focus={focusChannel}
  bind:pairX
  bind:pairY
/>

{#if mode === 'pdf'}
  <div class="field">
    <label>Bins</label>
    <input type="number" bind:value={bins} min="5" max="500" step="5" style="width:80px" />
  </div>
  <div class="field">
    <label>KDE bandwidth (blank=auto)</label>
    <input type="number" bind:value={bandwidth} min="0.001" step="0.01" placeholder="auto" style="width:80px" />
  </div>
{:else if mode === 'joint'}
  <div class="field">
    <label>Bins</label>
    <input type="number" bind:value={bins} min="5" max="500" step="5" style="width:80px" />
  </div>
{:else if mode === 'mahalanobis'}
  <div class="field">
    <label>Outlier percentile</label>
    <input type="number" bind:value={percentile} min="50" max="100" step="0.5" style="width:80px" />
  </div>
{/if}
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>
