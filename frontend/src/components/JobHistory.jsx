import { useState } from 'react'

const API = import.meta.env.VITE_API_URL || ''

export default function JobHistory({ jobs, onSelect, onDelete, onRefreshComplete, showToast }) {
  const [query, setQuery] = useState('')
  const [refreshingAll, setRefreshingAll] = useState(false)
  const [refreshProgress, setRefreshProgress] = useState({ current: 0, total: 0 })

  if (jobs.length === 0) return null

  const q = query.trim().toLowerCase()
  const filteredJobs = q
    ? jobs.filter(job => {
        const url = (job.url || '').toLowerCase()
        const handle = (job.author_handle || job.handle || job.author || '').toLowerCase()
        return url.includes(q) || handle.includes(q)
      })
    : jobs

  const handleDelete = async (e, job_id) => {
    e.stopPropagation()
    try {
      const res = await fetch(`${API}/jobs/${job_id}`, { method: 'DELETE' })
      onDelete(job_id)
      showToast && showToast(res.ok ? 'Job deleted' : `Delete failed: HTTP ${res.status}`)
    } catch (err) {
      showToast && showToast(`Delete failed: ${err.message || err}`)
    }
  }

  const handleRefreshAll = async () => {
    if (refreshingAll) return
    const targets = filteredJobs.filter(j => j.status === 'done')
    if (targets.length === 0) return
    setRefreshingAll(true)
    setRefreshProgress({ current: 0, total: targets.length })
    let failures = 0
    try {
      for (let i = 0; i < targets.length; i++) {
        const job = targets[i]
        try {
          const res = await fetch(`${API}/jobs/${job.job_id}/refresh-metrics`, { method: 'POST' })
          if (!res.ok) failures++
        } catch {
          failures++
        }
        setRefreshProgress({ current: i + 1, total: targets.length })
      }
      if (onRefreshComplete) await onRefreshComplete()
      showToast && showToast(
        failures === 0
          ? `Refreshed ${targets.length} jobs`
          : `Refreshed ${targets.length - failures}/${targets.length} (${failures} failed)`
      )
    } finally {
      setRefreshingAll(false)
      setRefreshProgress({ current: 0, total: 0 })
    }
  }

  const doneCount = filteredJobs.filter(j => j.status === 'done').length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#aaa', margin: 0 }}>
          History
        </h2>
        {doneCount > 0 && (
          <button
            onClick={handleRefreshAll}
            disabled={refreshingAll}
            title="Re-poll yt-dlp metrics for every done job in the current filter"
            style={{
              padding: '0.3rem 0.6rem',
              borderRadius: '6px',
              border: '1px solid #2a2a2a',
              background: 'transparent',
              color: refreshingAll ? '#666' : '#aaa',
              cursor: refreshingAll ? 'wait' : 'pointer',
              fontSize: '0.75rem',
            }}
          >
            {refreshingAll
              ? `↻ Refreshing ${refreshProgress.current}/${refreshProgress.total}…`
              : `↻ Refresh all metrics`}
          </button>
        )}
      </div>
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search by URL or @handle"
        style={{
          width: '100%',
          boxSizing: 'border-box',
          padding: '0.5rem 0.75rem',
          marginBottom: '0.75rem',
          borderRadius: '8px',
          border: '1px solid #2a2a2a',
          background: '#141414',
          color: '#f0f0f0',
          fontSize: '0.85rem',
          outline: 'none',
        }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {filteredJobs.length === 0 && (
          <div style={{ fontSize: '0.8rem', color: '#666', padding: '0.5rem 0' }}>
            No jobs match "{query}"
          </div>
        )}
        {filteredJobs.map(job => (
          <div
            key={job.job_id}
            style={{ position: 'relative' }}
            onMouseEnter={e => e.currentTarget.querySelector('.delete-btn').style.opacity = '1'}
            onMouseLeave={e => e.currentTarget.querySelector('.delete-btn').style.opacity = '0'}
          >
            <button
              onClick={() => onSelect(job)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.6rem 0.75rem',
                paddingRight: '2.5rem',
                borderRadius: '8px',
                border: '1px solid #2a2a2a',
                background: '#141414',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#fe2c55' }}
              onMouseLeave={e => e.currentTarget.style.borderColor = '#2a2a2a'}
            >
              {job.frames?.length > 0 ? (
                <img
                  src={`${API}/jobs/${job.job_id}/thumbnail`}
                  alt="preview"
                  style={{ width: '40px', height: '56px', objectFit: 'cover', borderRadius: '4px', flexShrink: 0 }}
                  onError={e => { e.currentTarget.style.display = 'none'; e.currentTarget.nextSibling.style.display = 'block' }}
                />
              ) : null}
              <div style={{ width: '40px', height: '56px', borderRadius: '4px', background: '#2a2a2a', flexShrink: 0, display: job.frames?.length > 0 ? 'none' : 'block' }} />
              <div style={{ overflow: 'hidden' }}>
                <div style={{
                  fontSize: '0.8rem', color: '#f0f0f0',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {(job.url || job.job_id).split('?')[0]}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#666', marginTop: '2px' }}>
                  {job.created_at && new Date(job.created_at).toLocaleString()}
                  {job.status !== 'done' && (
                    <span style={{ color: '#f0a500', marginLeft: job.created_at ? '0.5rem' : 0 }}>
                      · {job.status}
                    </span>
                  )}
                </div>
              </div>
            </button>

            <button
              className="delete-btn"
              onClick={e => handleDelete(e, job.job_id)}
              title="Delete"
              style={{
                position: 'absolute', right: '0.6rem', top: '50%',
                transform: 'translateY(-50%)',
                background: 'none', border: 'none',
                color: '#666', cursor: 'pointer',
                fontSize: '1rem', lineHeight: 1,
                opacity: 0, transition: 'opacity 0.15s, color 0.15s',
                padding: '0.25rem',
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#f44336'}
              onMouseLeave={e => e.currentTarget.style.color = '#666'}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
