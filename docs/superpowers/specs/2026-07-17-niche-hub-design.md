# Niche Hub — Design

Date : 2026-07-17
Statut : validé (brainstorming session 2026-07-17)

## But

Une interface web locale, type SaaS, en **lecture seule**, pour visualiser toutes
les niches TikTok : sourcing complet (chaînes, vidéos, classement, transcripts,
frames) + production (vidéos produites, dates de publication, vues TikTok).

Décisions utilisateur :
- **Accès : local uniquement** (`http://localhost`, Docker Desktop). Pas de version VPS.
- **Lecture seule.** Les écritures (saisie de vues, ajout de chaînes) restent
  dans les sessions Claude / fichiers vault.
- UI construite avec le skill `frontend-design`.

## Architecture

Greffé sur l'app TikTok Analyzer existante (FastAPI + React, docker-compose dev
avec bind-mounts et live-reload). Aucun nouveau service.

- Le vault Obsidian est monté **en lecture seule** dans le conteneur backend :
  volume `C:\Users\dbele\Documents\ObsidianVault\Wiki_Claude` → `/vault:ro`
  dans `docker-compose.yml` (dev uniquement).
- Garde par variable d'env `VAULT_DIR` (défaut `/vault`). Si le chemin n'existe
  pas (prod VPS), `GET /hub` répond 404 et le frontend masque l'entrée Hub.
- Pas de cache, pas de base de données : chaque requête rescanne le vault
  (données minuscules, scan < 1 s). Un F5 = données fraîches par construction.

## Backend

### `GET /hub`

Scanne le vault et renvoie :

```json
{
  "niches": [
    {
      "key": "neon_psycho",
      "nom": "Neon Psycho",
      "projet_dir": "Projects/TikTok/Neon_Psycho",
      "warnings": ["fichier X illisible"],
      "sourcing": {
        "chaines": [{ "channel_url": "...", "added": "...", "note": "..." }],
        "videos": [
          {
            "id": "...", "titre": "...", "chaine": "...", "vues": 30900000,
            "note": "...", "used": false,
            "transcript_ref": "Projects/Sourcing/transcripts/neon_psycho/<id>.md",
            "card_ref": "Projects/Sourcing/formats/viraldtoprw.md",
            "frames": ["frames/neon_psycho/<dir>/f_0001.jpg"]
          }
        ]
      },
      "production": {
        "videos": [
          {
            "slug": "episode-pilote",
            "date_publi": null,
            "caption": null, "tiktok_url": null, "vues": null,
            "compte": null
          }
        ]
      }
    }
  ]
}
```

Sources lues (toutes sous `VAULT_DIR`) :

| Donnée | Source |
|---|---|
| Chaînes par niche | `Projects/Sourcing/channels.json` |
| Vidéos sourcées (library) | `Projects/Sourcing/library/<niche>/*/meta.json` |
| Transcripts | `Projects/Sourcing/transcripts/<niche>/*.md` |
| Format cards (titre, vues, hook) | `Projects/Sourcing/formats/*.md` (parse léger) |
| Frames | `Projects/Sourcing/frames/<niche>/` |
| Vidéos produites | `Projects/TikTok/<projet>/outputs/*/` |
| Dates publi, vues, comptes | `Projects/TikTok/<projet>/_feedback/published.json` |

Mapping niche ↔ dossier projet : un dict dans le module backend
(`neon_psycho` → `TikTok/Neon_Psycho`, `pc-repair` → `TikTok/Repost_Amélioré`,
`stickman` → `TikTok/Stickman_3d_Psychologie`). Seule config du système.
Une niche présente d'un seul côté (sourcing sans projet, ou l'inverse)
apparaît quand même, avec la moitié vide.

### `GET /hub/frame/{path}`

Sert une image de `Projects/Sourcing/frames/` uniquement. Résolution du chemin
canonique + vérification qu'il reste sous `frames/` (anti path-traversal).
Hors périmètre ou inexistant → 404.

## Frontend

Deux écrans React (skill `frontend-design`, skill `dataviz` pour tout élément
graphique) :

1. **Accueil — grille de niches.** Une carte par niche : nom, nb chaînes
   suivies, nb vidéos sourcées, nb produites, date de dernière publi, total
   vues TikTok. Clic → détail.
2. **Détail niche — deux onglets.**
   - *Sourcing* : tableau classé par vues décroissantes ; vignettes frames,
     badge utilisé/dispo, chaîne, note de vetting, liens transcript et format
     card (ouverts en texte brut ou via lien `obsidian://`).
   - *Production* : timeline des posts — date, caption, compte, vues
     (« — » si non renseignées), lien TikTok si présent.

## Gestion d'erreurs

Fichier manquant, JSON invalide, markdown non parsable → on inclut ce qui est
lisible, on ajoute un message dans `warnings[]` de la niche, l'UI affiche un
badge d'avertissement. **Jamais de 500 pour une donnée sale.** 404 uniquement
si `VAULT_DIR` absent (prod) ou frame inexistante.

## Tests

`backend/test_hub.py` :
1. Scan du vault réel → ≥ 3 niches, champs attendus présents sur chacune.
2. `/hub/frame` avec un chemin traversant (`../`) → 404.

## Hors scope (v1)

Saisie/édition de vues, fetch automatique des vues TikTok (Apify/Publer),
version hébergée VPS, authentification, cache.
