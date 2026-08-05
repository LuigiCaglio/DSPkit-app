<script>
  // The one place channels are chosen. Everything downstream — overlays, the
  // single-channel picker, pair pickers, FDD — reads this selection.
  let {
    columnNames = [],
    timeCol = -1,
    selected = $bindable([]),
  } = $props()

  let query = $state('')

  let available = $derived(
    columnNames.map((name, i) => ({ name, i })).filter(c => c.i !== timeCol)
  )
  // Search only earns its space once scanning the list stops being instant.
  let searchable = $derived(available.length > 8)
  let shown = $derived(
    query.trim()
      ? available.filter(c => c.name.toLowerCase().includes(query.trim().toLowerCase()))
      : available
  )

  function toggle(i) {
    selected = selected.includes(i)
      ? selected.filter(s => s !== i)
      : [...selected, i].sort((a, b) => a - b)
  }
  // "All" respects an active filter, so it reads as "all of what I'm looking at".
  function selectAll() {
    const merged = new Set([...selected, ...shown.map(c => c.i)])
    selected = [...merged].sort((a, b) => a - b)
  }
  function selectNone() {
    const drop = new Set(shown.map(c => c.i))
    selected = selected.filter(i => !drop.has(i))
  }
</script>

<div class="chan-select">
  <div class="chan-head">
    <span class="chan-title">Channels</span>
    <span class="chan-count">{selected.length}/{available.length}</span>
  </div>

  {#if searchable}
    <input class="chan-search" type="text" placeholder="Filter channels…" bind:value={query} />
  {/if}

  <div class="chan-actions">
    <button class="btn-ghost chan-action" onclick={selectAll}>All</button>
    <button class="btn-ghost chan-action" onclick={selectNone}>None</button>
  </div>

  <div class="chan-list">
    {#each shown as c (c.i)}
      <label class="chan-item" class:on={selected.includes(c.i)}>
        <input type="checkbox" checked={selected.includes(c.i)} onchange={() => toggle(c.i)} />
        <span class="chan-name" title={c.name}>{c.name}</span>
      </label>
    {:else}
      <div class="chan-empty">No channel matches “{query}”.</div>
    {/each}
  </div>

  {#if selected.length === 0}
    <div class="chan-warn">Select at least one channel to analyse.</div>
  {/if}
</div>

<style>
  .chan-select { padding: 0 12px; }
  .chan-head {
    display: flex; align-items: baseline; justify-content: space-between;
    margin-bottom: 6px;
  }
  .chan-title {
    font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
    color: var(--text-muted);
  }
  .chan-count { font-size: 11px; color: var(--text-muted); }
  .chan-search { width: 100%; font-size: 12px; margin-bottom: 6px; }
  .chan-actions { display: flex; gap: 6px; margin-bottom: 6px; }
  .chan-action { font-size: 11px; padding: 2px 8px; }
  .chan-list {
    max-height: 190px; overflow-y: auto;
    border: 1px solid var(--border); border-radius: var(--radius-sm);
  }
  .chan-item {
    display: flex; align-items: center; gap: 8px;
    padding: 4px 8px; cursor: pointer; font-size: 12px;
    color: var(--text-secondary);
  }
  .chan-item:hover { background: var(--bg-hover); }
  .chan-item.on { color: var(--text-primary); }
  .chan-item input { margin: 0; flex-shrink: 0; }
  .chan-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chan-empty, .chan-warn {
    font-size: 11px; color: var(--text-muted); padding: 6px 2px;
  }
  .chan-warn { color: var(--warning); }
</style>
