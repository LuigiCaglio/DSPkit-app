<script>
  let { signalColX, timeCol, fsManual, loading, runAnalysis } = $props()
  let spectrum_type = $state('fft')
  let window_       = $state('hann')
  let nperseg       = $state(1024)
  let scaling       = $state('amplitude')
  let prominence    = $state(null)
  let distance_hz   = $state(null)
  let max_peaks     = $state(null)

  function run() {
    runAnalysis('/api/peaks/detect', {
      signal_col: signalColX,
      spectrum_type,
      window: window_,
      nperseg,
      scaling,
      prominence: prominence || undefined,
      distance_hz: distance_hz || undefined,
      max_peaks: max_peaks || undefined,
    })
  }
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
