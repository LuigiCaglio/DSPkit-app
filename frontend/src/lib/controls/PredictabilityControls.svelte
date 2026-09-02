<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { onMount } from 'svelte'

  let { loading, runAnalysis, dualSignal, autoRun = false, nSelected = 0 } = $props()

  const kept = paramsFor('predictability', { mode: 'multiple', nperseg: 1024 })
  let mode    = $state(kept.mode)
  let nperseg = $state(kept.nperseg)

  // Both quantities come from the inverse of the cross-spectral matrix, which is
  // only full rank with more Welch averages than channels. The library refuses
  // below that; saying so here means the user meets the rule before the run.
  let enough = $derived(nSelected >= 3)

  function run() {
    runAnalysis('/api/multisensor/coherence_conditioned', { mode, nperseg })
  }
  onMount(() => { if (autoRun && enough) run() })
  $effect(() => remember(kept, { mode, nperseg }))

  const HELP = {
    multiple:
      'Multiple coherence. For each channel, the share of it that all the other ' +
      'selected channels together explain, at each frequency. 1 means fully ' +
      'predictable from the rest; 0 means it carries information nothing else does. ' +
      'Use it to find a redundant sensor, or one doing its own thing.',
    partial:
      'Partial coherence. The relationship between two channels once every other ' +
      'selected channel has been conditioned out. It separates a direct link from ' +
      'one running through a third sensor: two channels can both follow a common ' +
      'source and look strongly related, while nothing passes between them.',
  }
</script>

<div class="field">
  <label for="pred-mode">
    Measure
    <span class="help-dot" title={HELP[mode]}>?</span>
  </label>
  <select id="pred-mode" bind:value={mode}>
    <option value="multiple">Multiple coherence</option>
    <option value="partial">Partial coherence</option>
  </select>
</div>

<div class="field">
  <label for="pred-nperseg">
    nperseg
    <span class="help-dot"
          title="Welch window length, in samples. It sets the frequency resolution (fs / nperseg) and how many segments are averaged. Both matter here and they pull against each other — see the note beside this control.">?</span>
  </label>
  <input id="pred-nperseg" type="number" bind:value={nperseg} min="64" step="64" style="width:90px" />
</div>

<div class="status" style="max-width:340px">
  {#if !enough}
    Needs at least 3 channels — with two there is nothing to condition out, so
    ordinary coherence on the Cross-Signal tab is the right tool.
  {:else}
    A lightly damped resonance can be narrower than one frequency bin, and
    coherence reads <em>low</em> there for that reason alone. If a peak you expect
    to be explained is not, raise nperseg and see whether it climbs. Raising it
    also leaves fewer segments to average, which lifts the whole curve — the
    library warns when that starts to matter.
  {/if}
</div>

<button class="btn btn-primary" onclick={run} disabled={loading || !enough}>
  {loading ? 'Running…' : 'Run'}
</button>
