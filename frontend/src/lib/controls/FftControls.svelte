<script>
  import { onMount } from 'svelte'
  let { loading, runAnalysis, autoRun = false} = $props()
  let window_ = $state('hann')
  let scaling  = $state('amplitude')

  function run() {
    runAnalysis('/api/spectral/fft', { window: window_, scaling })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })
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
