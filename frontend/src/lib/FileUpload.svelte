<script>
  let { hasFile, filename, onfile } = $props()

  let dragover = $state(false)
  let examples = $state([])
  let loadingExample = $state(false)

  async function fetchExamples() {
    try {
      const res = await fetch('/api/example-data')
      const data = await res.json()
      examples = data.examples ?? []
    } catch { /* ignore */ }
  }
  fetchExamples()

  function handleFile(f) {
    if (f) onfile(f)
  }

  async function loadExample(ex) {
    loadingExample = true
    try {
      const res = await fetch(`/api/example-data/${ex.id}`)
      const blob = await res.blob()
      const file = new File([blob], ex.filename, { type: 'text/csv' })
      onfile(file)
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
    <div class="upload-label">Click or drop to replace</div>
  {:else}
    <div class="upload-icon">📂</div>
    <div class="upload-title">Drop a file or click</div>
    <div class="upload-label">CSV · TSV · TXT</div>
  {/if}
</div>

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
