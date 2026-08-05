<script>
  // Shown in the controls strip, immediately above the plot: which channel(s)
  // the analysis about to run — and the result on screen — actually refer to.
  // Keeping this next to the Run button is the point; a channel choice hidden in
  // a sidebar is how the wrong trace ends up in a figure.
  let {
    kind = 'multi',              // 'multi' | 'single' | 'pair' | 'none'
    columnNames = [],
    selected = [],               // channel indices chosen in the sidebar
    focus = $bindable(null),     // 'single': channel index, or 'all'
    pairX = $bindable(null),
    pairY = $bindable(null),
  } = $props()

  const nameOf = (i) => columnNames[i] ?? `Ch ${i}`
</script>

{#if kind === 'multi'}
  <div class="scope scope-static" title={selected.map(nameOf).join(', ')}>
    <span class="scope-label">Channels</span>
    <span class="scope-value">
      {#if selected.length === 0}none selected
      {:else if selected.length <= 3}{selected.map(nameOf).join(', ')}
      {:else}all {selected.length} selected{/if}
    </span>
  </div>

{:else if kind === 'single'}
  <div class="field scope-field">
    <label for="scope-focus">Channel</label>
    <select id="scope-focus" bind:value={focus}>
      {#each selected as i}
        <option value={i}>{nameOf(i)}</option>
      {/each}
      {#if selected.length > 1}
        <option value="all">── All selected ({selected.length}) ──</option>
      {/if}
    </select>
  </div>

{:else if kind === 'ref'}
  <!-- One channel, but as the reference of a comparison rather than the subject
       of the analysis — and with no "All selected", which means something else
       here (see the overlay toggle in the pairwise controls). -->
  <div class="field scope-field">
    <label for="scope-ref">Reference</label>
    <select id="scope-ref" bind:value={pairX}>
      {#each selected as i}<option value={i}>{nameOf(i)}</option>{/each}
    </select>
  </div>

{:else if kind === 'pair'}
  <div class="field scope-field">
    <label for="scope-x">Channel X</label>
    <select id="scope-x" bind:value={pairX}>
      {#each selected as i}<option value={i}>{nameOf(i)}</option>{/each}
    </select>
  </div>
  <div class="scope-arrow">→</div>
  <div class="field scope-field">
    <label for="scope-y">Channel Y</label>
    <select id="scope-y" bind:value={pairY}>
      {#each selected as i}<option value={i}>{nameOf(i)}</option>{/each}
    </select>
  </div>
{/if}

<style>
  .scope {
    display: flex; flex-direction: column; gap: 2px;
    padding-right: 12px; margin-right: 4px;
    border-right: 1px solid var(--border);
    flex-shrink: 0;
  }
  .scope-label {
    font-size: 10px; text-transform: uppercase; letter-spacing: .07em;
    color: var(--text-muted);
  }
  .scope-value {
    font-size: 12px; color: var(--text-primary);
    max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .scope-field { flex-shrink: 0; }
  .scope-arrow {
    align-self: end; padding-bottom: 6px;
    color: var(--text-muted); font-size: 13px;
  }
</style>
