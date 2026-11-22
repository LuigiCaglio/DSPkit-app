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
  <label>Window length (s, blank = record / 100)</label>
  <input type="number" bind:value={segment_duration} min="0.01" step="0.1" placeholder="auto" style="width:80px" />
</div>
<div class="field">
  <label><input type="checkbox" bind:checked={excess} /> Excess kurtosis (Gaussian = 0, else 3)</label>
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>

<details class="ws-help" open>
  <summary>How to read it</summary>
  <p>The record is cut into equal, non-overlapping windows; each panel has one
     value per window, at the window's centre.</p>
  <dl>
    <dt>RMS</dt><dd>Level, in the signal's units. Steps show a change of
      excitation or a sensor that drops out.</dd>
    <dt>Crest factor</dt><dd>Peak / RMS. About 1.4 for a sine, 3–4 for
      random vibration; much higher means isolated spikes.</dd>
    <dt>Kurtosis</dt><dd>Shape of the amplitude distribution. 0 (excess) is
      Gaussian, −1.5 a sine; large positive values are impacts, bursts,
      handling.</dd>
    <dt>Dominant frequency</dt><dd>Peak of each window's spectrum. Steady
      means one line dominates; jumping means no single one does.</dd>
    <dt>Spectral entropy</dt><dd>How spread the power is: near 0 for one
      narrow line, near 1 for white noise.</dd>
  </dl>
</details>

<style>
  .ws-help { margin-top: 12px; font-size: 11.5px; color: var(--text-secondary); }
  .ws-help summary { cursor: pointer; color: var(--text-primary); margin-bottom: 4px; }
  .ws-help p { margin: 4px 0 6px; }
  .ws-help dl { margin: 0; }
  .ws-help dt { color: var(--text-primary); margin-top: 5px; }
  .ws-help dd { margin: 1px 0 0 0; }
</style>
