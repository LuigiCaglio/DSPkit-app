<script>
  let { signalColX, signalColY, timeCol, fsManual, loading, runAnalysis, dualSignal } = $props()
  let mode       = $state('pdf')
  let bins       = $state(50)
  let bandwidth  = $state(null)
  let percentile = $state(99)

  function run() {
    if (mode === 'pdf') {
      runAnalysis('/api/statistics/pdf', {
        signal_col: signalColX,
        bins,
        bandwidth: bandwidth || undefined,
      })
    } else if (mode === 'joint') {
      runAnalysis('/api/statistics/joint', {
        signal_col_x: signalColX,
        signal_col_y: signalColY,
        bins,
      })
    } else if (mode === 'covariance') {
      runAnalysis('/api/statistics/covariance', {})
    } else if (mode === 'mahalanobis') {
      runAnalysis('/api/statistics/mahalanobis', { percentile })
    }
  }
</script>

<div class="field">
  <label>Analysis</label>
  <select bind:value={mode}>
    <option value="pdf">PDF / Histogram</option>
    <option value="joint" disabled={!dualSignal}>Joint distribution</option>
    <option value="covariance" disabled={!dualSignal}>Covariance matrix</option>
    <option value="mahalanobis" disabled={!dualSignal}>Mahalanobis distance</option>
  </select>
</div>
{#if mode === 'pdf'}
  <div class="field">
    <label>Bins</label>
    <input type="number" bind:value={bins} min="5" max="500" step="5" style="width:80px" />
  </div>
  <div class="field">
    <label>KDE bandwidth (blank=auto)</label>
    <input type="number" bind:value={bandwidth} min="0.001" step="0.01" placeholder="auto" style="width:80px" />
  </div>
{:else if mode === 'joint'}
  <div class="field">
    <label>Bins</label>
    <input type="number" bind:value={bins} min="5" max="500" step="5" style="width:80px" />
  </div>
{:else if mode === 'mahalanobis'}
  <div class="field">
    <label>Outlier percentile</label>
    <input type="number" bind:value={percentile} min="50" max="100" step="0.5" style="width:80px" />
  </div>
{/if}
<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>
