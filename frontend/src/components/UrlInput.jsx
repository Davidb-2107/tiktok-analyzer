import { useState } from 'react'

export default function UrlInput({ onSubmit, disabled }) {
  const [url, setUrl] = useState('')
  const [fps, setFps] = useState(1)
  const [project, setProject] = useState('psycho')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (url.trim()) onSubmit(url.trim(), fps, project === 'none' ? null : project)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
      <input
        type="url"
        placeholder="https://www.tiktok.com/@user/video/..."
        value={url}
        onChange={e => setUrl(e.target.value)}
        disabled={disabled}
        required
        style={{
          flex: 1,
          minWidth: '280px',
          padding: '0.6rem 1rem',
          borderRadius: '6px',
          border: '1px solid #333',
          background: '#1a1a1a',
          color: '#f0f0f0',
          fontSize: '0.95rem',
        }}
      />
      <select
        value={fps}
        onChange={e => setFps(Number(e.target.value))}
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
