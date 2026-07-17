# Task 4 — Rapport : écrans Hub (frontend)

## Livré

- `frontend/src/Hub.jsx` (nouveau) — export default `Hub({ api, onBack })` + export `obsidianHref`.
- `frontend/src/App.jsx` — état `showHub`, bouton « Hub niches » dans le header, rendu conditionnel en tête (pattern `channelParams`).

## Choix visuels clés (skill frontend-design appliqué)

- **Shell inchangé** : mêmes tokens que l'app (#111 / #181818 / bordures #2a2a2a / texte #ddd, radius 6px, pills 999px, boutons ghost identiques au « ← Back » existant).
- **Signature = duotone TikTok** : cyan `#25F4EE` code Sourcing, rose `#FE2C55` code Production + warnings. Utilisé uniquement sur les soulignements d'onglets, les compteurs et les badges — tout le reste reste neutre.
- **Micro-labels mono uppercase** (0.7rem, letterspacing 0.08em) comme dispositif structurel ; chiffres/dates en monospace (identité « outil de données »).
- Grille : `repeat(auto-fill, minmax(260px, 1fr))` ; vignettes sourcing 72×128 (ratio 9:16), placeholder pointillé si `thumb` null.
- Null-safety : helpers `dash()`, `fmtNum()`, `fmtDate()` → « — » partout (vues, dates, captions, comptes) ; accès profonds en `?.` + fallbacks `[]`.

## Preuve de vérification (Playwright, msedge headless, 2026-07-17)

- `docker compose logs frontend` : Vite 5.4.21 ready, HMR appliqué, **aucune erreur de transform** ; `GET /src/Hub.jsx` → module compilé servi.
- Grille : **3 cartes** (Neon Psycho, PC Repair, Stickman Psycho) — screenshot `.playwright-cli/page-2026-07-17T12-08-54-430Z.png`. PC Repair : total vues « — » ; Stickman : dernier post 2026-07-14.
- Clic Neon Psycho → onglet Sourcing : **5 vidéos triées par vues** (30.9M → …), **vignettes visibles** (chemins avec espaces OK via `encodeURI`) — screenshot `.playwright-cli/page-2026-07-17T12-07-43-775Z.png`. Liens `obsidian://open?vault=Wiki_Claude&file=…` corrects dans le snapshot accessibilité.
- Onglet Production (Neon Psycho) : 1 post, date/caption/vues null → « — ».
- Stickman → Production : **6 posts datés** (2026-07-14 … 2026-07-08), vues « — ».
- Console navigateur : seule erreur = favicon 404 (préexistante).

## SHA

Voir `git log -1` sur `feat/niche-hub` (commit `feat(hub): écrans Hub…`).

## Doutes

- « Total vues » carte = somme sourcing **+** production (le brief ne précisait pas le périmètre) ; trivial à restreindre si voulu.
- Chaînes sourcing rendues en pills tolérantes (string ou objet `{nom|handle|url}`) — le shape exact des chaînes n'était pas dans le contrat.
- Liens obsidian:// non cliqués en headless (protocol handler hôte) ; hrefs vérifiés textuellement.
