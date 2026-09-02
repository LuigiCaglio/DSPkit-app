<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'

  let { signalCol, loading, runAnalysis, autoRun = false } = $props()

  const kept = paramsFor('response_spectrum', {
    tMin: 0.05, tMax: 5.0, nPeriods: 80, damping: '0.02, 0.05, 0.10',
  })
  let tMin = $state(kept.tMin)
  let tMax = $state(kept.tMax)
  let nPeriods = $state(kept.nPeriods)
  let damping = $state(kept.damping)
  let helpOpen = $state(false)

  function run() {
    const zs = damping.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v))
    runAnalysis('/api/response/spectrum', {
      signal_col: signalCol, t_min: tMin, t_max: tMax,
      n_periods: nPeriods, damping: JSON.stringify(zs.length ? zs : [0.05]),
    })
  }
  onMount(() => { if (autoRun) run() })
  $effect(() => remember(kept, { tMin, tMax, nPeriods, damping }))
</script>

<div class="field">
  <label for="rs-tmin">
    Period range (s)
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="About the response spectrum" onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
  <div style="display:flex;align-items:center;gap:6px">
    <input id="rs-tmin" type="number" bind:value={tMin} min="0.001" step="0.01" style="width:75px" />
    <span style="color:var(--text-muted);font-size:11px">to</span>
    <input type="number" bind:value={tMax} min="0.01" step="0.5" style="width:75px" />
  </div>
</div>

<div class="field">
  <label for="rs-n">Points</label>
  <input id="rs-n" type="number" bind:value={nPeriods} min="5" max="400" step="5" style="width:80px" />
</div>

<div class="field">
  <label for="rs-z">Damping ratios</label>
  <input id="rs-z" type="text" bind:value={damping} style="width:130px" />
</div>

{#if helpOpen}
  <div class="help-panel">
    The peak response of a family of single-degree-of-freedom oscillators to this
    record as base motion, plotted against their period. It answers "what would
    this shaking do to a structure of period T", which is why it is the standard
    summary of an earthquake record.
    <br /><br />
    <b>Pseudo is not true.</b> Pseudo-velocity and pseudo-acceleration are
    <i>defined</i> as w*Sd and w^2*Sd. They are close to the real peak velocity
    and acceleration at light damping and separate as damping rises, so both are
    computed and the toolbar chooses which to draw.
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">&times;</button>
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>
