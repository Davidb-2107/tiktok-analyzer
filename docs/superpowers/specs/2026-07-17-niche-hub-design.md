# Niche Hub — Design

Date : 2026-07-17 (v2, corrigé après vérification par 3 agents : données vault réelles,
intégration codebase, critique adversariale)
Statut : en attente de validation utilisateur

## But

Une interface web locale, type SaaS, en **lecture seule**, pour visualiser toutes
les niches TikTok : sourcing (chaînes, vidéos, classement, transcripts, frames)
+ production (vidéos produites, dates, vues TikTok).

Décisions utilisateur :
- **Accès : local uniquement** (`http://localhost`, Docker Desktop). Pas de version VPS.
- **Lecture seule.** Les écritures restent dans les sessions Claude / fichiers vault.
- UI construite avec le skill `frontend-design` (+ `dataviz` pour les éléments graphiques).

## Réalité des données (constat vérifié — contraint tout le design)

- **Aucune niche n'a un sourcing complet.** `pc-repair` a channels.json + library
  (7 meta.json, **sans vues**) mais ni transcripts ni frames. `neon_psycho` a
  transcripts (5, frontmatter avec `views` structuré) + frames + 2 format cards,
  mais ni channels.json ni library. `stickman` n'a **aucun sourcing** — seulement
  de la production.
- **Ids disjoints** : library = ids YouTube ; transcripts = ids TikTok ; frames =
  dossiers-slugs (`viraldtoprw - psychology-…`) reliés au video_id uniquement via
  leur `manifest.json` (champ `url`). Structure réelle des images :
  `frames/<niche>/<slug>/frames/frame_001.jpg`.
- **Format cards** (`formats/*.md`, nommées par chaîne) : frontmatter `videos:`
  liste les URLs TikTok complètes → jointure card↔transcript↔frames possible par
  video_id. Les vues y sont en commentaires (`# 30.9M vues`) — non fiable ; la
  source fiable des vues sourcing est le frontmatter `views` des transcripts.
- **Production** : `published.json` n'existe que pour Stickman. Champs réels :
  `slug, account_name, publer_id, post_id, tiktok_url, caption, scheduled_at,
  status` — **pas de vues, pas de date de publication effective** (seulement
  `scheduled_at`). `outputs/` contient des drafts préfixés `_`.

## Architecture

Greffé sur l'app TikTok Analyzer existante (FastAPI + React). Aucun nouveau service.

- Vault monté **lecture seule** dans le backend, compose dev uniquement :
  `- ../../:/vault:ro` (le compose vit dans `Wiki_Claude/Projects/TikTok Analyzer`)
  + `VAULT_DIR=/vault` dans `environment`. Le mount `/sourcing:rw` existant reste.
- Backend : `VAULT_DIR = Path(os.environ.get("VAULT_DIR", "/vault"))` (pattern
  env maison). `VAULT_DIR` absent (prod VPS) → `GET /hub` répond 404. **Pas de
  logique de masquage côté frontend** : le fetch échoue en prod, point.
- Pas de cache, pas de base : chaque requête rescanne (JSON/md seulement,
  cf. §frames). F5 = données fraîches.

## Backend

Routes ajoutées dans `backend/main.py`, **avant le mount StaticFiles catch-all**
(fin de fichier).

### `GET /hub`

```json
{
  "niches": [
    {
      "key": "neon_psycho",
      "nom": "Neon Psycho",
      "projet_dir": "Projects/TikTok/Neon_Psycho",
      "warnings": [],
      "sourcing": {
        "chaines": [{ "channel_url": "…", "added": "…", "note": "…" }],
        "videos": [
          {
            "source": "transcript",
            "id": "7568334048544820510",
            "titre": "…", "chaine": "@viraldtoprw",
            "vues": 30900000,
            "note": null, "used": false,
            "transcript_ref": "Projects/Sourcing/transcripts/neon_psycho/7568….md",
            "card_ref": "Projects/Sourcing/formats/viraldtoprw.md",
            "thumb": "frames/neon_psycho/<slug>/frames/frame_001.jpg"
          },
          {
            "source": "library",
            "id": "54zYEXmeI7M",
            "titre": "…", "chaine": "…",
            "vues": null,
            "note": "…", "used": false,
            "transcript_ref": null, "card_ref": null, "thumb": null,
            "duree_s": 1822, "vetted": "2026-06-04"
          }
        ]
      },
      "production": {
        "videos": [
          { "slug": "episode-pilote", "date": null, "caption": null,
            "tiktok_url": null, "vues": null, "compte": null, "status": null }
        ]
      }
    }
  ]
}
```

