<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'

  let { signalCol, loading, runAnalysis } = $props()

  const kept = paramsFor('log_decrement', { nPeaks: null, floor: 0.05 })
  let nPeaks = $state(kept.nPeaks)
  let floor = $state(kept.floor)
  let helpOpen = $state(false)

  function run() {
    runAnalysis('/api/response/log_decrement', {
      signal_col: signalCol,
      n_peaks: nPeaks || undefined,
      floor_fraction: floor,
    })
  }
  $effect(() => remember(kept, { nPeaks, floor }))
</script>

<div class="field">
  <label for="ld-floor">
    Noise floor
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="About log decrement" onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
  <input id="ld-floor" type="number" bind:value={floor} min="0.005" max="0.5" step="0.01" style="width:80px" />
</div>

<div class="field">
  <label for="ld-n">Max peaks (blank = all)</label>
  <input id="ld-n" type="number" bind:value={nPeaks} min="3" step="1" placeholder="all" style="width:80px" />
</div>

{#if helpOpen}
  <div class="help-panel">
    Damping from how fast a free vibration dies away. It needs a <b>decay</b> —
    hit the structure and let it ring, not a forced response. The fit runs
    through every peak rather than just the first and last, so one noisy peak
    cannot move the answer.
    <br /><br />
    The noise floor stops the fit where the decay disappears into the noise; past
    that the peaks are noise, and they flatten the estimate towards zero damping.
    Check R-squared <i>and</i> the peak count in the results: a good-looking fit
    through the wrong peaks is the failure to watch for, and it does not show up
    in R-squared alone.
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">&times;</button>
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>
