import { useEffect, useState } from 'react'
import { getSceneTranscript, summarizeScenes } from '../sceneTranscript.js'
import CollapsibleSection from './CollapsibleSection.js'

function formatTimestamp(value) {
  const seconds = Number(value)
  if (!Number.isFinite(seconds)) return '—'
  return `${Math.max(0, seconds).toFixed(2)}s`
}

function SceneCard({ scene, index, segments }) {
  const start = Number(scene.start)
  const end = Number(scene.end)
  const duration = Number.isFinite(start) && Number.isFinite(end)
    ? Math.max(0, end - start)
    : null
  const transcript = getSceneTranscript(scene, segments)
  const [imageUrl, setImageUrl] = useState(scene.keyframe || scene.keyframeFallback || null)
  useEffect(() => {
    setImageUrl(scene.keyframe || scene.keyframeFallback || null)
  }, [scene.keyframe, scene.keyframeFallback])

  return (
    <article style={{
      border: '1px solid #2a2a2a',
      borderRadius: '10px',
      overflow: 'hidden',
      background: '#151515',
    }}>
      <div style={{
        aspectRatio: '9/16',
        background: '#202020',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#777',
        fontSize: '0.8rem',
        textAlign: 'center',
        padding: '0.75rem',
      }}>
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={`Scene ${index + 1}, ${formatTimestamp(scene.start)} midpoint`}
            onError={() => {
              if (scene.keyframeFallback && imageUrl !== scene.keyframeFallback) {
                setImageUrl(scene.keyframeFallback)
              } else {
                setImageUrl(null)
              }
            }}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <span>{scene.keyframeFallback ? 'Image indisponible' : 'Pas de keyframe'}</span>
        )}
      </div>
      <div style={{ padding: '0.7rem' }}>
        <strong style={{ display: 'block', marginBottom: '0.3rem' }}>Scene {index + 1}</strong>
        <div style={{ color: '#bbb', fontSize: '0.85rem' }}>
          {formatTimestamp(scene.start)} → {formatTimestamp(scene.end)}
        </div>
        <div style={{ color: '#888', fontSize: '0.8rem', marginTop: '0.2rem' }}>
          Durée : {duration === null ? '—' : formatTimestamp(duration)}
        </div>
        <div style={{
          marginTop: '0.8rem',
          paddingTop: '0.65rem',
          borderTop: '1px solid #2a2a2a',
        }}>
          <div style={{ color: '#888', fontSize: '0.72rem', marginBottom: '0.3rem' }}>
            Transcription de la scène
          </div>
          {transcript ? (
            <p
              title={transcript}
              style={{ color: '#d0d0d0', fontSize: '0.82rem', lineHeight: 1.45 }}
            >
              {transcript}
            </p>
          ) : (
            <p style={{ color: '#666', fontSize: '0.82rem', lineHeight: 1.45 }}>
              Aucune parole détectée
            </p>
          )}
        </div>
      </div>
    </article>
  )
}

export default function SceneTimeline({ scenes, segments = [] }) {
  if (!Array.isArray(scenes) || scenes.length === 0) return null
  const summary = summarizeScenes(scenes, segments)

  return (
    <CollapsibleSection title="Detected scenes">
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: '1rem',
        flexWrap: 'wrap',
        marginBottom: '0.75rem',
      }}>
        <div>
          <p style={{ color: '#888', fontSize: '0.85rem' }}>
            Chaque carte relie une image au texte prononcé pendant le plan.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.9rem', color: '#aaa', fontSize: '0.78rem' }}>
          <span><strong style={{ color: '#f0f0f0' }}>{summary.count}</strong> scènes</span>
          <span><strong style={{ color: '#f0f0f0' }}>{formatTimestamp(summary.averageDuration)}</strong> en moyenne</span>
          <span><strong style={{ color: '#f0f0f0' }}>{summary.silentCount}</strong> sans parole</span>
        </div>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
        gap: '0.75rem',
      }}>
        {scenes.map((scene, index) => (
          <SceneCard
            key={`${scene.start}-${scene.end}-${index}`}
            scene={scene}
            index={index}
            segments={segments}
          />
        ))}
      </div>
    </CollapsibleSection>
  )
}
