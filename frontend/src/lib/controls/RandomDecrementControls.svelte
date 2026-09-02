<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'

  let {
    signalCol, columnNames = [], selected = [],
    loading, runAnalysis,
  } = $props()

  const kept = paramsFor('random_decrement', {
    levels: '0.5, 1.0, 1.5, 2.0',
    condition: 'level_up',
    segLen: null,
    bandLow: null,
    bandHigh: null,
    crossCol: null,
  })
  let levels    = $state(kept.levels)
  let condition = $state(kept.condition)
  let segLen    = $state(kept.segLen)
  let bandLow   = $state(kept.bandLow)
  let bandHigh  = $state(kept.bandHigh)
  let crossCol  = $state(kept.crossCol)
  let helpOpen  = $state(false)

  let parsed = $derived(
    levels.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v) && v > 0))

  function run() {
    runAnalysis('/api/response/random_decrement', {
      signal_col: signalCol,
      levels: JSON.stringify(parsed.length ? parsed : [1.0]),
      condition,
      segment_length: segLen || undefined,
      band_low: bandLow || undefined,
      band_high: bandHigh || undefined,
      cross_col: crossCol ?? undefined,
    })
  }
  $effect(() => remember(kept, {
    levels, condition, segLen, bandLow, bandHigh, crossCol,
  }))
</script>

<div class="field">
  <label for="rdt-lv">
    Trigger levels (× sd)
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="About random decrement" onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
  <input id="rdt-lv" type="text" bind:value={levels} style="width:140px" />
</div>

<div class="field">
  <label for="rdt-cond">Trigger on</label>
  <select id="rdt-cond" bind:value={condition}>
    <option value="level_up">Upward crossing of the level</option>
    <option value="level">Either crossing of the level</option>
    <option value="positive_point">Any point above the level</option>
    <option value="local_extremum">A peak above the level</option>
  </select>
</div>

<div class="field">
  <label for="rdt-band">Isolate a mode (Hz)</label>
  <div style="display:flex;align-items:center;gap:6px">
    <input id="rdt-band" type="number" bind:value={bandLow} min="0" step="0.5"
           placeholder="off" style="width:70px" />
    <span style="color:var(--text-muted);font-size:11px">to</span>
    <input type="number" bind:value={bandHigh} min="0" step="0.5"
           placeholder="off" style="width:70px" />
  </div>
</div>

<div class="field">
  <label for="rdt-seg">Segment length</label>
  <input id="rdt-seg" type="number" bind:value={segLen} min="32" step="64"
         placeholder="auto" style="width:85px" />
</div>

<div class="field">
  <label for="rdt-cross">Average channel (blank = same)</label>
  <select id="rdt-cross" bind:value={crossCol}>
    <option value={null}>— same channel —</option>
    {#each selected as c}
      {#if c !== signalCol}
        <option value={c}>{columnNames[c] ?? `Ch ${c}`}</option>
      {/if}
    {/each}
  </select>
</div>

{#if helpOpen}
  <div class="help-panel">
    Random decrement turns ambient vibration into a free-decay signature. Take
    many short segments that all begin from the same condition and average them:
    the random forcing is uncorrelated with the trigger and cancels, the
    structure's own response to that condition is identical every time and
    survives.
    <br /><br />
    <b>Several levels is the point.</b> For a linear system the normalised
    signature does not depend on where you trigger, so signatures that separate
    once normalised say the system is not behaving linearly — and damping that
    rises or falls with level is the classic amplitude-dependent signature. Each
    level is fitted separately so the comparison is a number, not just a picture.
    <br /><br />
    Higher levels give a cleaner starting state but fewer segments to average.
    Below about 100 segments the random part has not cancelled and the signature
    is still partly noise; the table says how many each level got.
    <br /><br />
    Averaging a <i>different</i> channel from the one triggered gives the cross
    signature — the equivalent of a cross-correlation, which is what mode shapes
    across an array need.
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">&times;</button>
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading || !parsed.length}>
  {loading ? 'Running…' : `Run (${parsed.length} level${parsed.length === 1 ? '' : 's'})`}
</button>
