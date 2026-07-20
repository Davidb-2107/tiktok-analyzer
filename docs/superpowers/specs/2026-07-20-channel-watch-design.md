# Veille de chaînes (channel watch) — Design v1

Date : 2026-07-20 · Statut : validé par David, durci après revue 3 agents
(vérif code, critique adversarial, faisabilité n8n) + test live prod.

## Problème

Le pipeline (analyze → extract-format → prod) dépend d'URLs injectées à la main.
Objectif : une veille automatique des chaînes TikTok/YouTube suivies qui fait
remonter les **nouvelles** vidéos, sans compute automatique — David vette.

## Décisions de cadrage

- **Action à la détection** : inbox à vetter (pas d'auto-analyze).
- **Plateformes** : TikTok + YouTube (yt-dlp gère les deux via `/channel/top`).
- **Mécanique** : workflow n8n sur le VPS (hen8n.com) — tourne PC éteint.
- **Sortie** : digest Telegram 1x/jour.

## Validation live (2026-07-20)

`GET /channel/top?url=tiktok.com/@the.wisejourney&n=8` depuis la prod :
32 entrées, URLs complètes cliquables (`…/@handle/video/<id>`), vues et
durées remplies. L'énumération profil TikTok depuis l'IP Contabo avec
yt-dlp 2024.10.7 **fonctionne** — le risque anti-bot/datacenter reste un
risque d'exploitation (voir Erreurs), pas un bloquant de design.
Note : l'énumération peut être limitée à la première page (~30 entrées) sur
certaines chaînes — sans impact pour une veille (les nouveautés sont en tête).

## Architecture

```
Cron n8n (1x/jour, VPS)
  └─ Get rows Data Table "channels" (active=true) → traitement SÉQUENTIEL
       └─ GET tiktok-analyzer.hen8n.com/channel/top?url=...&order=recent&n=50
          (HTTP node en continueOnFail ; Wait 5–10 s entre chaînes)
            └─ dédup BATCH : 1 "get many" seen_videos (filtre channel)
               + diff en Code node — clé = ID VIDÉO extrait de l'URL
                 ├─ déjà vu → skip
                 └─ nouveau → insert batch seen_videos + ajout au digest
  └─ IF digest non vide → message(s) Telegram groupés par chaîne
```

## Composants

### 1. Registre des chaînes — Data Table n8n `channels`
Colonnes : `url`, `label`, `niche`, `active` (bool), `seeded` (bool).
Ajout/retrait = édition dans l'UI n8n, zéro déploiement.
**Convention YouTube** : URL de tab explicite (`/@chan/videos` ou
`/@chan/shorts`, une ligne par tab) — une URL racine ne garantit pas
d'énumérer les Shorts.

### 2. Détection du nouveau — Data Table n8n `seen_videos`
Colonnes : `video_id` (clé de dédup), `url`, `channel`, `title`, `views`,
`first_seen`.
- **Clé = ID vidéo extrait** (TikTok `/video/(\d+)`, YouTube
  `v=|shorts/([\w-]{11})`), pas l'URL brute — les variantes d'URL entre
  versions yt-dlp ne re-déclenchent pas de fausses nouveautés.
- **Seed crash-safe** : `channels.seeded=false` → insert tout, zéro digest,
  puis `seeded=true` en **dernière** opération. Un crash mi-seed ne pollue
  pas le digest suivant.
- **Garde-fou re-seed** : >10 « nouveautés » d'un coup sur une chaîne →
  ligne unique « ⚠️ chaîne X : N entrées, probable re-seed » au lieu de la
  liste.
- Dédup en **batch** (1 read par chaîne + diff en Code node + insert batch),
  pas de lookup par vidéo (~50 requêtes/jour au lieu de 2500).
- Purge des lignes > 12 mois (les Data Tables sont pensées small/medium,
  cap 50 MB global).

### 3. Modif backend (la seule) — `GET /channel/top?order=recent`
`/channel/top` trie par vues et clampe `n` à 20 (`main.py:1104,1129`) : une
nouvelle vidéo à faibles vues n'y apparaîtrait jamais. Modifs :
- Param `order` (`views` défaut inchangé ; `recent` = **ordre de listing de
  la plateforme**, pins inclus — pas un tri par date). Le tri est simplement
  sauté ; l'ordre natif est déjà préservé jusqu'au sort.
- `n` clampé à 50 (au lieu de 20) quand `order=recent`.
- `playlistend = n` en mode recent (au lieu de 200) — moins de requêtes vers
  TikTok, moins de signal scraper.
- `asyncio.Semaphore(2)` dédié autour de `enumerate_channel` — l'endpoint est
  public sans auth ni rate-limit ; borne les threads yt-dlp concurrents.
  L'auth reste hors scope : risque accepté (un tiers peut consommer le budget
  anti-bot de l'IP).

### 4. Digest Telegram
1x/jour : `📡 Veille — N nouveautés`, puis par chaîne : titre, vues, durée,
lien. `views` null/0 en flat → afficher `?`, pas `0` (fréquent côté YouTube).
**Chunking** : blocs ≤ ~3500 chars (limite Telegram 4096). IF empty-check :
aucun message les jours sans nouveauté. Chaque lien se colle tel quel dans
`/analyze-video` ou `/extract-format` (format validé en live).

### 5. Erreurs
Chaîne en échec (rate-limit TikTok, 502) : `continueOnFail` sur le HTTP node,
ligne « ⚠️ chaîne X inaccessible » dans le digest, retry naturel au cron
suivant. Pas de retry logic dédiée en v1. Si les échecs TikTok deviennent
systématiques (anti-bot datacenter) : bump yt-dlp + `yt-dlp[curl-cffi]` dans
requirements (rebuild, cf. deploy_gotchas), puis cookies en dernier recours.

## Pré-requis avant build (état vérifié sur l'instance)

- Data Tables : feature active, **0 table existante** → créer `channels` et
  `seen_videos`.
- **Aucune credential Telegram** → David fournit bot token (BotFather) +
  chat_id.
- Aucun workflow existant réutilisable (0 hit telegram/tiktok) → build from
  scratch via le MCP n8n officiel (le serveur communautaire n8n-mcp est en
  401, non bloquant).

## Tests

- Backend : pytest sur `order=recent` (ordre préservé, clamp 50 vs 20 selon
  mode, `playlistend=n`, défaut `order=views` inchangé) — premier test de cet
  endpoint, mock de `yt_dlp.YoutubeDL.extract_info`.
- n8n : run manuel — 1er run = seed silencieux (0 message, `seeded` passe à
  true), 2e run = digest reçu sur Telegram ; test d'une chaîne en erreur
  (URL bidon) → les autres chaînes passent.

## Hors scope v1 (délibéré)

Auto-analyze, seuils de vues, écriture dans le hub/vault, autres canaux de
notification, auth sur `/channel/top`. À ajouter si le besoin se prouve.
