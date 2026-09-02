<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'

  let { loading, runAnalysis, autoRun = false } = $props()

  const kept = paramsFor('autocorrelation', {
    normalize: true, maxLag: null,
    windows: ['parzen'], btMaxLag: null, btDecay: 3.0, showBt: false,
  })
  let normalize = $state(kept.normalize)
  let maxLag    = $state(kept.maxLag)
  let windows   = $state(kept.windows)
  let btMaxLag  = $state(kept.btMaxLag)
  let btDecay   = $state(kept.btDecay)
  let showBt    = $state(kept.showBt)
  let helpOpen  = $state(false)

  // Which windows keep the estimate non-negative. The unsafe ones are offered
  // because people look for them, not because they should be used.
  const WINDOWS = [
    { id: 'none',        label: 'None (rectangular)', safe: false },
    { id: 'bartlett',    label: 'Triangular (Bartlett)', safe: true },
    { id: 'parzen',      label: 'Parzen', safe: true },
    { id: 'exponential', label: 'Exponential', safe: true },
    { id: 'hann',        label: 'Hann', safe: false },
    { id: 'hamming',     label: 'Hamming', safe: false },
  ]
  function toggle(id) {
    windows = windows.includes(id) ? windows.filter(w => w !== id) : [...windows, id]
  }
  let anyUnsafe = $derived(
    windows.some(w => !WINDOWS.find(x => x.id === w)?.safe))

  function run() {
    runAnalysis('/api/spectral/autocorrelation', {
      normalize,
      max_lag: maxLag || undefined,
      lag_windows: JSON.stringify(showBt ? windows : []),
      bt_max_lag: btMaxLag || undefined,
      bt_decay: btDecay,
    })
  }
  onMount(() => { if (autoRun) run() })
  $effect(() => remember(kept, {
    normalize, maxLag, windows, btMaxLag, btDecay, showBt,
  }))
</script>

<div class="field">
  <label class="checkbox-row" style="margin-top:14px">
    <input type="checkbox" bind:checked={normalize} /> Normalise
  </label>
</div>

<div class="field">
  <label for="ac-lag">Max lag (s, blank = full)</label>
  <input id="ac-lag" type="number" bind:value={maxLag} min="0" step="0.5"
         placeholder="full" style="width:90px" />
</div>

<div class="field">
  <label class="checkbox-row" style="margin-top:14px">
    <input type="checkbox" bind:checked={showBt} />
    Spectrum from the ACF
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="About Blackman-Tukey" onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
</div>

{#if showBt}
  <div class="field">
    <label>Lag windows</label>
    <div class="frf-inputs">
      {#each WINDOWS as w}
        <button class="frf-chip" class:on={windows.includes(w.id)}
                class:unsafe={windows.includes(w.id) && !w.safe}
                onclick={() => toggle(w.id)}
                title={w.safe
                  ? 'Transform is non-negative, so the spectrum cannot go negative.'
                  : 'Transform has negative sidelobes — this can return negative power, which is not a possible value.'}>
          {w.label}{w.safe ? '' : ' ⚠'}
        </button>
      {/each}
    </div>
  </div>

  <div class="field">
    <label for="bt-lag">Lags used</label>
    <input id="bt-lag" type="number" bind:value={btMaxLag} min="8" step="64"
           placeholder="auto" style="width:90px" />
  </div>

  {#if windows.includes('exponential')}
    <div class="field">
      <label for="bt-decay">Exponential decay</label>
      <input id="bt-decay" type="number" bind:value={btDecay} min="0.5" max="20" step="0.5" style="width:80px" />
    </div>
  {/if}

  {#if anyUnsafe}
    <div class="status" style="max-width:290px;color:var(--warning)">
      A selected window has negative sidelobes in its own transform, so the
      spectrum it produces can go negative. The panel reports how much of it did.
    </div>
  {/if}
{/if}

{#if helpOpen}
  <div class="help-panel">
    The spectrum is the Fourier transform of the autocorrelation — a third route
    alongside the periodogram and Welch. What it buys you is the knob: the ACF
    at lag k is estimated from N−k sample pairs, so long lags get noisier, and a
    lag window trades resolution for variance explicitly. Fewer lags means a
    smoother, blunter spectrum.
    <br /><br />
    <b>A lag window is not a data window, and the usual advice inverts.</b> The
    biased ACF is positive semi-definite, so its transform cannot be negative.
    Tapering keeps that only if the window's own transform is non-negative —
    true for triangular, Parzen and exponential. Rectangular truncation, Hann
    and Hamming have negative sidelobes and can return <i>negative power</i>,
    which is not a possible value. Measured on a narrowband record: 30% of the
    spectrum negative with no window, 15% with Hamming, 0% with the safe three.
    <br /><br />
    Hann is the right default as a <i>data</i> window and the wrong choice as a
    <i>lag</i> window. Same name, opposite verdict, different domain.
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">&times;</button>
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run'}
</button>
