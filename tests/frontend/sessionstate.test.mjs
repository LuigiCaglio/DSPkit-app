// Restoring settings is only safe if the restore is checked against the file it
// is being applied to. A saved selection can outlive the shape of the data it
// was made for -- the file can be re-read with a different layout, or edited on
// disk to have fewer columns -- and restoring it blindly leaves every analysis
// failing on an out-of-range channel with nothing on screen to explain why.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  STATE_VERSION, applyState, buildState, debounce, defaultPreproc,
  relativeTime, shortPath,
} from '../../frontend/src/lib/sessionState.js'
import { ALL_CHANNELS } from '../../frontend/src/lib/analyses.js'

const saved = (over = {}) => ({
  version: STATE_VERSION,
  signalCols: [1, 2],
  focusChannel: 1,
  pairX: 1,
  pairY: 2,
  preproc: { ...defaultPreproc(), hpEnabled: true, hpCutoff: 7 },
  activeCategory: 'spectral',
  activeTab: 'psd',
  params: { psd: { nperseg: 4096 } },
  ...over,
})

const FILE = { nColumns: 5, timeCol: 0 }

test('a saved state round-trips through build and apply', () => {
  const blob = buildState({
    orientation: 'columns', headerRow: 0, timeCol: 0, fsManual: 1024,
    signalCols: [1, 2], focusChannel: 2, pairX: 1, pairY: 2,
    preproc: { ...defaultPreproc(), lpEnabled: true, lpCutoff: 200 },
    activeCategory: 'spectral', activeTab: 'fft',
    params: { fft: { window: 'hann' } },
  })
  const out = applyState(blob, FILE)
  assert.deepEqual(out.signalCols, [1, 2])
  assert.equal(out.focusChannel, 2)
  assert.equal(out.preproc.lpCutoff, 200)
  assert.equal(out.params.fft.window, 'hann')
  assert.equal(out.activeTab, 'fft')
})

test('buildState snapshots rather than aliasing the live objects', () => {
  const preproc = defaultPreproc()
  const signalCols = [1, 2]
  const blob = buildState({ signalCols, preproc, params: {} })
  signalCols.push(3)
  preproc.hpEnabled = true
  assert.deepEqual(blob.signalCols, [1, 2], 'the saved selection did not follow the live array')
  assert.equal(blob.preproc.hpEnabled, false, 'the saved chain did not follow the live object')
})

test('nothing to restore returns null rather than a half-built state', () => {
  assert.equal(applyState(null, FILE), null)
  assert.equal(applyState(undefined, FILE), null)
  assert.equal(applyState('nope', FILE), null)
  assert.equal(applyState([1, 2], FILE), null, 'an array is not a state blob')
})

test('a state from an older format is ignored', () => {
  assert.equal(applyState(saved({ version: 0 }), FILE), null)
  assert.equal(applyState(saved({ version: undefined }), FILE), null)
})

test('channels beyond the end of the file are dropped', () => {
  // The file shrank from 5 columns to 3 since this was saved.
  const out = applyState(saved({ signalCols: [1, 2, 4, 9] }), { nColumns: 3, timeCol: 0 })
  assert.deepEqual(out.signalCols, [1, 2])
})

test('a selection with nothing left in range falls back to defaults', () => {
  assert.equal(applyState(saved({ signalCols: [7, 8] }), { nColumns: 3, timeCol: 0 }), null)
})

test('the time column is never restored as a signal', () => {
  const out = applyState(saved({ signalCols: [0, 1, 2] }), FILE)
  assert.deepEqual(out.signalCols, [1, 2], 'column 0 is the time axis here')
})

test('a different time column is respected on the way back in', () => {
  const out = applyState(saved({ signalCols: [0, 1, 2] }), { nColumns: 5, timeCol: 2 })
  assert.deepEqual(out.signalCols, [0, 1])
})

test('duplicate channels collapse and the order is stable', () => {
  const out = applyState(saved({ signalCols: [3, 1, 3, 2] }), FILE)
  assert.deepEqual(out.signalCols, [1, 2, 3])
})

test('the focus and pair picks are pulled back onto selected channels', () => {
  const out = applyState(saved({ signalCols: [1, 2], focusChannel: 4, pairX: 9, pairY: 9 }), FILE)
  assert.equal(out.focusChannel, 1)
  assert.equal(out.pairX, 1)
  assert.equal(out.pairY, 2)
})

