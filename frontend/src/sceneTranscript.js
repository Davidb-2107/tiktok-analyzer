function finiteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function getSceneTranscript(scene, segments) {
  const sceneStart = finiteNumber(scene?.start)
  const sceneEnd = finiteNumber(scene?.end)
  if (sceneStart === null || sceneEnd === null || sceneEnd <= sceneStart) return ''

  return (Array.isArray(segments) ? segments : [])
    .filter((segment) => {
      const start = finiteNumber(segment?.start)
      const end = finiteNumber(segment?.end)
      return start !== null && end !== null && end > sceneStart && start < sceneEnd
    })
    .map((segment) => String(segment.text ?? '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join(' ')
}

export function summarizeScenes(scenes, segments) {
  const validScenes = (Array.isArray(scenes) ? scenes : []).filter((scene) => {
    const start = finiteNumber(scene?.start)
    const end = finiteNumber(scene?.end)
    return start !== null && end !== null && end >= start
  })
  const totalDuration = validScenes.reduce(
    (total, scene) => total + Number(scene.end) - Number(scene.start),
    0,
  )

  return {
    count: validScenes.length,
    averageDuration: validScenes.length ? totalDuration / validScenes.length : 0,
    silentCount: validScenes.filter((scene) => !getSceneTranscript(scene, segments)).length,
  }
}
