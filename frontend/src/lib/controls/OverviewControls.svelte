<script>
  let { loading, runOverview, nSelected = 0 } = $props()
</script>

<div class="status" style="flex:1;min-width:220px">
  Time series, PSD and — with 2+ channels — FDD singular values, computed on the
  selected channels. Runs automatically when a file is loaded.
</div>
{#if nSelected < 2}
  <div style="font-size:11px;color:var(--text-muted)">FDD needs 2+ channels.</div>
{/if}
<button class="btn btn-primary" onclick={() => runOverview()} disabled={loading || nSelected === 0}>
  {loading ? 'Running…' : 'Refresh overview'}
</button>
