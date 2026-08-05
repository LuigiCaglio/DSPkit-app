<script>
  import { onMount } from 'svelte'
  let { signalCol, loading, runAnalysis, autoRun = false} = $props()
  let filterType  = $state('lowpass')
  let cutoff      = $state(100)
  let low         = $state(50)
  let high        = $state(200)
  let freq        = $state(60)
  let order       = $state(4)
  let zeroPhase   = $state(true)

  const NEEDS_CUTOFF  = new Set(['lowpass', 'highpass'])
  const NEEDS_LOWHIGH = new Set(['bandpass', 'bandstop'])
  const NEEDS_FREQ    = new Set(['notch'])

  function run() {
    const extra = { signal_col: signalCol, filter_type: filterType, order, zero_phase: zeroPhase }
    if (NEEDS_CUTOFF.has(filterType))  extra.cutoff = cutoff
    if (NEEDS_LOWHIGH.has(filterType)) { extra.low = low; extra.high = high }
    if (NEEDS_FREQ.has(filterType))    extra.freq = freq
    runAnalysis('/api/filter/apply', extra)
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })
</script>

<div class="field">
  <label>Filter type</label>
  <select bind:value={filterType}>
    <option value="lowpass">Low-pass</option>
    <option value="highpass">High-pass</option>
    <option value="bandpass">Band-pass</option>
    <option value="bandstop">Band-stop</option>
    <option value="notch">Notch</option>
  </select>
</div>

{#if NEEDS_CUTOFF.has(filterType)}
  <div class="field">
    <label>Cutoff (Hz)</label>
    <input type="number" bind:value={cutoff} min="0.01" step="1" />
  </div>
{/if}
{#if NEEDS_LOWHIGH.has(filterType)}
  <div class="field">
    <label>Low (Hz)</label>
    <input type="number" bind:value={low} min="0.01" step="1" />
  </div>
  <div class="field">
    <label>High (Hz)</label>
    <input type="number" bind:value={high} min="0.01" step="1" />
  </div>
{/if}
{#if NEEDS_FREQ.has(filterType)}
  <div class="field">
    <label>Notch freq (Hz)</label>
    <input type="number" bind:value={freq} min="0.01" step="1" />
  </div>
{/if}

<div class="field">
  <label>Order</label>
  <input type="number" bind:value={order} min="1" max="16" step="1" style="width:60px" />
</div>
<div class="checkbox-row">
  <input type="checkbox" id="zero-phase" bind:checked={zeroPhase} />
  <label for="zero-phase" style="margin:0">Zero-phase</label>
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Apply Filter'}
</button>
