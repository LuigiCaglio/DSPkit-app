<script>
  import { onMount } from 'svelte'
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { TRANSFORMS, EXPENSIVE, EXPLORER_MAX_SAMPLES } from '../explorer.js'

  let { signalCol, loading, runExplorer, autoRun = false } = $props()

  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('explorer', {
    transform: 'stft',
    window_:   'hann',
    nperseg:   256,
    noverlap:  null,
    fMin:      1.0,
    fMax:      null,
    nFreqs:    50,
    w:         6.0,
    lagSamples:  null,
    timeSamples: null,
    threshold:   0.001,
  })

  let transform   = $state(kept.transform)
  let window_     = $state(kept.window_)
  let nperseg     = $state(kept.nperseg)
  let noverlap    = $state(kept.noverlap)
  let fMin        = $state(kept.fMin)
  let fMax        = $state(kept.fMax)
  let nFreqs      = $state(kept.nFreqs)
  let w           = $state(kept.w)
  let lagSamples  = $state(kept.lagSamples)
  let timeSamples = $state(kept.timeSamples)
  let threshold   = $state(kept.threshold)

  let expensive = $derived(EXPENSIVE.has(transform))

  /** The fields for whichever transform is selected. */
  function paramsOf(t) {
    if (t === 'stft')  return { window: window_, nperseg, noverlap: noverlap || undefined }
    if (t === 'fsst')  return { window: window_, nperseg,
                                noverlap: noverlap || undefined, threshold }
    if (t === 'cwt')   return { f_min: fMin, f_max: fMax || undefined, n_freqs: nFreqs, w }
    if (t === 'spwvd') return { lag_samples: lagSamples || undefined,
                                time_samples: timeSamples || undefined }
    return {}
  }

  function run() {
    runExplorer(transform, paramsOf(transform))
  }

  /**
   * Switching transform recomputes immediately for the cheap ones — flipping
   * between surfaces on the same data is the point of the tab, and making that
   * a two-click operation would defeat it. WVD and SPWVD keep an explicit Run
   * even capped, because "expensive" is a property of the record, not just the
   * sample count we chose.
   */
  function pick(id) {
    if (transform === id) return
    transform = id
    if (!EXPENSIVE.has(id)) run()
  }

  onMount(() => { if (autoRun && !expensive) run() })

  $effect(() => remember(kept, {
    transform, window_, nperseg, noverlap, fMin, fMax, nFreqs, w,
    lagSamples, timeSamples, threshold,
  }))
</script>

<div class="field">
  <label>Transform</label>
  <div class="xf-row">
    {#each TRANSFORMS as t}
      <button class="xf-btn" class:on={transform === t.id}
              onclick={() => pick(t.id)} disabled={loading}>{t.label}</button>
    {/each}
  </div>
</div>

{#if transform === 'stft' || transform === 'fsst'}
  <div class="field">
    <label>Window</label>
    <select bind:value={window_}>
      <option value="hann">Hann</option>
      <option value="hamming">Hamming</option>
      <option value="blackman">Blackman</option>
      <option value="boxcar">Rectangular</option>
    </select>
  </div>
  <div class="field">
    <label>nperseg</label>
    <input type="number" bind:value={nperseg} min="16" step="16" style="width:90px" />
  </div>
  <div class="field">
    <label>noverlap (blank = ¾)</label>
    <input type="number" bind:value={noverlap} min="0" placeholder="auto" style="width:90px" />
  </div>

  {#if transform === 'fsst'}
    <div class="field">
      <label>Noise gate (× peak)</label>
      <input type="number" bind:value={threshold} min="0" max="1" step="0.001"
             style="width:90px" />
    </div>
    <div class="status" style="font-size:11px;color:var(--text-muted)">
      Same window as STFT, with the smear removed. Bins below the gate are
      discarded rather than reassigned — where the magnitude is near zero the
      phase carries no frequency, only noise.
    </div>
  {/if}

{:else if transform === 'cwt'}
  <div class="field">
    <label>f min (Hz)</label>
    <input type="number" bind:value={fMin} min="0" step="0.1" style="width:90px" />
  </div>
  <div class="field">
    <label>f max (blank = Nyquist)</label>
    <input type="number" bind:value={fMax} min="0" placeholder="auto" style="width:90px" />
  </div>
  <div class="field">
    <label>n freqs</label>
    <input type="number" bind:value={nFreqs} min="8" step="1" style="width:90px" />
  </div>
  <div class="field">
    <label>Morlet w</label>
    <input type="number" bind:value={w} min="1" step="0.5" style="width:90px" />
  </div>

{:else if transform === 'spwvd'}
  <div class="field">
    <label>Lag samples (blank = auto)</label>
    <input type="number" bind:value={lagSamples} min="0" placeholder="auto" style="width:90px" />
  </div>
  <div class="field">
    <label>Time samples (blank = auto)</label>
    <input type="number" bind:value={timeSamples} min="0" placeholder="auto" style="width:90px" />
  </div>
{/if}

{#if expensive}
  <div class="status" style="color:var(--warning);font-size:11px">
    ⚠ O(N²) — the Explorer caps this at {EXPLORER_MAX_SAMPLES.toLocaleString()}
    samples from the middle of the record. The {transform.toUpperCase()} tab runs
    the full record.
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : `Run ${transform.toUpperCase()}`}
</button>

<style>
  .xf-row { display: flex; gap: 4px; flex-wrap: wrap; }
  .xf-btn {
    flex: 1 1 auto; min-width: 52px;
    font-size: 11px; padding: 4px 6px;
    background: var(--bg-hover); color: var(--text-secondary);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    cursor: pointer;
  }
  .xf-btn:hover:not(:disabled) { color: var(--text-primary); }
  .xf-btn.on {
    background: var(--accent); color: var(--accent-text, #fff);
    border-color: var(--accent);
  }
  .xf-btn:disabled { opacity: .5; cursor: default; }
</style>
