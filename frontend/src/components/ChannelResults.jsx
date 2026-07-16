import { useEffect, useRef, useState } from 'react'
import StatusIndicator from './StatusIndicator.jsx'
import FrameGallery from './FrameGallery.jsx'
import Transcript from './Transcript.jsx'
import Toast from './Toast.jsx'

const viewsFmt = new Intl.NumberFormat()

function frameUrls(api, video) {
  if (!video.frames?.length) return []
  const isLocal = video.status === 'frames_ready' || video.status === 'transcribing'
  return isLocal
    ? video.frames.map(name => `${api}/frames/${video.job_id}/local/${name}`)
    : video.frames
}

function SaveToSourcing({ api, video, channel, showToast }) {
  const [niche, setNiche] = useState(() => localStorage.getItem('sourcing.lastNiche') || '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(null) // null | 'saved' | 'exists'

  const save = async () => {
    const n = niche.trim()
    if (!n || saving) return
    setSaving(true)
    try {
      const res = await fetch(`${api}/jobs/${video.job_id}/save-transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: n, channel, title: video.title, views: video.views }),
      })
      const data = await res.json()
      if (!res.ok) {
        showToast(`Save failed: ${data.detail || `HTTP ${res.status}`}`)
        return
      }
      localStorage.setItem('sourcing.lastNiche', n)
      if (data.saved) {
        setSaved('saved')
        showToast('Saved to Sourcing registry')
      } else {
        setSaved('exists')
        showToast('Already saved, skipped')
      }
    } catch (err) {
      showToast(`Save failed: ${err.message || err}`)
    } finally {
      setSaving(false)
    }
  }

  const disabled = video.status !== 'done' || !video.transcript || saving

  return (
    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
      <input
        type="text"
        value={niche}
        onChange={e => { setNiche(e.target.value); setSaved(null) }}
        placeholder="niche (e.g. neon_psycho)"
        disabled={disabled}
        style={{
          padding: '0.4rem 0.7rem',
          borderRadius: '6px',
          border: '1px solid #2a2a2a',
          background: '#111',
          color: '#ddd',
          fontSize: '0.8rem',
          minWidth: '10rem',
        }}
      />
      <button
        onClick={save}
        disabled={disabled}
        style={{
          padding: '0.4rem 0.85rem',
          borderRadius: '6px',
          border: '1px solid #2a2a2a',
          background: 'transparent',
          color: disabled ? '#555' : '#aaa',
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontSize: '0.8rem',
        }}
      >
        {saved === 'saved' ? '✓ Saved' : saved === 'exists' ? '✓ Already saved' : 'Save to Sourcing'}
      </button>
    </div>
  )
}

export default function ChannelResults({ api, url, topN, fps, project, onBack }) {
  const [channel, setChannel] = useState(null)
  const [videos, setVideos] = useState([]) // [{url,title,views,duration,job_id?,status,rejectedReason?,...status fields}]
  const [error, setError] = useState(null)
  const [toastMessage, setToastMessage] = useState(null)
  const pollRef = useRef(null)
  const showToast = (msg) => setToastMessage(msg)

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      setError(null)
      setVideos([])
      try {
        const topRes = await fetch(`${api}/channel/top?url=${encodeURIComponent(url)}&n=${topN}`)
        const topData = await topRes.json()
        if (!topRes.ok) throw new Error(topData.detail || `HTTP ${topRes.status}`)
        if (cancelled) return
        setChannel(topData.channel)

        const urls = topData.top.map(v => v.url)
        const batchRes = await fetch(`${api}/analyze/batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ urls, fps, project }),
        })
        const batchData = await batchRes.json()
        if (!batchRes.ok) throw new Error(batchData.detail || `HTTP ${batchRes.status}`)
        if (cancelled) return

        const jobByUrl = new Map(batchData.jobs.map(j => [j.url, j.job_id]))
        const rejectedByUrl = new Map((batchData.rejected || []).map(r => [r.url, r.reason]))
        const initial = topData.top
          .slice()
          .sort((a, b) => (b.views || 0) - (a.views || 0))
          .map(v => ({
            ...v,
            job_id: jobByUrl.get(v.url) || null,
            status: jobByUrl.has(v.url) ? 'pending' : 'rejected',
            rejectedReason: rejectedByUrl.get(v.url) || null,
            frames: [],
            transcript: null,
          }))
        setVideos(initial)
      } catch (err) {
        if (!cancelled) setError(err.message || String(err))
      }
    }

    run()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, url, topN, fps, project])

  useEffect(() => {
    const jobIds = videos.filter(v => v.job_id).map(v => v.job_id)
    if (!jobIds.length) return
    const allTerminal = videos.every(v => !v.job_id || ['done', 'error'].includes(v.status))
    if (allTerminal) return

    pollRef.current = setInterval(async () => {
      try {
        const results = await Promise.all(
          jobIds.map(id => fetch(`${api}/status/${id}`).then(r => r.json()))
        )
        setVideos(vs => vs.map(v => {
          if (!v.job_id) return v
          const data = results.find(r => r.job_id === v.job_id)
          return data ? { ...v, ...data } : v
        }))
      } catch {
        // A transient network hiccup — next tick retries. Matches the
        // single-job poller's tolerant behavior, just without the 5-strikes
        // giveup (N jobs make a per-job failure budget more fiddly than it's
        // worth for a local-only feature).
      }
    }, 500)

    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [api, videos])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <button
          onClick={onBack}
          style={{
            padding: '0.4rem 0.85rem',
            borderRadius: '6px',
            border: '1px solid #2a2a2a',
            background: 'transparent',
            color: '#aaa',
            cursor: 'pointer',
            fontSize: '0.85rem',
          }}
        >
          ← Back
        </button>
        {channel && (
          <span style={{ color: '#888', fontSize: '0.85rem' }}>
            {channel} — top {topN} by views
          </span>
        )}
      </div>

      {error && <div style={{ color: '#f44336' }}>{error}</div>}

      {videos.map((video, i) => (
        <div
          key={video.url}
          style={{
            display: 'flex', flexDirection: 'column', gap: '0.75rem',
            padding: '1rem', borderRadius: '10px', border: '1px solid #2a2a2a',
          }}
        >
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, color: '#fe2c55' }}>#{i + 1}</span>
            <span style={{ color: '#f0f0f0' }}>{viewsFmt.format(video.views || 0)} views</span>
            <span style={{ color: '#888', fontSize: '0.85rem' }}>{video.title}</span>
            <a
              href={video.url}
              target="_blank"
              rel="noreferrer"
              style={{ color: '#888', fontSize: '0.8rem', marginLeft: 'auto' }}
            >
              ↗ Source
            </a>
          </div>

          {video.status === 'rejected' ? (
            <div style={{ color: '#f44336', fontSize: '0.85rem' }}>
              Rejected: {video.rejectedReason || 'unknown reason'}
            </div>
          ) : (
            <StatusIndicator status={video} />
          )}

          {frameUrls(api, video).length > 0 && <FrameGallery frames={frameUrls(api, video)} />}
          {video.transcript && <Transcript text={video.transcript} />}

          {video.status !== 'rejected' && (
            <SaveToSourcing api={api} video={video} channel={channel} showToast={showToast} />
          )}
        </div>
      ))}

      <Toast message={toastMessage} onDismiss={() => setToastMessage(null)} />
    </div>
  )
}
