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

function WatchChannelButton({ api, url, showToast }) {
  const [state, setState] = useState('idle') // idle | loading | followed | exists | error
  const [errMsg, setErrMsg] = useState('')

  const watch = async () => {
    if (state === 'loading' || !url) return
    setState('loading')
    try {
      const res = await fetch(`${api}/watch/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const data = await res.json()
      if (res.status === 503) {
        setErrMsg('Veille non configurée')
        setState('error')
        return
      }
      if (!res.ok) {
        setErrMsg(data.detail || `HTTP ${res.status}`)
        setState('error')
        return
      }
      setState(data.created ? 'followed' : 'exists')
    } catch (err) {
      setErrMsg(err.message || String(err))
      setState('error')
    }
  }

  const label = {
    idle: '📡 Suivre cette chaîne',
    loading: 'Envoi…',
    followed: 'Suivie ✓',
    exists: 'Déjà suivie',
    error: errMsg,
  }[state]

  return (
    <button
      onClick={watch}
      disabled={state === 'loading' || state === 'followed' || state === 'exists'}
      style={{
        padding: '0.4rem 0.85rem',
        borderRadius: '6px',
        border: '1px solid #2a2a2a',
        background: 'transparent',
        color: state === 'error' ? '#f44336' : '#aaa',
        cursor: state === 'loading' ? 'wait' : 'pointer',
        fontSize: '0.85rem',
      }}
    >
      {label}
    </button>
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
        {channel && <WatchChannelButton api={api} url={channel} showToast={showToast} />}
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

        </div>
      ))}

      <Toast message={toastMessage} onDismiss={() => setToastMessage(null)} />
    </div>
  )
}
