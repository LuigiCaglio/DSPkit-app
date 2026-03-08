<script>
  let { loading, runAnalysis } = $props()
  let window_ = $state('hann')
  let scaling  = $state('amplitude')

  function run() {
    runAnalysis('/api/spectral/fft', { window: window_, scaling })
  }
</script>

<div class="field">
  <label>Window</label>
  <select bind:value={window_}>
    <option>hann</option><option>hamming</option><option>blackman</option><option>flattop</option><option>boxcar</option>
  </select>
</div>
<div class="field">
  <label>Scaling</label>
  <select bind:value={scaling}>
    <option value="amplitude">Amplitude</option>
    <option value="rms">RMS</option>
  </select>
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run FFT'}
</button>
