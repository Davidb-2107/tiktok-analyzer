import { useState, useEffect, useRef, Component } from 'react'
import UrlInput from './components/UrlInput.jsx'
import StatusIndicator from './components/StatusIndicator.jsx'
import FrameGallery from './components/FrameGallery.jsx'
import SceneTimeline from './components/SceneTimeline.jsx'
import JobHistory from './components/JobHistory.jsx'
import Transcript from './components/Transcript.jsx'
import Toast from './components/Toast.jsx'
import ChannelResults from './components/ChannelResults.jsx'
import Hub from './Hub.jsx'

// '' in prod (same origin via Cloudflare Tunnel) — Vite dev sets
// VITE_API_URL=http://localhost:8000 in docker-compose.yml.
const API = import.meta.env.VITE_API_URL || ''
const R2_ACCOUNT_ID = import.meta.env.VITE_R2_ACCOUNT_ID
const R2_BUCKET = import.meta.env.VITE_R2_BUCKET

const r2FolderUrl = (jobId) =>
  R2_ACCOUNT_ID && R2_BUCKET && jobId
    ? `https://dash.cloudflare.com/${R2_ACCOUNT_ID}/r2/default/buckets/${R2_BUCKET}?prefix=${jobId}/`
    : null

function UserTagsEditor({ jobId, tags, onChange, showToast }) {
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)

  const persist = async (next) => {
    setSaving(true)
    try {
      const res = await fetch(`${API}/jobs/${jobId}/tags`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: next }),
      })
      if (res.ok) {
        const data = await res.json()
        onChange(data.user_tags || [])
        showToast && showToast('Tags saved')
      } else {
        showToast && showToast(`Save failed: HTTP ${res.status}`)
      }
    } catch (err) {
      showToast && showToast(`Save failed: ${err.message || err}`)
    } finally {
      setSaving(false)
    }
  }

  const addTag = () => {
    const t = draft.trim().toLowerCase()
    if (!t) return
    if (tags.includes(t)) { setDraft(''); return }
    setDraft('')
    persist([...tags, t])
  }

  const removeTag = (t) => persist(tags.filter(x => x !== t))

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
      <span style={{ color: '#888', fontSize: '0.8rem', marginRight: '0.25rem' }}>User tags:</span>
      {tags.map(t => (
        <span
          key={t}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.25rem 0.6rem',
            borderRadius: '999px',
            border: '1px solid #2a2a2a',
            background: '#181818',
            color: '#ddd',
            fontSize: '0.8rem',
          }}
        >
          {t}
          <button
            onClick={() => removeTag(t)}
            disabled={saving}
            title="Remove tag"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#888',
              cursor: saving ? 'wait' : 'pointer',
              fontSize: '0.85rem',
              padding: 0,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </span>
      ))}
      <input
        type="text"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag() } }}
        placeholder="add tag + Enter"
        disabled={saving}
        style={{
          padding: '0.25rem 0.6rem',
          borderRadius: '999px',
          border: '1px solid #2a2a2a',
          background: '#111',
          color: '#ddd',
          fontSize: '0.8rem',
          minWidth: '8rem',
          outline: 'none',
        }}
      />
    </div>
  )
}

class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (this.state.error) return (
      <div style={{ padding: '1rem', color: '#f44336' }}>
        Something went wrong: {this.state.error.message}
        <button onClick={() => this.setState({ error: null })} style={{ marginLeft: '1rem', cursor: 'pointer' }}>Retry</button>
      </div>
    )
    return this.props.children
  }
}

