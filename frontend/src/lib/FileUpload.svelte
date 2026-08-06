<script>
  import { relativeTime, shortPath } from './sessionState.js'

  let {
    hasFile, filename, sourcePath = null, sessionId = null,
    onfile, onopen, onclose,
  } = $props()

  let dragover = $state(false)
  let examples = $state([])
  let loadingExample = $state(false)
  let recent = $state([])
  let recentOpen = $state(false)
  let busyId = $state(null)

  async function fetchExamples() {
    try {
      const res = await fetch('/api/example-data')
      const data = await res.json()
      examples = data.examples ?? []
    } catch { /* ignore */ }
  }

  /**
   * Files opened before. Re-fetched when the list is shown rather than only on
   * mount, so opening something and coming back doesn't show a stale ordering.
   */
  async function fetchRecent() {
    try {
      const res = await fetch('/api/session/recent')
      const data = await res.json()
      recent = data.recent ?? []
    } catch { recent = [] }
  }

  fetchExamples()

  // Keyed on the session so the list is right after a file is opened, not just
  // at mount. On launch the app restores a session *after* this component
  // exists, so a one-shot fetch here showed an empty list and hid the section
  // entirely — including the entry for the file that had just been opened.
  $effect(() => {
    sessionId
    fetchRecent()
  })

  function handleFile(f) {
    if (f) onfile(f)
  }

  async function openRecent(entry) {
    if (!entry.available || busyId) return
    busyId = entry.session_id
    try {
      await onopen(entry)
      await fetchRecent()
    } finally {
      busyId = null
    }
  }

  async function loadExample(ex) {
    loadingExample = true
    try {
      const res = await fetch(`/api/example-data/${ex.id}`)
      const blob = await res.blob()
      const file = new File([blob], ex.filename, { type: 'text/csv' })
      onfile(file)
      await fetchRecent()
    } catch (e) {
      console.error('Failed to load example:', e)
    } finally {
      loadingExample = false
    }
  }

  function onDrop(e) {
    e.preventDefault()
    dragover = false
    const f = e.dataTransfer?.files?.[0]
    if (f) handleFile(f)
  }
</script>

<div
  class="upload-zone"
  class:dragover
  role="button"
  tabindex="0"
  ondragover={(e) => { e.preventDefault(); dragover = true }}
  ondragleave={() => dragover = false}
  ondrop={onDrop}
  onclick={() => document.getElementById('file-input').click()}
  onkeydown={(e) => e.key === 'Enter' && document.getElementById('file-input').click()}
>
  <input
    id="file-input"
    type="file"
    accept=".csv,.txt,.tsv"
    onchange={(e) => handleFile(e.target.files?.[0])}
  />
  {#if hasFile}
    <div class="upload-filename">{filename}</div>
    {#if sourcePath}
      <div class="upload-path" title={sourcePath}>{shortPath(sourcePath)}</div>
    {/if}
    <div class="upload-label">Click or drop to replace</div>
  {:else}
    <div class="upload-icon">📂</div>
    <div class="upload-title">Drop a file or click</div>
    <div class="upload-label">CSV · TSV · TXT</div>
  {/if}
</div>

{#if hasFile}
  <button class="btn-close-file" onclick={() => { onclose(); fetchRecent() }}>
    Close file
  </button>
{/if}

<!--
  Recent files — the point of the disk-backed sessions. Reopening yesterday's
  record is one click, and it comes back with the channels and preprocessing it
  was left with.
-->
{#if recent.length > 0}
  <div class="recent-section">
    <button
      class="recent-toggle"
      onclick={() => { recentOpen = !recentOpen; if (recentOpen) fetchRecent() }}
    >
      Recent files
      <span>{recentOpen ? '▲' : '▼'}</span>
    </button>
    {#if recentOpen}
      <div class="recent-list">
        {#each recent as entry (entry.session_id)}
          <button
            class="recent-item"
            disabled={!entry.available || busyId !== null}
            title={entry.available
              ? (entry.source_path ?? entry.filename)
              : 'This file has moved or been deleted'}
            onclick={() => openRecent(entry)}
          >
            <span class="recent-name">
              {entry.filename}
              {#if entry.changed}<span
                class="recent-flag"
                title="Changed on disk since it was opened"
              >•</span>{/if}
            </span>
            <span class="recent-meta">
              {#if busyId === entry.session_id}
                opening…
              {:else if !entry.available}
                missing
              {:else}
                {entry.n_columns ?? '?'} ch · {relativeTime(entry.opened_at)}
              {/if}
            </span>
            {#if entry.source_path}
              <span class="recent-path">{shortPath(entry.source_path, 34)}</span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  </div>
{/if}

{#if examples.length > 0 && !hasFile}
  <div class="example-section">
    <div class="example-hint">Or load an example:</div>
    {#each examples as ex}
      <button
        class="btn-example"
        onclick={(e) => { e.stopPropagation(); loadExample(ex) }}
        disabled={loadingExample}
      >
        {loadingExample ? 'Loading…' : ex.name}
      </button>
      <div class="example-desc">{ex.description}</div>
    {/each}
  </div>
{/if}

<style>
  .upload-path {
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 2px;
    word-break: break-all;
  }

  .btn-close-file {
    display: block;
    width: calc(100% - 24px);
    margin: 6px 12px 0;
    padding: 5px 0;
    font-size: 11px;
    color: var(--text-muted);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-close-file:hover {
    color: var(--text);
    border-color: var(--text-muted);
  }

  .recent-section {
    margin: 10px 12px 0;
  }

  .recent-toggle {
    display: flex;
    justify-content: space-between;
    width: 100%;
    padding: 6px 0;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: var(--text-muted);
    background: transparent;
    border: none;
    cursor: pointer;
  }

  .recent-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    max-height: 210px;
    overflow-y: auto;
  }

  .recent-item {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 6px 8px;
    text-align: left;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
  }
  .recent-item:hover:not(:disabled) {
    border-color: var(--text-muted);
  }
  .recent-item:disabled {
    cursor: default;
    opacity: .45;
  }

  .recent-name {
    font-size: 12px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* A file edited since it was last opened — worth knowing before trusting a
     result computed from the older contents. */
  .recent-flag {
    color: #e0a030;
    font-size: 14px;
    line-height: 1;
  }

  .recent-meta,
  .recent-path {
    font-size: 10px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
