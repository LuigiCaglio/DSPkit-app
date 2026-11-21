// Long lines go to WebGL in full-size charts, where SVG made panning crawl, but
// never in a small-multiples grid, which would run out of WebGL contexts.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot, lineType, GL_MIN_POINTS } from '../../frontend/src/lib/plotSpec.js'
import { T, timeseries } from './helpers.mjs'

test('lineType switches to WebGL only for long lines outside grid cells', () => {
  assert.equal(lineType(GL_MIN_POINTS + 1), 'scattergl')
  assert.equal(lineType(GL_MIN_POINTS), 'scatter')
  assert.equal(lineType(GL_MIN_POINTS + 1, true), 'scatter')
})

test('a long time series is drawn with WebGL, a short one with SVG', () => {
  const long = buildPlot('timeseries', timeseries(20, 1000), { T, colors: T.series })
  assert.ok(long.traces.every(tr => tr.type === 'scattergl'))
  const short = buildPlot('timeseries', timeseries(1, 1000), { T, colors: T.series })
  assert.ok(short.traces.every(tr => tr.type === 'scatter'))
})

test('a grid cell stays on SVG however long the line', () => {
  const cell = buildPlot('timeseries', timeseries(20, 1000), { T, colors: T.series, cell: true })
  assert.ok(cell.traces.every(tr => tr.type === 'scatter'))
})
