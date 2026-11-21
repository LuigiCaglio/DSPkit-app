<script>
  import DspkitLogo from './DspkitLogo.svelte'

  let { onclose } = $props()

  // Versions come from the running server, not from the build: the dspkit in
  // the venv can drift from the one the app was written against, and that is
  // exactly what someone opening About is trying to find out.
  let info  = $state(null)
  let error = $state(false)

  $effect(() => {
    fetch('/api/about')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => info = d)
      .catch(() => error = true)
  })

  function onkeydown(e) {
    if (e.key === 'Escape') onclose()
  }

  const v = (x) => x ?? '—'
</script>

<svelte:window {onkeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="about-backdrop" onclick={(e) => { if (e.target === e.currentTarget) onclose() }}>
  <div class="about-dialog" role="dialog" aria-modal="true" aria-labelledby="about-title">
    <button class="about-close" onclick={onclose} aria-label="Close">✕</button>

    <div class="about-head">
      <DspkitLogo size={64} />
      <div>
        <h2 id="about-title">DSPkit <span class="about-sub">GUI</span></h2>
        <div class="about-desc">Digital signal processing for time series data</div>
      </div>
    </div>

    <dl class="about-grid">
      <dt>Author</dt>
      <dd>
        Luigi Caglio
        <a href="https://orcid.org/0000-0002-9830-2490" target="_blank"
           rel="noopener noreferrer">ORCID ↗</a>
      </dd>

      <dt>App version</dt>
      <dd>{info ? v(info.app_version) : '…'}</dd>

      <dt>DSPkit library</dt>
      <dd>{info ? v(info.dspkit_version) : '…'}</dd>

      <dt>Runtime</dt>
      <dd class="about-muted">
        {#if info}
          Python {v(info.python_version)} · NumPy {v(info.numpy_version)} · SciPy {v(info.scipy_version)}
        {:else if error}
          could not reach the server
        {:else}
          …
        {/if}
      </dd>

      <dt>License</dt>
      <dd>MIT</dd>

      <dt>Cite</dt>
      <dd>
        <a href="https://doi.org/10.5281/zenodo.22257120" target="_blank"
           rel="noopener noreferrer">10.5281/zenodo.22257120 ↗</a>
      </dd>

      <dt>Source</dt>
      <dd class="about-links">
        <a href="https://github.com/LuigiCaglio/DSPkit-app" target="_blank"
           rel="noopener noreferrer">DSPkit-app ↗</a>
        <a href="https://github.com/LuigiCaglio/DSPkit" target="_blank"
           rel="noopener noreferrer">DSPkit library ↗</a>
        <a href="https://LuigiCaglio.github.io/DSPkit" target="_blank"
           rel="noopener noreferrer">Docs ↗</a>
      </dd>
    </dl>

    <p class="about-note">
      Runs entirely on this machine — files are read by a local process and
      never uploaded anywhere.
    </p>
  </div>
</div>

<style>
  .about-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, .55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 16px;
  }
  .about-dialog {
    position: relative;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    color: var(--text-primary);
    width: 100%;
    max-width: 460px;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    padding: 22px 24px 18px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, .4);
  }
  .about-close {
    position: absolute;
    top: 10px;
    right: 10px;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 14px;
    width: 26px;
    height: 26px;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }
  .about-close:hover { background: var(--bg-hover); color: var(--text-primary); }

  .about-head {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 18px;
  }
  h2 { font-size: 20px; font-weight: 600; }
  .about-sub { color: var(--text-muted); font-weight: 400; }
  .about-desc { color: var(--text-secondary); font-size: 13px; margin-top: 2px; }

  .about-grid {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 7px 16px;
    font-size: 13px;
  }
  dt { color: var(--text-muted); }
  dd { color: var(--text-primary); overflow-wrap: anywhere; }
  .about-muted { color: var(--text-secondary); font-size: 12px; }
  .about-links { display: flex; flex-wrap: wrap; gap: 4px 12px; }

  a { color: var(--accent-text); text-decoration: none; }
  a:hover { text-decoration: underline; }
  dd > a { margin-left: 6px; font-size: 12px; }
  .about-links > a, dd > a:only-child { margin-left: 0; }

  .about-note {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 12px;
    line-height: 1.5;
  }
</style>
