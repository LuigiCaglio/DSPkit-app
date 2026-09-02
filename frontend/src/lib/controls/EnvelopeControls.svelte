<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'

  let { signalCol, loading, runAnalysis, autoRun = false, bandSweep = [] } = $props()

  const kept = paramsFor('envelope', {
    bandLow: null, bandHigh: null, nperseg: 4096, maxFreq: null,
  })
  let bandLow = $state(kept.bandLow)
  let bandHigh = $state(kept.bandHigh)
  let nperseg = $state(kept.nperseg)
  let maxFreq = $state(kept.maxFreq)
  let helpOpen = $state(false)

  // The most impulsive band is usually the one to demodulate, so the last run's
  // kurtosis sweep is offered as a one-click suggestion rather than left to
  // trial and error.
  let best = $derived(
    bandSweep.length
      ? bandSweep.reduce((a, b) => (b.kurtosis > a.kurtosis ? b : a))
      : null)

  function run() {
    runAnalysis('/api/envelope/spectrum', {
      signal_col: signalCol,
      band_low: bandLow || undefined,
      band_high: bandHigh || undefined,
      nperseg,
      max_freq: maxFreq || undefined,
    })
  }
  onMount(() => { if (autoRun) run() })
  $effect(() => remember(kept, { bandLow, bandHigh, nperseg, maxFreq }))
</script>

<div class="field">
  <label for="env-lo">
    Band (Hz)
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="About envelope analysis" onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
  <div style="display:flex;align-items:center;gap:6px">
    <input id="env-lo" type="number" bind:value={bandLow} min="0" step="10" placeholder="all" style="width:75px" />
    <span style="color:var(--text-muted);font-size:11px">to</span>
    <input type="number" bind:value={bandHigh} min="0" step="10" placeholder="all" style="width:75px" />
  </div>
</div>

{#if best}
  <div class="field">
    <label>Most impulsive band</label>
    <button class="btn-ghost" onclick={() => { bandLow = Math.round(best.low); bandHigh = Math.round(best.high) }}>
      {best.low.toFixed(0)}-{best.high.toFixed(0)} Hz (kurtosis {best.kurtosis.toFixed(1)})
    </button>
  </div>
{/if}

<div class="field">
  <label for="env-n">nperseg</label>
  <input id="env-n" type="number" bind:value={nperseg} min="256" step="256" style="width:90px" />
</div>

<div class="field">
  <label for="env-max">Show up to (Hz)</label>
  <input id="env-max" type="number" bind:value={maxFreq} min="1" step="10" placeholder="auto" style="width:80px" />
</div>

{#if helpOpen}
  <div class="help-panel">
    For finding a repeating impact buried under a resonance — a spalled bearing
    race, a chipped gear tooth. The impacts are weak and broadband, but they
    excite a resonance far above them and modulate it at the repetition rate. So
    the fault is not in the signal's spectrum, where the resonance dominates; it
    is in the spectrum of the signal's <b>envelope</b>, at the repetition rate
    and its harmonics.
    <br /><br />
    <b>The band is the method.</b> Pick it around the excited resonance. Too wide
    and the modulation is diluted by everything else; too narrow and the
    sidebands carrying it are filtered out with the noise. High kurtosis marks
    impulsiveness, which is why the most impulsive band is offered above.
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">&times;</button>
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>
