<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'

  let { signalCol, loading, runAnalysis } = $props()

  const kept = paramsFor('log_decrement', {
    source: 'decay', nPeaks: null, floor: 0.05,
    bandLow: null, bandHigh: null, levelSd: 1.0, segLen: null, maxLag: null,
  })
  let source   = $state(kept.source)
  let nPeaks   = $state(kept.nPeaks)
  let floor    = $state(kept.floor)
  let bandLow  = $state(kept.bandLow)
  let bandHigh = $state(kept.bandHigh)
  let levelSd  = $state(kept.levelSd)
  let segLen   = $state(kept.segLen)
  let maxLag   = $state(kept.maxLag)
  let helpOpen = $state(false)

  function run() {
    runAnalysis('/api/response/log_decrement', {
      signal_col: signalCol,
      source,
      n_peaks: nPeaks || undefined,
      floor_fraction: floor,
      band_low: bandLow || undefined,
      band_high: bandHigh || undefined,
      rdt_level_sd: levelSd,
      segment_length: segLen || undefined,
      max_lag_s: maxLag || undefined,
    })
  }
  $effect(() => remember(kept, {
    source, nPeaks, floor, bandLow, bandHigh, levelSd, segLen, maxLag,
  }))
</script>

<div class="field">
  <label for="ld-src">
    From
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="Which route to use" onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
  <select id="ld-src" bind:value={source}>
    <option value="decay">A free decay (the record itself)</option>
    <option value="autocorrelation">Autocorrelation (ambient data)</option>
    <option value="random_decrement">Random decrement (ambient data)</option>
  </select>
</div>

<div class="field">
  <label for="ld-band">Isolate a mode (Hz)</label>
  <div style="display:flex;align-items:center;gap:6px">
    <input id="ld-band" type="number" bind:value={bandLow} min="0" step="0.5"
           placeholder="off" style="width:70px" />
    <span style="color:var(--text-muted);font-size:11px">to</span>
    <input type="number" bind:value={bandHigh} min="0" step="0.5"
           placeholder="off" style="width:70px" />
  </div>
</div>

{#if source === 'random_decrement'}
  <div class="field">
    <label for="ld-lvl">Trigger (× sd)</label>
    <input id="ld-lvl" type="number" bind:value={levelSd} min="0.1" max="4" step="0.1" style="width:75px" />
  </div>
  <div class="field">
    <label for="ld-seg">Segment length</label>
    <input id="ld-seg" type="number" bind:value={segLen} min="32" step="64"
           placeholder="auto" style="width:85px" />
  </div>
{:else}
  <div class="field">
    <label for="ld-lag">Use first (s)</label>
    <input id="ld-lag" type="number" bind:value={maxLag} min="0.1" step="0.5"
           placeholder="all" style="width:80px" />
  </div>
{/if}

<div class="field">
  <label for="ld-floor">Noise floor</label>
  <input id="ld-floor" type="number" bind:value={floor} min="0.005" max="0.5" step="0.01" style="width:80px" />
</div>

{#if helpOpen}
  <div class="help-panel">
    Log decrement measures damping from how fast a free vibration dies away — so
    it needs a <b>decay</b>. Ambient vibration is not one, and run on it directly
    the answer is meaningless (measured: 0.000% damping, R&sup2; 0.005).
    <br /><br />
    Two routes turn ambient data into a decay, and both are proportional to the
    free-decay response. <b>Autocorrelation</b> is the familiar one.
    <b>Random decrement</b> averages many segments that all start from the same
    trigger condition: the random forcing is uncorrelated with the trigger and
    averages away, the structure's own response does not. On a known 2.0% system
    they gave 2.16% and 1.97%.
    <br /><br />
    <b>Isolate a mode first.</b> The method assumes one decaying mode; a raw
    record has several, and they beat rather than decay. Band-pass around the
    peak you want before doing anything else.
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">&times;</button>
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>
