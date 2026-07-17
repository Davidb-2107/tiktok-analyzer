import { useEffect, useState } from 'react'

// Duotone TikTok : cyan = sourcing, pink = production / warnings.
const CYAN = '#25F4EE'
const PINK = '#FE2C55'
const MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

export function obsidianHref(vaultRelPath) {
  return `obsidian://open?vault=Wiki_Claude&file=${encodeURIComponent(vaultRelPath)}`
}

const fmtNum = (n) => (n == null ? '—' : Number(n).toLocaleString('fr-FR'))
const dash = (v) => (v == null || v === '' ? '—' : v)
const fmtDate = (d) => (d == null || d === '' ? '—' : String(d).slice(0, 10))

const microLabel = {
  fontFamily: MONO,
  fontSize: '0.7rem',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: '#888',
}

const card = {
  background: '#181818',
  border: '1px solid #2a2a2a',
  borderRadius: '6px',
  padding: '1rem',
  cursor: 'pointer',
  textAlign: 'left',
  color: '#ddd',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.75rem',
}

const pill = (color) => ({
  display: 'inline-block',
  padding: '0.15rem 0.55rem',
  borderRadius: '999px',
  border: `1px solid ${color}44`,
  color,
  fontSize: '0.72rem',
  fontFamily: MONO,
})

const backBtn = {
  padding: '0.4rem 0.85rem',
  borderRadius: '6px',
  border: '1px solid #2a2a2a',
  background: 'transparent',
  color: '#aaa',
  cursor: 'pointer',
  fontSize: '0.85rem',
}

const linkStyle = { color: '#8ab4f8', fontSize: '0.8rem', textDecoration: 'none' }

function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
      <span style={microLabel}>{label}</span>
      <span style={{ fontFamily: MONO, fontSize: '0.95rem', color: color || '#ddd' }}>{value}</span>
    </div>
  )
}

function totalViews(niche) {
  const all = [...(niche.sourcing?.videos || []), ...(niche.production?.videos || [])]
    .map(v => v.vues).filter(v => v != null)
  return all.length ? all.reduce((a, b) => a + b, 0).toLocaleString('fr-FR') : '—'
}

