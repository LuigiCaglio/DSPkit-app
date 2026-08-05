<script>
  import { onMount } from 'svelte'
  let { loading, runAnalysis, dualSignal, autoRun = false} = $props()
  let window_       = $state('hann')
  let nperseg       = $state(1024)
  let prominence    = $state(null)
  let distance_hz   = $state(null)
  let max_peaks     = $state(null)
  let freq_min      = $state(null)
  let freq_max      = $state(null)
  let mac_threshold = $state(0.8)
  let n_crossings   = $state(10)

  function run() {
    runAnalysis('/api/fdd/analyze', {
      window: window_,
      nperseg,
      prominence: prominence || undefined,
      distance_hz: distance_hz || undefined,
      max_peaks: max_peaks || undefined,
      freq_min: freq_min || undefined,
      freq_max: freq_max || undefined,
      mac_threshold,
      n_crossings,
    })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun && dualSignal) run() })
</script>

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
  <label>Prominence (dB, blank=auto)</label>
  <input type="number" bind:value={prominence} min="0" step="0.5" placeholder="auto" style="width:80px" />
</div>
<div class="field">
  <label>Min distance (Hz)</label>
  <input type="number" bind:value={distance_hz} min="0" step="0.1" placeholder="auto" style="width:80px" />
</div>
<div class="field">
  <label>Max peaks</label>
  <input type="number" bind:value={max_peaks} min="1" step="1" placeholder="all" style="width:80px" />
</div>
<div class="field">
  <label>Freq range (Hz)</label>
  <div style="display:flex;gap:4px;align-items:center">
    <input type="number" bind:value={freq_min} min="0" step="0.1" placeholder="min" style="width:60px" />
    <span>–</span>
    <input type="number" bind:value={freq_max} min="0" step="0.1" placeholder="max" style="width:60px" />
  </div>
</div>
<div class="field">
  <label>MAC threshold</label>
  <input type="number" bind:value={mac_threshold} min="0" max="1" step="0.05" style="width:60px" />
</div>
<div class="field">
  <label>EFDD crossings</label>
  <input type="number" bind:value={n_crossings} min="2" step="1" style="width:60px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading || !dualSignal}>
  {loading ? 'Running…' : 'Run FDD'}
</button>
{#if !dualSignal}
  <div style="font-size:11px;color:var(--warning);margin-top:4px">Requires 2+ channels</div>
{:else}
  <div style="font-size:11px;color:var(--text-muted);margin-top:4px;max-width:190px">
    Output-only method — deselect excitation/force channels.
  </div>
{/if}
