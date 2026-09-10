<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'
  let { loading, runAnalysis, autoRun = false, checkSegments = null } = $props()
  // Settings persist across tab switches; see paramStore.
  const kept = paramsFor('psd', {
    method: 'welch',
    window_: 'hann',
    nperseg: 1024,
    noverlap: null,
    scaling: 'density',
    arOrder: 0,
    arMethod: 'burg',
    arCriterion: 'aic',
  })
  let method = $state(kept.method)
  let window_ = $state(kept.window_)
  let nperseg = $state(kept.nperseg)
  let noverlap = $state(kept.noverlap)
  let scaling = $state(kept.scaling)
  let arOrder = $state(kept.arOrder)
  let arMethod = $state(kept.arMethod)
  let arCriterion = $state(kept.arCriterion)

  function run() {
    runAnalysis('/api/spectral/psd', {
      method,
      window: window_,
      nperseg,
      noverlap: noverlap || undefined,
      scaling,
      ar_order: arOrder,
      ar_method: arMethod,
      ar_criterion: arCriterion,
    })
  }

  // Opening the tab computes with the current settings; the Run button is for
  // re-running after a change. Guarded so an expensive tab can opt out.
  onMount(() => { if (autoRun) run() })

  $effect(() => remember(kept, {
    method, window_, nperseg, noverlap, scaling, arOrder, arMethod, arCriterion,
  }))

  // ── the nperseg trade, answered on this record ─────────────────────────────
  //
  // nperseg is the one parameter here that can be wrong in two opposite ways,
  // and the app used to say so only in prose. This asks the library to weigh
  // both on the actual data: resolution against averages, with a verdict.
  let advice = $state(null)
  let checking = $state(false)
  async function check() {
    if (!checkSegments || checking) return
    checking = true
    advice = null
    try {
      advice = await checkSegments({ nperseg, window: window_,
                                     noverlap: noverlap || undefined })
    } finally {
      checking = false
    }
  }
  // A changed parameter invalidates the verdict; better blank than stale.
  $effect(() => { nperseg; window_; noverlap; advice = null })

  const VERDICT_LABEL = {
    ok: 'Good',
    marginal: 'Too coarse',
    unresolved: 'Peak not resolved',
    too_few: 'Too few averages',
    squeezed: 'Record too short',
  }
</script>

<div class="field">
  <label>Method</label>
  <select bind:value={method}>
    <option value="welch">Welch (averaged)</option>
    <option value="ar">AR model (Burg)</option>
  </select>
</div>

{#if method === 'welch'}
  <div class="field">
    <label>Window</label>
    <select bind:value={window_}>
      <option>hann</option><option>hamming</option><option>blackman</option><option>flattop</option><option>boxcar</option>
    </select>
  </div>
  <div class="field">
    <label>nperseg</label>
    <input type="number" bind:value={nperseg} min="16" step="1" />
  </div>
  <div class="field">
    <label>noverlap (blank=auto)</label>
    <input type="number" bind:value={noverlap} min="0" placeholder="auto" style="width:80px" />
  </div>
  <div class="field">
    <label>Scaling</label>
    <select bind:value={scaling}>
      <option value="density">Density</option>
      <option value="spectrum">Spectrum</option>
    </select>
  </div>
  {#if checkSegments}
    <div class="field">
      <button class="btn-ghost" onclick={check} disabled={checking || loading}>
        {checking ? 'Checking…' : 'Check nperseg'}
      </button>
    </div>
  {/if}
{:else}
  <div class="field">
    <label>Order (0 = choose)</label>
    <input type="number" bind:value={arOrder} min="0" step="1" style="width:90px" />
  </div>
  {#if !arOrder}
    <div class="field">
      <label>Criterion</label>
      <select bind:value={arCriterion}>
        <option value="aic">AIC</option>
        <option value="bic">BIC (lower orders)</option>
      </select>
    </div>
  {/if}
  <div class="field">
    <label>Estimator</label>
    <select bind:value={arMethod}>
      <option value="burg">Burg</option>
      <option value="yule_walker">Yule-Walker</option>
    </select>
  </div>
{/if}

{#if advice}
  <div class="status advice" class:bad={advice.verdict !== 'ok'} style="max-width:360px">
    <strong>{VERDICT_LABEL[advice.verdict] ?? advice.verdict}</strong> —
    {advice.advice}
  </div>
{:else if method === 'ar'}
  <div class="status" style="max-width:360px">
    Fits an all-pole model to the whole record instead of averaging segments, so
    it can separate two close peaks where Welch would need more data than you
    have. <strong>The order is the estimate</strong>: too low merges peaks, too
    high invents them. Check any peak that only this method shows against Welch
    before believing it, and expect notches to come out too shallow — an
    all-pole model represents resonances exactly and antiresonances only by
    cancellation.
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading}>
  {loading ? 'Running…' : 'Run PSD'}
</button>

<style>
  .advice { line-height: 1.45; }
  .advice.bad { color: var(--warning); }
</style>
