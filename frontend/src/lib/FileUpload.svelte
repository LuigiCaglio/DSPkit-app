<script>
  let { hasFile, filename, onfile } = $props()

  let dragover = $state(false)

  function handleFile(f) {
    if (f) onfile(f)
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
    <div style="font-size:12px;color:#a5b4fc;word-break:break-all">{filename}</div>
    <div class="upload-label">Click or drop to replace</div>
  {:else}
    <div style="font-size:22px">📂</div>
    <div style="margin-top:6px;font-size:13px">Drop a file or click</div>
    <div class="upload-label">CSV · TSV · TXT</div>
  {/if}
</div>
