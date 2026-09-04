import test from 'node:test'
import assert from 'node:assert/strict'

import { getSceneTranscript, summarizeScenes } from './sceneTranscript.js'

test('collects transcript segments that overlap a scene', () => {
  const scene = { start: 2, end: 6 }
  const segments = [
    { start: 0, end: 2.5, text: 'before and overlap' },
    { start: 2.5, end: 4, text: 'inside' },
    { start: 3, end: 5, text: ' second phrase ' },
    { start: 6, end: 7, text: 'after' },
  ]

  assert.equal(getSceneTranscript(scene, segments), 'before and overlap inside second phrase')
})

test('summarizes scene count, average duration, and silent scenes', () => {
  const scenes = [
    { start: 0, end: 2 },
    { start: 2, end: 6 },
    { start: 6, end: 7 },
  ]
  const segments = [{ start: 0.5, end: 2.5, text: 'speech' }]

  assert.deepEqual(summarizeScenes(scenes, segments), {
    count: 3,
    averageDuration: 7 / 3,
    silentCount: 1,
  })
})
