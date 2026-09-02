<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import ChannelScope from '../ChannelScope.svelte'

  let {
    columnNames = [], selected = [],
    focusChannel = $bindable(null), pairX = $bindable(null), pairY = $bindable(null),
    loading, runAnalysis, dualSignal,
  } = $props()

  const kept = paramsFor('mutual_info', {
    k: 3, maxLagS: 0, nLags: 41, nSurrogates: 199, method: 'shift',
  })
  let k            = $state(kept.k)
  let maxLagS      = $state(kept.maxLagS)
  let nLags        = $state(kept.nLags)
  let nSurrogates  = $state(kept.nSurrogates)
  let method       = $state(kept.method)

  let helpOpen = $state(false)

  // The estimator runs once per lag per surrogate, so the two settings multiply.
  // Showing the product before the click is the difference between a considered
  // choice and a window that appears to have frozen.
  let evaluations = $derived((maxLagS > 0 ? Math.max(3, nLags) : 1) * Math.max(1, nSurrogates))
  let tooMany = $derived(evaluations > 400)

  function run() {
    runAnalysis('/api/crosssignal/mutual_information', {
      signal_col_x: pairX, signal_col_y: pairY,
      k, max_lag_s: maxLagS, n_lags: nLags,
      n_surrogates: nSurrogates, method,
    })
  }
  // Deliberately no auto-run: the surrogate test recomputes the estimate a
  // couple of hundred times, so opening the tab must not start it.
  $effect(() => remember(kept, { k, maxLagS, nLags, nSurrogates, method }))
</script>

<ChannelScope kind="pair" {columnNames} {selected}
              bind:focus={focusChannel} bind:pairX bind:pairY />

<div class="field">
  <label for="mi-lag">
    Max lag (s, 0 = no scan)
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="What is mutual information?"
            onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
  <input id="mi-lag" type="number" bind:value={maxLagS} min="0" step="0.1" style="width:90px" />
</div>

{#if maxLagS > 0}
  <div class="field">
    <label for="mi-nlags">Lag steps</label>
    <input id="mi-nlags" type="number" bind:value={nLags} min="3" max="401" step="2" style="width:80px" />
  </div>
{/if}

<div class="field">
  <label for="mi-k">Neighbours (k)</label>
  <input id="mi-k" type="number" bind:value={k} min="1" max="20" style="width:70px" />
</div>

<div class="field">
  <label for="mi-surr">Surrogates</label>
  <input id="mi-surr" type="number" bind:value={nSurrogates} min="19" max="999" step="10" style="width:80px" />
</div>

<div class="field">
  <label for="mi-method">Null by</label>
  <select id="mi-method" bind:value={method}>
    <option value="shift">Circular shift</option>
    <option value="permutation">Permutation</option>
  </select>
</div>

{#if helpOpen}
  <div class="help-panel">
    Mutual information measures <em>any</em> dependence between two channels,
    not only the linear, same-frequency kind coherence sees — a channel that is
    a squared or rectified version of another shows near-zero correlation and
    high mutual information. It is an estimate rather than a transform, so a
    value in nats means nothing on its own; it is read against a null built by
    surrogates that destroy the relationship while keeping each signal's own
    distribution. Circular shift preserves each signal's autocorrelation and is
    the safer null for a time series; permutation destroys it and will call
    weak dependence significant more often.
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">×</button>
  </div>
{/if}

<div class="status" style="max-width:300px">
  {evaluations.toLocaleString()} estimates
  ({maxLagS > 0 ? `${Math.max(3, nLags)} lags` : '1 lag'} × {nSurrogates} surrogates)
  {#if tooMany}
    <div class="mi-toomany">
      Too many — this would take minutes. Reduce the lag steps or the surrogates.
    </div>
  {/if}
</div>

<button class="btn btn-primary" onclick={run} disabled={loading || !dualSignal || tooMany}>
  {loading ? 'Running…' : 'Run'}
</button>
