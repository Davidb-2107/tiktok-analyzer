### Task 4: Frontend — écrans Hub

**Files:**
- Create: `frontend/src/Hub.jsx`
- Modify: `frontend/src/App.jsx` (ajout d'un état `showHub` + bouton d'entrée + rendu conditionnel)

**Interfaces:**
- Consumes: `GET ${API}/hub` (payload Task 3) ; images via `` `${API}/hub/frame/${encodeURI(thumb)}` ``.
- Produces: `<Hub api={API} onBack={fn} />` exporté par défaut de `Hub.jsx`.

- [ ] **Step 1: Invoquer le skill `frontend-design`** (et `dataviz` si graphiques) pour le langage visuel, puis implémenter `Hub.jsx` sur cette base fonctionnelle :

Contrat fonctionnel obligatoire (le style est libre, la structure non) :

```jsx
import { useEffect, useState } from 'react'

export default function Hub({ api, onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null) // key de niche ou null
  const [tab, setTab] = useState('sourcing')     // 'sourcing' | 'production'

  useEffect(() => {
    fetch(`${api}/hub`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(setData)
      .catch(e => setError(String(e)))
  }, [api])

  if (error) return <div>Hub indisponible : {error} <button onClick={onBack}>Retour</button></div>
  if (!data) return <div>Chargement…</div>

  const niche = data.niches.find(n => n.key === selected)

  // Écran 1 — grille : une carte par niche. Par carte : nom, nb chaînes,
  // nb videos sourcing, nb production, date du dernier post (production[0].date),
  // total vues (somme des vues non null, "—" si aucune), badge si warnings.length.
  // Écran 2 (niche != null) — bouton retour grille + 2 onglets :
  //   sourcing : tableau trié tel que reçu (le backend trie) — vignette
  //     (img src `${api}/hub/frame/${encodeURI(v.thumb)}` si thumb), titre,
  //     chaîne, vues ("—" si null), badge used, note, liens obsidian://
  //     (voir helper ci-dessous) pour transcript_ref et card_ref.
  //   production : liste — slug, date, caption, compte, vues ("—"), status,
  //     lien tiktok_url si présent.
  // ... rendu construit avec frontend-design ...
}

// Lien Obsidian : le navigateur tourne sur l'hôte Windows, le protocol
// handler obsidian:// y est enregistré.
export function obsidianHref(vaultRelPath) {
  return `obsidian://open?vault=Wiki_Claude&file=${encodeURIComponent(vaultRelPath)}`
}
```

- [ ] **Step 2: Brancher dans `App.jsx`**

Pattern maison (état + rendu conditionnel, comme `channelParams`) :

```jsx
import Hub from './Hub'
// dans App() :
const [showHub, setShowHub] = useState(false)
// bouton dans le header existant :
<button onClick={() => setShowHub(true)}>Hub niches</button>
// tout en haut du rendu principal :
if (showHub) return <Hub api={API} onBack={() => setShowHub(false)} />
```

- [ ] **Step 3: Vérifier en réel**

Ouvrir `http://localhost:5173`, cliquer « Hub niches ».
Expected : 3 cartes ; clic `neon_psycho` → onglet Sourcing avec 5 vidéos triées par vues, vignettes visibles, liens obsidian:// qui ouvrent Obsidian ; clic `stickman` → onglet Production avec 6 posts datés ; `pc-repair` → chaînes + 7 vidéos library avec vues « — ».

- [ ] **Step 4: Commit**

```bash
git add frontend/src/Hub.jsx frontend/src/App.jsx
git commit -m "feat(hub): écrans Hub (grille de niches + détail sourcing/production)"
```

---

