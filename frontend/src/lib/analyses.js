// How many channels each analysis consumes. This drives which picker appears in
// the controls strip and whether "All selected" can fan out into a grid.
//
//   multi    — runs over every selected channel at once (overlaid or a matrix)
//   single   — one channel; may also be run per-channel as small multiples
//   pair     — inherently bivariate (X vs Y)
//   dynamic  — the control decides, because its mode changes the arity
//   none     — no channel input
export const SCOPE = {
  overview:          'multi',
  timeseries:        'multi',
  datatable:         'none',
  fft:               'multi',
  psd:               'multi',
  autocorrelation:   'multi',
  peaks:             'single',
  // 'dynamic': these can run as a single X→Y pair or as one reference against
  // every other selected channel, so the control renders its own picker.
  cross_correlation: 'dynamic',
  csd:               'dynamic',
  coherence:         'dynamic',
  filter:            'single',
  stft:              'single',
  cwt:               'single',
  wvd:               'single',
  spwvd:             'single',
  instantaneous:     'single',
  emd:               'single',
  hht:               'single',
  multisensor:       'multi',
  fdd:               'multi',
  statistics:        'dynamic',
  indicators:        'single',
}

export const scopeOf = (tab) => SCOPE[tab] ?? 'multi'

/** Sentinel for "run this single-channel analysis on every selected channel". */
export const ALL_CHANNELS = 'all'

/**
 * Analyses cheap enough to compute the moment their tab is opened, so a click
 * shows a result instead of an empty canvas and a Run button.
 *
 * Deliberately excluded: cwt, wvd, spwvd, emd and hht. WVD is O(N^2) and the
 * decompositions are iterative — auto-running those on a long record would
 * stall the app on a stray click. They keep an explicit Run.
 */
export const AUTORUN = new Set([
  'timeseries', 'fft', 'psd', 'autocorrelation', 'peaks',
  'cross_correlation', 'csd', 'coherence', 'filter', 'stft',
  'instantaneous', 'indicators', 'multisensor', 'fdd', 'statistics',
])

/** Tabs whose x-axis is time and whose traces are decimated for display. */
export const ZOOMABLE = new Set(['timeseries', 'filter', 'instantaneous'])

/** Tabs drawn as a time-frequency surface, sharing one set of scaling controls. */
export const HEATMAP = new Set(['stft', 'cwt', 'wvd', 'spwvd'])
