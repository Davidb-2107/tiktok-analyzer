import { useState } from 'react'

export default function UrlInput({ onSubmit, onSubmitBatch, disabled }) {
  const [url, setUrl] = useState('')
  const [fps, setFps] = useState('auto')
  const [project, setProject] = useState('psycho')
  const [batch, setBatch] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    const proj = project === 'none' ? null : project
    // 'auto' -> fps null: the backend picks an adaptive frame budget from duration
    const fpsVal = fps === 'auto' ? null : Number(fps)
    if (batch) {
      const urls = url.split('\n').map(u => u.trim()).filter(Boolean)
      if (urls.length) {
        onSubmitBatch(urls, fpsVal, proj)
        setUrl('')
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

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
      {batch ? (
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
          placeholder="https://www.tiktok.com/@user/video/..."
          value={url}
          onChange={e => setUrl(e.target.value)}
          disabled={disabled}
          required
          style={inputStyle}
        />
      )}
      <button
        type="button"
        onClick={() => {
          // Leaving batch mode: keep only the first line — the hidden \n
          // would otherwise survive in state and be submitted inside one URL.
          if (batch) setUrl(u => u.split('\n')[0].trim())
          setBatch(b => !b)
        }}
        disabled={disabled}
        title="Toggle batch mode: submit several URLs at once (one per line)"
        style={{
          padding: '0.6rem 0.75rem',
          borderRadius: '6px',
          border: '1px solid #333',
          background: batch ? '#2a2a2a' : '#1a1a1a',
          color: batch ? '#f0f0f0' : '#888',
          cursor: 'pointer',
          fontSize: '0.95rem',
        }}
      >
        Batch
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