test('the all-channels sentinel survives, since it is not an index', () => {
  const out = applyState(saved({ focusChannel: ALL_CHANNELS }), FILE)
  assert.equal(out.focusChannel, ALL_CHANNELS)
})

test('a single selected channel pairs with itself rather than going out of range', () => {
  const out = applyState(saved({ signalCols: [2], focusChannel: 2, pairX: 2, pairY: 3 }), FILE)
  assert.deepEqual(out.signalCols, [2])
  assert.equal(out.pairX, 2)
  assert.equal(out.pairY, 2)
})

test('a partial preprocessing chain is filled in from the defaults', () => {
  // An old blob predating the notch controls must not leave them undefined --
  // buildPreprocUrl tests these flags directly.
  const out = applyState(saved({ preproc: { hpEnabled: true, hpCutoff: 3 } }), FILE)
  assert.equal(out.preproc.hpCutoff, 3)
  assert.equal(out.preproc.notchEnabled, false)
  assert.equal(out.preproc.zeroPhase, true)
  assert.equal(out.preproc.detrendOrder, 0)
})

test('a junk params blob does not become the params object', () => {
  assert.deepEqual(applyState(saved({ params: 'nope' }), FILE).params, {})
  assert.deepEqual(applyState(saved({ params: [1, 2] }), FILE).params, {})
  assert.deepEqual(applyState(saved({ params: null }), FILE).params, {})
})

test('a nonsense sample rate is not restored over a detected one', () => {
  assert.equal(applyState(saved({ fsManual: 0 }), FILE).fsManual, undefined)
  assert.equal(applyState(saved({ fsManual: -5 }), FILE).fsManual, undefined)
  assert.equal(applyState(saved({ fsManual: 'fast' }), FILE).fsManual, undefined)
  assert.equal(applyState(saved({ fsManual: 2048 }), FILE).fsManual, 2048)
})

test('a file with no columns cannot have a state applied to it', () => {
  assert.equal(applyState(saved(), { nColumns: 0, timeCol: -1 }), null)
  assert.equal(applyState(saved(), {}), null)
})

test('debounce writes once, with the value settled on', async () => {
  let calls = []
  const save = debounce((v) => calls.push(v), 5)
  save(1); save(2); save(3)
  assert.deepEqual(calls, [], 'nothing written while still typing')
  await new Promise(r => setTimeout(r, 25))
  assert.deepEqual(calls, [3], 'only the last value is written')
})

test('a cancelled debounce never fires', async () => {
  let calls = []
  const save = debounce((v) => calls.push(v), 5)
  save(1)
  save.cancel()
  await new Promise(r => setTimeout(r, 25))
  assert.deepEqual(calls, [])
})

test('flush writes immediately and cancels the pending write', async () => {
  let calls = []
  const save = debounce((v) => calls.push(v), 5)
  save(1)
  save.flush(2)
  assert.deepEqual(calls, [2])
  await new Promise(r => setTimeout(r, 25))
  assert.deepEqual(calls, [2], 'the superseded write did not also land')
})

test('relative times read as ages, not timestamps', () => {
  const now = 1_000_000
  assert.equal(relativeTime(now - 5, now), 'just now')
  assert.equal(relativeTime(now - 300, now), '5 min ago')
  assert.equal(relativeTime(now - 7200, now), '2 h ago')
  assert.equal(relativeTime(now - 3 * 86400, now), '3 d ago')
  assert.equal(relativeTime(undefined, now), '')
})

test('a long path is shortened from the front, keeping the filename', () => {
  const p = 'C:\\Users\\someone\\Desktop\\measurements\\2026\\bridge\\run_017.csv'
  const short = shortPath(p, 30)
  assert.ok(short.startsWith('…/'), short)
  assert.ok(short.endsWith('run_017.csv'), 'the filename is what identifies it')
  assert.ok(short.length <= 32, `too long: ${short}`)
})

test('a short path is left exactly as it is', () => {
  assert.equal(shortPath('C:\\data\\a.csv'), 'C:\\data\\a.csv')
  assert.equal(shortPath(null), '')
})