export default function App() {
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [frames, setFrames] = useState([])
  const [scenes, setScenes] = useState([])
  const [history, setHistory] = useState([])
  const [toastMessage, setToastMessage] = useState(null)
  const [channelParams, setChannelParams] = useState(null)
  const [showHub, setShowHub] = useState(false)
  const pollRef = useRef(null)

  const showToast = (msg) => setToastMessage(msg)

  const loadHistory = async () => {
    const res = await fetch(`${API}/jobs`)
    setHistory(await res.json())
  }

  useEffect(() => { loadHistory() }, [])

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const applyJobData = (data) => {
    setJobStatus(data)
    const localSceneStatus = ['frames_ready', 'transcribing'].includes(data.status)
    const nextScenes = Array.isArray(data.scenes) ? data.scenes.map((scene) => {
      if (!scene || typeof scene !== 'object') return null
      const keyframe = scene.keyframe ?? scene.keyframe_url ?? null
      const localKeyframeValue = scene.local_keyframe || scene.localKeyframe || (
        typeof keyframe === 'string' && !/^https?:\/\//i.test(keyframe) ? keyframe : null
      )
      const localKeyframe = typeof localKeyframeValue === 'string'
        ? (/^https?:\/\//i.test(localKeyframeValue)
          ? localKeyframeValue
          : `${API}/frames/${data.job_id}/local/${encodeURIComponent(localKeyframeValue)}`)
        : null
      return {
        ...scene,
        keyframe: localSceneStatus && localKeyframe ? localKeyframe : keyframe,
        keyframeFallback: localKeyframe,
      }
    }).filter(Boolean) : []
    setScenes(nextScenes)
    if (data.frames?.length) {
      const isLocal = data.status === 'frames_ready' || data.status === 'transcribing'
      const urls = isLocal
        ? data.frames.map(name => `${API}/frames/${data.job_id}/local/${name}`)
        : data.frames
      setFrames(urls)
    } else {
      // Frameless job (errored early, still pending): clear instead of
      // keeping the previously selected job's gallery on screen.
      setFrames([])
    }
  }

  const handleAnalyze = async (url, fps, project) => {
    stopPolling()
    setFrames([])
    setScenes([])
    setJobStatus(null)
    setJobId(null)

    const res = await fetch(`${API}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, fps, project }),
    })
    const data = await res.json()
    if (!res.ok) {
      setJobStatus({ status: 'error', error: data.detail || 'Request failed' })
      return
    }
    setJobStatus({ status: 'pending', project: data.project ?? project ?? null })
    setJobId(data.job_id)
  }

  const handleAnalyzeChannel = (url, topN, fps, project) => {
    stopPolling()
    setFrames([])
    setScenes([])
    setJobStatus(null)
    setJobId(null)
    setChannelParams({ url, topN, fps, project })
  }

  const handleAnalyzeBatch = async (urls, fps, project) => {
    try {
      const res = await fetch(`${API}/analyze/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls, fps, project }),
      })
      const data = await res.json()
      if (!res.ok) {
        showToast(`Batch failed: ${data.detail || `HTTP ${res.status}`}`)
        return
      }
      const rejected = data.rejected?.length
        ? ` — ${data.rejected.length} rejected (${data.rejected.map(r => r.reason)[0]})`
        : ''
      showToast(`${data.jobs.length} jobs queued${rejected}`)
      loadHistory()
    } catch (err) {
      showToast(`Batch failed: ${err.message || err}`)
    }
  }

  // Bumped on every history select so the polling effect re-runs even when
  // the same job_id is clicked again (setJobId with an identical value would
  // otherwise bail out and leave polling stopped forever).
  const [pollEpoch, setPollEpoch] = useState(0)
  const selectedRef = useRef(null)

  const handleSelectHistory = async (job) => {
    stopPolling()
    selectedRef.current = job.job_id
    setJobId(job.job_id)
    setPollEpoch(e => e + 1)
    // Re-fetch instead of reusing the cached history entry: its presigned R2
    // URLs go stale after 1h (PRESIGN_TTL) if the tab stays open.
    try {
      const res = await fetch(`${API}/status/${job.job_id}`)
      const data = res.ok ? await res.json() : job
      // Discard if the user selected another job while this fetch was in
      // flight — a slow response must not overwrite the newer selection.
      if (selectedRef.current === job.job_id) applyJobData(data)
    } catch {
      if (selectedRef.current === job.job_id) applyJobData(job)
    }
  }

  const handleBack = () => {
    stopPolling()
    setJobId(null)
    setJobStatus(null)
    setFrames([])
    setScenes([])
    setChannelParams(null)
  }

  const [refreshing, setRefreshing] = useState(false)
  const handleRefreshMetrics = async () => {
    if (!jobId || refreshing) return
    setRefreshing(true)
    try {
      const res = await fetch(`${API}/jobs/${jobId}/refresh-metrics`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        applyJobData(data)
        loadHistory()
        showToast('Metrics refreshed')
      } else {
        showToast(`Refresh failed: HTTP ${res.status}`)
      }
    } catch (err) {
      showToast(`Refresh failed: ${err.message || err}`)
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    if (!jobId) return

    let failures = 0
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/status/${jobId}`)
        const data = await res.json()
        failures = 0
        applyJobData(data)

        const terminal = ['done', 'error']
        if (terminal.includes(data.status)) {
          stopPolling()
          if (data.status === 'done') loadHistory()
        }
      } catch {
        failures++
        if (failures >= 5) {
          stopPolling()
          setJobStatus(s => ({ ...s, status: 'error', error: 'Lost connection to server' }))
        }
      }
    }, 500)

    return stopPolling
  }, [jobId, pollEpoch])

  const isProcessing = jobStatus && !['done', 'error', 'frames_ready'].includes(jobStatus.status)

  if (showHub) return (
    <ErrorBoundary>
      <Hub api={API} onBack={() => setShowHub(false)} />
    </ErrorBoundary>
  )

  return (
    <ErrorBoundary>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>TikTok Analyzer</h1>
        <button
          onClick={() => setShowHub(true)}
          style={{
            padding: '0.4rem 0.85rem',
            borderRadius: '6px',
            border: '1px solid #2a2a2a',
            background: 'transparent',
            color: '#aaa',
            cursor: 'pointer',
            fontSize: '0.85rem',
            marginLeft: 'auto',
          }}
        >
          Hub niches
        </button>
      </header>
      {channelParams ? (
        <ChannelResults
          api={API}
          url={channelParams.url}
          topN={channelParams.topN}
          fps={channelParams.fps}
          project={channelParams.project}
          onBack={handleBack}
        />
      ) : jobStatus ? (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            onClick={handleBack}
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
          {r2FolderUrl(jobId) && (
            <a
              href={r2FolderUrl(jobId)}
              target="_blank"
              rel="noreferrer"
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: '6px',
                border: '1px solid #2a2a2a',
                background: 'transparent',
                color: '#aaa',
                fontSize: '0.85rem',
                textDecoration: 'none',
              }}
            >
              R2 folder ↗
            </a>
          )}
          {jobStatus.status === 'done' && jobStatus.frames?.length > 0 && (
            <a
              href={`${API}/jobs/${jobId}/frames.zip`}
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: '6px',
                border: '1px solid #2a2a2a',
                background: 'transparent',
                color: '#aaa',
                fontSize: '0.85rem',
                textDecoration: 'none',
              }}
            >
              ⬇ Frames (.zip)
            </a>
          )}
          {jobStatus.status === 'done' && (
            <a
              href={`${API}/jobs/${jobId}/captions.srt`}
              title="Download word-timed SRT captions (404 for older jobs without segments)"
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: '6px',
                border: '1px solid #2a2a2a',
                background: 'transparent',
                color: '#aaa',
                fontSize: '0.85rem',
                textDecoration: 'none',
              }}
            >
              ⬇ Captions (.srt)
            </a>
          )}
          {jobStatus.status === 'done' && (
            <a
              href={`${API}/jobs/${jobId}/audio.mp3`}
              title="Download extracted MP3 audio (404 for older jobs run before audio retention)"
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: '6px',
                border: '1px solid #2a2a2a',
                background: 'transparent',
                color: '#aaa',
                fontSize: '0.85rem',
                textDecoration: 'none',
              }}
            >
              ⬇ Audio (.mp3)
            </a>
          )}
          {jobStatus.url && (
            <a
              href={jobStatus.url}
              target="_blank"
              rel="noreferrer"
              title="Open the original TikTok/YouTube/Instagram URL in a new tab"
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: '6px',
                border: '1px solid #2a2a2a',
                background: 'transparent',
                color: '#aaa',
                fontSize: '0.85rem',
                textDecoration: 'none',
              }}
            >
              ↗ Source
            </a>
          )}
          {jobStatus.status === 'done' && jobStatus.url && (
            <button
              onClick={handleRefreshMetrics}
              disabled={refreshing}
              title="Re-poll yt-dlp for current views/likes/comments and rewrite script.txt"
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: '6px',
                border: '1px solid #2a2a2a',
                background: 'transparent',
                color: refreshing ? '#666' : '#aaa',
                cursor: refreshing ? 'wait' : 'pointer',
                fontSize: '0.85rem',
              }}
            >
              {refreshing ? '↻ Refreshing…' : '↻ Refresh metrics'}
            </button>
          )}
          {jobStatus.project && (
            <span
              title="Project this job is routed to"
              style={{
                padding: '0.4rem 0.7rem',
                borderRadius: '6px',
                border: '1px solid #2a2a2a',
                background: 'transparent',
                color: '#888',
                fontSize: '0.8rem',
                marginLeft: 'auto',
              }}
            >
              project: {jobStatus.project}
            </span>
          )}
        </div>
      ) : (
        <UrlInput
          onSubmit={handleAnalyze}
          onSubmitBatch={handleAnalyzeBatch}
          onSubmitChannel={handleAnalyzeChannel}
          disabled={isProcessing}
        />
      )}
      {!channelParams && jobStatus && <StatusIndicator status={jobStatus} />}
      {!channelParams && jobId && jobStatus && (
        <UserTagsEditor
          jobId={jobId}
          tags={jobStatus.user_tags || []}
          onChange={(next) => setJobStatus(s => ({ ...s, user_tags: next }))}
          showToast={showToast}
        />
      )}
      {!channelParams && frames.length > 0 && <FrameGallery frames={frames} />}
      {!channelParams && jobStatus?.status === 'done' && scenes.length > 0 && (
        <SceneTimeline scenes={scenes} segments={jobStatus.segments || []} />
      )}
      {!channelParams && jobStatus?.transcript && <Transcript text={jobStatus.transcript} />}
      {!channelParams && jobStatus?.hook_overlay_text && (
        <Transcript title="Hook — on-screen text, first seconds (OCR)" text={jobStatus.hook_overlay_text} />
      )}
      {!channelParams && jobStatus?.overlay_text && (
        <Transcript title="On-screen text (OCR)" text={jobStatus.overlay_text} />
      )}
      <JobHistory
        jobs={history}
        onSelect={handleSelectHistory}
        onDelete={id => {
          setHistory(h => h.filter(j => j.job_id !== id))
          if (jobId === id) {
            setJobId(null)
            setJobStatus(null)
            setFrames([])
          }
        }}
        onRefreshComplete={loadHistory}
        showToast={showToast}
      />
      <Toast message={toastMessage} onDismiss={() => setToastMessage(null)} />
    </div>
    </ErrorBoundary>
  )
}
