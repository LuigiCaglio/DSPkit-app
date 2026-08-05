<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { signalCol, loading, runAnalysis, autoRun = false} = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('peaks', {
    spectrum_type: 'fft',
    window_: 'hann',
    nperseg: 1024,
    scaling: 'amplitude',
    prominence: null,
    distance_hz: null,
    max_peaks: null,
  })
  let spectrum_type = $state(kept.spectrum_type)
  let window_ = $state(kept.window_)
  let nperseg = $state(kept.nperseg)
  let scaling = $state(kept.scaling)
  let prominence = $state(kept.prominence)
  let distance_hz = $state(kept.distance_hz)
  let max_peaks = $state(kept.max_peaks)
  function run() {
    runAnalysis('/api/peaks/detect', {
      signal_col: signalCol,
      spectrum_type,
      window: window_,
      nperseg,
      scaling,
      prominence: prominence || undefined,
      distance_hz: distance_hz || undefined,
      max_peaks: max_peaks || undefined,
    })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, { spectrum_type, window_, nperseg, scaling, prominence, distance_hz, max_peaks }))
</script>

<div class="field">
  <label>Spectrum</label>
  <select bind:value={spectrum_type}>
    <option value="fft">FFT</option>
    <option value="psd">PSD</option>
  </select>
</div>
<div class="field">
  <label>Window</label>
  <select bind:value={window_}>
    <option>hann</option><option>hamming</option><option>blackman</option><option>flattop</option><option>boxcar</option>
  </select>
</div>
{#if spectrum_type === 'psd'}
  <div class="field">
    <label>nperseg</label>
    <input type="number" bind:value={nperseg} min="16" step="1" />
  </div>
{/if}
<div class="field">
  <label>Prominence (blank=auto)</label>
  <input type="number" bind:value={prominence} min="0" step="0.01" placeholder="auto" style="width:80px" />
</div>
<div class="field">
  <label>Min distance (Hz)</label>
  <input type="number" bind:value={distance_hz} min="0" step="0.1" placeholder="auto" style="width:80px" />
</div>
<div class="field">
  <label>Max peaks</label>
  <input type="number" bind:value={max_peaks} min="1" step="1" placeholder="all" style="width:80px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Detect Peaks'}
</button>
