# Veille de chaînes (channel watch) — Design v1

Date : 2026-07-20 · Statut : validé par David

## Problème

Le pipeline (analyze → extract-format → prod) dépend d'URLs injectées à la main.
Objectif : une veille automatique des chaînes TikTok/YouTube suivies qui fait
remonter les **nouvelles** vidéos, sans compute automatique — David vette.

## Décisions de cadrage

- **Action à la détection** : inbox à vetter (pas d'auto-analyze).
- **Plateformes** : TikTok + YouTube (yt-dlp gère les deux via `/channel/top`).
- **Mécanique** : workflow n8n sur le VPS (hen8n.com) — tourne PC éteint.
- **Sortie** : digest Telegram 1x/jour.

## Architecture

```
Cron n8n (1x/jour, VPS)
  └─ pour chaque chaîne du registre (Data Table n8n "channels", active=true)
       └─ GET tiktok-analyzer.hen8n.com/channel/top?url=...&order=recent&n=50
            └─ dédup contre Data Table "seen_videos" (clé = URL vidéo)
                 ├─ déjà vu → skip
                 └─ nouveau → insert seen_videos + ajout au digest
  └─ si digest non vide → message Telegram groupé par chaîne
```

## Composants

### 1. Registre des chaînes — Data Table n8n `channels`
Colonnes : `url`, `label`, `niche`, `active` (bool).
Ajout/retrait d'une chaîne = édition dans l'UI n8n, zéro déploiement.

### 2. Détection du nouveau — Data Table n8n `seen_videos`
Colonnes : `url` (clé), `channel`, `title`, `views`, `first_seen`.
Pas de date fiable côté TikTok en énumération flat → détection par **ID jamais
vu**. Premier passage sur une chaîne = **seed silencieux** (tout marqué vu,
aucun digest). Passages suivants : ID absent de la table = nouveauté.

### 3. Modif backend (la seule) — `GET /channel/top?order=recent`
`/channel/top` trie par vues et coupe à 20 : une nouvelle vidéo à faibles vues
n'y apparaîtrait jamais. Ajout d'un param `order` (`views` par défaut,
`recent` = garder l'ordre chaîne, plus récent d'abord) et `n` autorisé
jusqu'à 50 dans ce mode. Pas de scheduler, pas de state, pas de webhook
côté backend.

### 4. Digest Telegram
1 message/jour : `📡 Veille — N nouveautés`, puis par chaîne : titre, vues,
durée, lien. Chaque lien se colle tel quel dans `/analyze-video` ou
`/extract-format` — la veille rejoint le pipeline existant sans glue.

### 5. Erreurs
Chaîne en échec (rate-limit TikTok, 502) : skip + ligne
« ⚠️ chaîne X inaccessible » dans le digest, retry naturel au cron suivant.
Pas de retry logic dédiée en v1.

## Tests

- Backend : test pytest sur `order=recent` (ordre préservé, cap n=50,
  défaut inchangé `order=views`).
- n8n : run manuel du workflow — 1er run = seed silencieux (0 message),
  2e run après ajout simulé = digest reçu sur Telegram.

## Hors scope v1 (délibéré)

Auto-analyze, seuils de vues, écriture dans le hub/vault, autres canaux de
notification. À ajouter seulement si le besoin se prouve à l'usage.
