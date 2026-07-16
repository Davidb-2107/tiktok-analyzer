import { useState } from 'react'

export default function UrlInput({ onSubmit, onSubmitBatch, onSubmitChannel, disabled }) {
  const [url, setUrl] = useState('')
  const [topN, setTopN] = useState(5)
  const [fps, setFps] = useState('auto')
  const [project, setProject] = useState('psycho')
  const [mode, setMode] = useState('single') // 'single' | 'batch' | 'channel'

  const handleSubmit = (e) => {
    e.preventDefault()
    const proj = project === 'none' ? null : project
    // 'auto' -> fps null: the backend picks an adaptive frame budget from duration
    const fpsVal = fps === 'auto' ? null : Number(fps)
    if (mode === 'batch') {
      const urls = url.split('\n').map(u => u.trim()).filter(Boolean)
      if (urls.length) {
        onSubmitBatch(urls, fpsVal, proj)
        setUrl('')
      }
    } else if (mode === 'channel') {
      if (url.trim()) {
        // Same cap as /analyze/batch's 20-URL limit.
        const n = Math.max(1, Math.min(20, Number(topN) || 5))
        onSubmitChannel(url.trim(), n, fpsVal, proj)
      }
    } else if (url.trim()) {
      onSubmit(url.trim(), fpsVal, proj)
    }
  }

  const inputStyle = {
    flex: 1,
    minWidth: '280px',
    padding: '0.6rem 1rem',
    borderRadius: '6px',
    border: '1px solid #333',
    background: '#1a1a1a',
    color: '#f0f0f0',
    fontSize: '0.95rem',
  }

  const modeButtonStyle = (active) => ({
    padding: '0.6rem 0.75rem',
    borderRadius: '6px',
    border: '1px solid #333',
    background: active ? '#2a2a2a' : '#1a1a1a',
    color: active ? '#f0f0f0' : '#888',
    cursor: 'pointer',
    fontSize: '0.95rem',
  })

  const toggleMode = (next) => {
    // Leaving batch mode: keep only the first line — the hidden \n would
    // otherwise survive in state and be submitted inside one URL.
    if (mode === 'batch' && next !== 'batch') setUrl(u => u.split('\n')[0].trim())
    setMode(m => (m === next ? 'single' : next))
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
      {mode === 'batch' ? (
        <textarea
          placeholder={'One URL per line (max 20)\nhttps://www.tiktok.com/@user/video/...\nhttps://www.tiktok.com/@user/video/...'}
          value={url}
          onChange={e => setUrl(e.target.value)}
          disabled={disabled}
          required
          rows={4}
          style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
        />
      ) : (
        <input
          type="url"
          placeholder={
            mode === 'channel'
              ? 'https://www.tiktok.com/@channel (profile URL)'
              : 'https://www.tiktok.com/@user/video/...'
          }
          value={url}
          onChange={e => setUrl(e.target.value)}
          disabled={disabled}
          required
          style={inputStyle}
        />
      )}
      {mode === 'channel' && (
        <input
          type="number"
          min={1}
          max={20}
          value={topN}
          onChange={e => setTopN(e.target.value)}
          disabled={disabled}
          title="Top N videos by views (max 20)"
          style={{ ...inputStyle, flex: '0 0 90px', minWidth: '90px' }}
        />
      )}
      <button
        type="button"
        onClick={() => toggleMode('batch')}
        disabled={disabled}
        title="Toggle batch mode: submit several URLs at once (one per line)"
        style={modeButtonStyle(mode === 'batch')}
      >
        Batch
      </button>
      <button
        type="button"
        onClick={() => toggleMode('channel')}
        disabled={disabled}
        title="Toggle channel mode: fetch a channel's top-N videos by views"
        style={modeButtonStyle(mode === 'channel')}
      >
        Channel
      </button>
      <select
        value={fps}
        onChange={e => setFps(e.target.value)}
        disabled={disabled}
        style={{
          padding: '0.6rem 0.75rem',
          borderRadius: '6px',
          border: '1px solid #333',
          background: '#1a1a1a',
          color: '#f0f0f0',
          fontSize: '0.95rem',
        }}
      >
        <option value="auto">Auto fps (adaptive)</option>
        <option value={0.5}>0.5 fps (1 frame / 2s)</option>
        <option value={1}>1 fps</option>
        <option value={2}>2 fps</option>
      </select>
      <select
        value={project}
        onChange={e => setProject(e.target.value)}
        disabled={disabled}
        title="Which project this job belongs to (controls inbox routing)"
        style={{
          padding: '0.6rem 0.75rem',
          borderRadius: '6px',
          border: '1px solid #333',
          background: '#1a1a1a',
          color: '#f0f0f0',
          fontSize: '0.95rem',
        }}
      >
        <option value="psycho">Project: Psycho</option>
        <option value="archive">Project: Archive</option>
        <option value="none">Project: None</option>
      </select>
      <button
        type="submit"
        disabled={disabled}
        style={{
          padding: '0.6rem 1.5rem',
          borderRadius: '6px',
          border: 'none',
          background: disabled ? '#333' : '#fe2c55',
          color: '#fff',
          fontWeight: 600,
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontSize: '0.95rem',
        }}
      >
        Analyze
      </button>
    </form>
  )
}
