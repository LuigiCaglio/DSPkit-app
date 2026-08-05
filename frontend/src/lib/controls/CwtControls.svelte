<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  let { signalCol, loading, runAnalysis } = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('cwt', {
    fMin: 1.0,
    fMax: null,
    nFreqs: 50,
    w: 6.0,
  })
  let fMin = $state(kept.fMin)
  let fMax = $state(kept.fMax)
  let nFreqs = $state(kept.nFreqs)
  let w = $state(kept.w)
  function run() {
    runAnalysis('/api/timefreq/cwt', {
      signal_col: signalCol,
      f_min: fMin,
      f_max: fMax || undefined,
      n_freqs: nFreqs,
      w,
    })
  }

  $effect(() => remember(kept, { fMin, fMax, nFreqs, w }))
</script>

<div class="field">
  <label>f min (Hz)</label>
  <input type="number" bind:value={fMin} min="0.001" step="0.1" />
</div>
<div class="field">
  <label>f max (Hz, blank=fs/4)</label>
  <input type="number" bind:value={fMax} min="0.01" placeholder="fs/4" style="width:90px" />
</div>
<div class="field">
  <label>n freqs</label>
  <input type="number" bind:value={nFreqs} min="5" max="500" step="1" />
</div>
<div class="field">
  <label>Morlet w</label>
  <input type="number" bind:value={w} min="1" step="0.5" style="width:70px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run CWT'}
</button>