Règles de construction :

1. **Univers des niches = le dict de mapping**, source de vérité unique :
   `neon_psycho → TikTok/Neon_Psycho`, `pc-repair → TikTok/Repost_Amélioré`,
   `stickman → TikTok/Stickman_3d_Psychologie`. Une clé de sourcing hors mapping
   (future niche) apparaît quand même, sans projet. Toujours 3 niches minimum,
   moitiés vides assumées.
2. **`sourcing.videos[]` = union non jointe** de deux types d'entrées :
   - `source: "transcript"` — un fichier `transcripts/<niche>/*.md` ; `vues` =
     frontmatter `views` ; `card_ref` = la format card dont le frontmatter
     `videos:` contient l'id ; `thumb` = première frame du dossier de frames dont
     le `manifest.json` référence cet id (lecture des manifests, pas de walk des
     images).
   - `source: "library"` — un `library/<niche>/*/meta.json` ; `vues` = null
     (n'existe pas) ; `used` = `bool(usage)`.
   Aucune tentative de jointure library↔transcript (ids disjoints par
   construction).
3. **Tri** : vues décroissantes quand présentes, puis date (`captured`/`vetted`)
   décroissante. L'UI affiche « — » quand vues = null.
4. **`production.videos[]`** : les dossiers de `outputs/` **hors préfixe `_`**
   (drafts exclus), enrichis par `published.json` si présent (`date` =
   `scheduled_at`, `compte` = `account_name`, `vues` = champ `views` si présent —
   convention : les sessions Claude pourront l'ajouter à published.json plus
   tard ; aujourd'hui null partout).
5. **Erreurs** : fichier illisible/JSON invalide → entrée dégradée + message dans
   `warnings[]` de la niche. Jamais de 500 pour une donnée sale.

### `GET /hub/frame/{path:path}`

Sert une image sous `Projects/Sourcing/frames/` uniquement. Converter `:path`
obligatoire (chemins multi-segments avec espaces/accents, URL-encodés côté
front). Garde : `Path.resolve()` + `is_relative_to(frames_root)` + extension
image, sinon 404. Pattern `FileResponse` déjà présent dans main.py.

### Transcripts et format cards

Ouverts via liens **`obsidian://open?vault=Wiki_Claude&file=<path urlencodé>`**
(le navigateur tourne sur l'hôte Windows, le protocol handler fonctionne).
Aucun endpoint texte en v1.

## Frontend

Deux écrans React, **navigation par état** (pattern maison de `App.jsx` :
state + rendu conditionnel + bouton retour). Pas de react-router, pas de
Tailwind — on suit les conventions existantes (inline styles, composants
réutilisables : `FrameGallery`, `Toast`, modèle `ChannelResults` pour l'écran
détail). Appels via `${API}` (`VITE_API_URL`), comme l'existant.

1. **Accueil — grille de niches.** Une carte par niche : nom, nb chaînes,
   nb vidéos sourcées, nb produites (hors drafts), date du dernier post
   programmé, total vues (« — » si aucune donnée). Badge warning si
   `warnings[]` non vide.
2. **Détail niche — deux onglets.**
   - *Sourcing* : tableau trié (règle §3), vignette (`thumb` via `/hub/frame`),
     badge utilisé/dispo, chaîne, note, liens obsidian:// transcript/card.
   - *Production* : liste chronologique — slug, date programmée, caption,
     compte, vues, lien TikTok si présent, status.

## Tests

`backend/test_hub.py`, conventions existantes : stub des 4 env R2 en tête
(main les lit à l'import), **pas de TestClient** (httpx absent des deps) —
on teste les helpers directement :
1. Scan (VAULT_DIR pointé sur le vault réel via env ; `skipif` si absent) →
   exactement les 3 niches du mapping au minimum ; `neon_psycho` a ≥1 vidéo
   sourcing avec `vues` non null ; `stickman` a ≥1 vidéo production datée.
2. Helper de résolution de frame : chemin `../` → lève HTTPException 404.

## Hors scope (v1)

Saisie/édition de vues, fetch automatique des vues TikTok (Apify/Publer),
généralisation de `published.json` aux 3 projets (travail de données, pas
d'app), endpoint texte pour transcripts, version VPS, authentification, cache.
