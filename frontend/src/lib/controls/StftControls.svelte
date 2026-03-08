<script>
  let { signalColX, timeCol, fsManual, loading, runAnalysis } = $props()
  let window_  = $state('hann')
  let nperseg  = $state(256)
  let noverlap = $state(null)

  function run() {
    runAnalysis('/api/timefreq/stft', {
      signal_col: signalColX,
      window: window_,
      nperseg,
      noverlap: noverlap || undefined,
    })
  }
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
  <label>noverlap (blank=75%)</label>
  <input type="number" bind:value={noverlap} min="0" placeholder="auto" style="width:80px" />
</div>
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run STFT'}
</button>
