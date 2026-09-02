<script>
  import ChannelScope        from './ChannelScope.svelte'
  import { scopeOf, AUTORUN } from './analyses.js'
  import OverviewControls    from './controls/OverviewControls.svelte'
  import FftControls         from './controls/FftControls.svelte'
  import PsdControls         from './controls/PsdControls.svelte'
  import AutocorrControls    from './controls/AutocorrControls.svelte'
  import CrossCorrControls   from './controls/CrossCorrControls.svelte'
  import CsdControls         from './controls/CsdControls.svelte'
  import CoherenceControls   from './controls/CoherenceControls.svelte'
  import FilterControls      from './controls/FilterControls.svelte'
  import ExplorerControls    from './controls/ExplorerControls.svelte'
  import StftControls        from './controls/StftControls.svelte'
  import CwtControls         from './controls/CwtControls.svelte'
  import WvdControls         from './controls/WvdControls.svelte'
  import SpwvdControls       from './controls/SpwvdControls.svelte'
  import InstantControls     from './controls/InstantControls.svelte'
  import EmdControls         from './controls/EmdControls.svelte'
  import HhtControls         from './controls/HhtControls.svelte'
  import TimeseriesControls  from './controls/TimeseriesControls.svelte'
  import PeaksControls       from './controls/PeaksControls.svelte'
  import IndicatorsControls  from './controls/IndicatorsControls.svelte'
  import MultisensorControls from './controls/MultisensorControls.svelte'
  import PredictabilityControls from './controls/PredictabilityControls.svelte'
  import FddControls         from './controls/FddControls.svelte'
  import StatisticsControls  from './controls/StatisticsControls.svelte'

  let {
    activeTab, dualSignal, columnNames = [], selected = [],
    focusChannel = $bindable(null), pairX = $bindable(null), pairY = $bindable(null),
    loading, plotError, runAnalysis, runOverview, runPairOverlay, runExplorer,
  } = $props()

  let scope   = $derived(scopeOf(activeTab))
  let autoRun = $derived(AUTORUN.has(activeTab))
</script>

<div class="controls-area">
  <!-- Which channel(s) this run refers to, shown where the run happens.
       'dynamic' tabs render their own scope, because their arity depends on the
       mode picked inside the control. -->
  {#if scope !== 'none' && scope !== 'dynamic'}
    <ChannelScope
      kind={scope}
      {columnNames}
      {selected}
      bind:focus={focusChannel}
      bind:pairX
      bind:pairY
    />
  {/if}

  {#if activeTab === 'overview'}
    <OverviewControls {loading} {runOverview} nSelected={selected.length} />
  {:else if activeTab === 'datatable'}
    <div class="status">The raw values as parsed. Use "File layout" in the sidebar if a column looks wrong.</div>
  {:else if activeTab === 'timeseries'}
    <TimeseriesControls {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'fft'}
    <FftControls {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'psd'}
    <PsdControls {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'autocorrelation'}
    <AutocorrControls {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'cross_correlation'}
    <CrossCorrControls
      {columnNames} {selected} bind:focusChannel bind:pairX bind:pairY
      {runPairOverlay} {autoRun} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'csd'}
    <CsdControls
      {columnNames} {selected} bind:focusChannel bind:pairX bind:pairY
      {runPairOverlay} {autoRun} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'coherence'}
    <CoherenceControls
      {columnNames} {selected} bind:focusChannel bind:pairX bind:pairY
      {runPairOverlay} {autoRun} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'filter'}
    <FilterControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'explorer'}
    <ExplorerControls signalCol={focusChannel} {autoRun} {loading} {runExplorer} />
  {:else if activeTab === 'stft'}
    <StftControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'cwt'}
    <CwtControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'wvd'}
    <WvdControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'spwvd'}
    <SpwvdControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'instantaneous'}
    <InstantControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'emd'}
    <EmdControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'hht'}
    <HhtControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'peaks'}
    <PeaksControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'indicators'}
    <IndicatorsControls signalCol={focusChannel} {autoRun} {loading} {runAnalysis} />
  {:else if activeTab === 'multisensor'}
    <MultisensorControls {autoRun} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'predictability'}
    <PredictabilityControls {autoRun} {loading} {runAnalysis} {dualSignal} nSelected={selected.length} />
  {:else if activeTab === 'fdd'}
    <FddControls {autoRun} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'statistics'}
    <StatisticsControls
      {columnNames} {selected}
      bind:focusChannel bind:pairX bind:pairY
      {autoRun} {loading} {runAnalysis} {dualSignal}
    />
  {/if}

  {#if plotError}
    <div class="error" style="width:100%">Error: {plotError}</div>
  {/if}
</div>
