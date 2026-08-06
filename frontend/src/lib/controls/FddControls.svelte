<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { loading, runAnalysis, dualSignal, autoRun = false} = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('fdd', {
    window_: 'hann',
    nperseg: 1024,
    prominence: null,
    distance_hz: null,
    max_peaks: null,
    freq_min: null,
    freq_max: null,
    mac_threshold: 0.8,
    n_crossings: 10,
    // Second gate on top of prominence: at a real mode one shape dominates, so
    // SV1 stands clear of SV2. 0 disables it and shows every prominent peak.
    min_dominance_db: 6,
  })
  let window_ = $state(kept.window_)
  let nperseg = $state(kept.nperseg)
  let prominence = $state(kept.prominence)
  let distance_hz = $state(kept.distance_hz)
  let max_peaks = $state(kept.max_peaks)
  let freq_min = $state(kept.freq_min)
  let freq_max = $state(kept.freq_max)
  let mac_threshold = $state(kept.mac_threshold)
  let n_crossings = $state(kept.n_crossings)
  let min_dominance_db = $state(kept.min_dominance_db)
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
      // Sent even at 0 — that is "show everything", not "use the default".
      min_dominance_db: min_dominance_db ?? 0,
    })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun && dualSignal) run() })

  $effect(() => remember(kept, { window_, nperseg, prominence, distance_hz, max_peaks, freq_min, freq_max, mac_threshold, n_crossings, min_dominance_db }))
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
  <label>Min prominence (dB)</label>
  <input type="number" bind:value={prominence} min="0" step="0.5" placeholder="6 (default)" style="width:80px" />
</div>
<div class="field">
  <label>Min SV1/SV2 (dB)</label>
  <input type="number" bind:value={min_dominance_db} min="0" step="0.5" style="width:80px" />
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
  <div class="status" style="max-width:250px">
    FDD takes the SVD of the cross-spectral matrix <em>between</em> sensors, so it
    needs at least 2 channels. Select another in the sidebar. For a single
    channel, use Spectral &gt; Peaks instead.
  </div>
{:else}
  <div style="font-size:11px;color:var(--text-muted);margin-top:4px;max-width:190px">
    Output-only method — deselect excitation/force channels.
    A peak must clear both thresholds to be reported; set either to 0 to see
    everything the picker found.
  </div>
{/if}
