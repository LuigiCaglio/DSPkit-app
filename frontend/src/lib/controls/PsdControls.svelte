<script>
  import { onMount } from 'svelte'
  let { loading, runAnalysis, autoRun = false} = $props()
  let window_  = $state('hann')
  let nperseg  = $state(1024)
  let noverlap = $state(null)
  let scaling  = $state('density')

  function run() {
    runAnalysis('/api/spectral/psd', {
      window: window_,
      nperseg,
      noverlap: noverlap || undefined,
      scaling,
    })
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
  <label>nperseg</label>
  <input type="number" bind:value={nperseg} min="16" step="1" />
</div>
<div class="field">
  <label>noverlap (blank=auto)</label>
  <input type="number" bind:value={noverlap} min="0" placeholder="auto" style="width:80px" />
</div>
<div class="field">
  <label>Scaling</label>
  <select bind:value={scaling}>
    <option value="density">Density</option>
    <option value="spectrum">Spectrum</option>
  </select>
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run PSD'}
</button>
