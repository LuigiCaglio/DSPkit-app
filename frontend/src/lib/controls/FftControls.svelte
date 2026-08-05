<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { loading, runAnalysis, autoRun = false} = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('fft', {
    window_: 'hann',
    scaling: 'amplitude',
  })
  let window_ = $state(kept.window_)
  let scaling = $state(kept.scaling)
  function run() {
    runAnalysis('/api/spectral/fft', { window: window_, scaling })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, { window_, scaling }))
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