function SourcingTab({ api, niche }) {
  const chaines = niche.sourcing?.chaines || []
  const videos = niche.sourcing?.videos || []
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {chaines.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
          <span style={microLabel}>Chaînes</span>
          {chaines.map((c, i) => (
            <span key={i} style={pill('#aaa')}>{typeof c === 'string' ? c : dash(c?.note || c?.channel_url)}</span>
          ))}
        </div>
      )}
      {videos.length === 0 && <div style={{ color: '#888' }}>Aucune vidéo sourcing.</div>}
      {videos.map((v, i) => (
        <div key={i} style={{ display: 'flex', gap: '0.85rem', background: '#181818', border: '1px solid #2a2a2a', borderRadius: '6px', padding: '0.75rem' }}>
          {v.thumb ? (
            <img
              src={`${api}/hub/frame/${encodeURI(v.thumb)}`}
              alt=""
              style={{ width: '72px', height: '128px', objectFit: 'cover', borderRadius: '4px', background: '#111', flexShrink: 0 }}
            />
          ) : (
            <div style={{ width: '72px', height: '128px', borderRadius: '4px', background: '#111', border: '1px dashed #2a2a2a', flexShrink: 0 }} />
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{dash(v.titre)}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', fontSize: '0.8rem', color: '#888' }}>
              <span>{dash(v.chaine)}</span>
              <span style={{ fontFamily: MONO, color: CYAN }}>{fmtNum(v.vues)} vues</span>
              {v.used && <span style={pill(PINK)}>used</span>}
            </div>
            {v.note != null && v.note !== '' && (
              <div style={{ fontSize: '0.8rem', color: '#aaa', fontStyle: 'italic' }}>{v.note}</div>
            )}
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              {v.transcript_ref && <a href={obsidianHref(v.transcript_ref)} style={linkStyle}>transcript ↗</a>}
              {v.card_ref && <a href={obsidianHref(v.card_ref)} style={linkStyle}>card ↗</a>}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ProductionTab({ niche }) {
  const videos = niche.production?.videos || []
  if (videos.length === 0) return <div style={{ color: '#888' }}>Aucun post production.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
      {videos.map((v, i) => (
        <div key={i} style={{ background: '#181818', border: '1px solid #2a2a2a', borderRadius: '6px', padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', alignItems: 'baseline' }}>
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{dash(v.slug)}</span>
            <span style={{ fontFamily: MONO, fontSize: '0.8rem', color: '#888' }}>{fmtDate(v.date)}</span>
            {v.status && <span style={pill(PINK)}>{v.status}</span>}
          </div>
          {v.caption != null && v.caption !== '' && (
            <div style={{ fontSize: '0.82rem', color: '#aaa' }}>{v.caption}</div>
          )}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', alignItems: 'center', fontSize: '0.8rem', color: '#888' }}>
            <span>{dash(v.compte)}</span>
            <span style={{ fontFamily: MONO, color: PINK }}>{fmtNum(v.vues)} vues</span>
            {v.tiktok_url && (
              <a href={v.tiktok_url} target="_blank" rel="noreferrer" style={linkStyle}>TikTok ↗</a>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Hub({ api, onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState('sourcing')

  useEffect(() => {
    fetch(`${api}/hub`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(setData)
      .catch(e => setError(String(e)))
  }, [api])

  if (error) return (
    <div style={{ color: '#f44336' }}>
      Hub indisponible : {error}{' '}
      <button onClick={onBack} style={{ ...backBtn, marginLeft: '0.5rem' }}>Retour</button>
    </div>
  )
  if (!data) return <div style={{ color: '#888' }}>Chargement…</div>

  const niche = data.niches.find(n => n.key === selected)

  // Écran 2 — détail
  if (niche) {
    const tabBtn = (id, label, color) => (
      <button
        onClick={() => setTab(id)}
        style={{
          padding: '0.5rem 0.9rem',
          background: 'transparent',
          border: 'none',
          borderBottom: tab === id ? `2px solid ${color}` : '2px solid transparent',
          color: tab === id ? '#ddd' : '#888',
          cursor: 'pointer',
          fontSize: '0.9rem',
          fontFamily: MONO,
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </button>
    )
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button onClick={() => setSelected(null)} style={backBtn}>← Niches</button>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>{dash(niche.nom)}</h2>
          <span style={{ ...microLabel, marginLeft: '0.25rem' }}>{niche.projet_dir}</span>
        </div>
        {niche.warnings?.length > 0 && (
          <div style={{ border: `1px solid ${PINK}44`, borderRadius: '6px', padding: '0.6rem 0.85rem', color: PINK, fontSize: '0.82rem', fontFamily: MONO }}>
            {niche.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
          </div>
        )}
        <div style={{ display: 'flex', borderBottom: '1px solid #2a2a2a' }}>
          {tabBtn('sourcing', `Sourcing · ${niche.sourcing?.videos?.length ?? 0}`, CYAN)}
          {tabBtn('production', `Production · ${niche.production?.videos?.length ?? 0}`, PINK)}
        </div>
        {tab === 'sourcing'
          ? <SourcingTab api={api} niche={niche} />
          : <ProductionTab niche={niche} />}
      </div>
    )
  }

  // Écran 1 — grille
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <button onClick={onBack} style={backBtn}>← Back</button>
        <h2 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>Hub niches</h2>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem' }}>
        {data.niches.map(n => (
          <button key={n.key} onClick={() => { setSelected(n.key); setTab('sourcing') }} style={{ ...card, font: 'inherit' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontWeight: 700, fontSize: '1rem' }}>{dash(n.nom)}</span>
              {n.warnings?.length > 0 && <span style={pill(PINK)}>⚠ {n.warnings.length}</span>}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
              <Stat label="Chaînes" value={n.sourcing?.chaines?.length ?? 0} />
              <Stat label="Sourcing" value={n.sourcing?.videos?.length ?? 0} color={CYAN} />
              <Stat label="Production" value={n.production?.videos?.length ?? 0} color={PINK} />
              <Stat label="Total vues" value={totalViews(n)} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
              <span style={microLabel}>Dernier post</span>
              <span style={{ fontFamily: MONO, fontSize: '0.85rem', color: '#aaa' }}>
                {fmtDate(n.production?.videos?.[0]?.date)}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
