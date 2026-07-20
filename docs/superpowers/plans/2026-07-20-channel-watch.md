# Veille de chaînes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Veille automatique des chaînes TikTok/YouTube : cron n8n quotidien → nouvelles vidéos détectées par dédup → digest Telegram, sans intervention de David.

**Architecture:** Une seule modif backend (`GET /channel/top?order=recent` + sémaphore d'énumération), tout le reste vit dans n8n sur le VPS : 2 Data Tables (`channels` registre, `seen_videos` dédup par ID vidéo), workflow Schedule → boucle séquentielle HTTP → diff en Code node → digest Telegram chunké.

**Tech Stack:** FastAPI + yt-dlp 2024.10.7 (backend, inchangé côté deps), pytest hermétique (pattern `test_guards.py`), n8n Data Tables + nodes Schedule/HTTP/Code/Telegram via MCP n8n officiel.

**Spec:** `docs/superpowers/specs/2026-07-20-channel-watch-design.md` — lire avant de commencer.

## Global Constraints

- Repo : `C:\Users\dbele\Documents\ObsidianVault\Wiki_Claude\Projects\TikTok Analyzer` (branche `master`, commits directs OK pour ce repo).
- Prod : VPS Contabo, `docker-compose.prod.yml` (PAS le compose par défaut), **rebuild** pas restart (cf. mémoire deploy_gotchas). URL publique : `https://tiktok-analyzer.hen8n.com`.
- Ne PAS bumper yt-dlp (2024.10.7 validé en live le 2026-07-20 sur l'énumération TikTok).
- `order=views` reste le défaut et son comportement actuel est INCHANGÉ (clamp n≤20, tri par vues, playlistend 200) — le pipe format-study existant en dépend.
- pytest n'est pas dans requirements.txt : dans le conteneur dev, `pip install pytest` d'abord (installation éphémère, voulue).
- Clé de dédup = **ID vidéo extrait de l'URL**, jamais l'URL brute.
- n8n : lecture/écriture via le MCP officiel (`mcp__claude_ai_n8n_MCP__*`) ; le serveur communautaire n8n-mcp est en 401, ne pas l'utiliser.
- Workflow n8n : ne PAS activer le cron avant la fin des tests E2E (Task 6).

---

### Task 1: Backend — `order=recent` sur `/channel/top`

**Files:**
- Modify: `backend/main.py:1098-1138` (endpoint `channel_top`) + 1 ligne module-level
- Test (create): `backend/test_channel_top.py`

**Interfaces:**
- Produces: `GET /channel/top?url=<chaîne>&order=recent&n=50` → `{"channel", "enumerated", "top": [{"url","title","views","duration"}]}` en ordre de listing plateforme (plus récent d'abord, pins inclus). `order=views` (défaut) inchangé. `order` invalide → 422. C'est le contrat que le workflow n8n (Task 5) consomme.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/test_channel_top.py` :

```python
"""Hermetic tests for /channel/top order param.
main.py needs R2 env at import -> stub it (same pattern as test_guards.py).
"""

import asyncio
import os

import pytest

os.environ.setdefault("R2_ENDPOINT", "https://test.invalid")
for k in ("R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
    os.environ.setdefault(k, "test")
pytest.importorskip("faster_whisper")
pytest.importorskip("yt_dlp")

from fastapi import HTTPException  # noqa: E402

import main  # noqa: E402

N_ENTRIES = 60


def _listing_entries():
    """Channel listing order = newest first (descending video ids).
    Views deliberately NOT monotonic so order-preservation is observable."""
    return [
        {
            "url": f"https://www.tiktok.com/@x/video/{N_ENTRIES - i}",
            "title": f"v{N_ENTRIES - i}",
            "view_count": (i * 37) % 1000,
            "duration": 60,
        }
        for i in range(N_ENTRIES)
    ]


class _FakeYDL:
    last_opts = None

    def __init__(self, opts):
        _FakeYDL.last_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        return {"entries": _listing_entries()}


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", _FakeYDL)
    # fresh semaphore per test: asyncio.run() creates a new loop each call
    monkeypatch.setattr(main, "_ENUM_SEMAPHORE", asyncio.Semaphore(2))


def _call(**kw):
    return asyncio.run(main.channel_top(**kw))


def test_default_order_views_sorted_and_capped_at_20(patched):
    out = _call(url="https://www.tiktok.com/@x", n=99)
    views = [v["views"] for v in out["top"]]
    assert len(out["top"]) == 20  # legacy clamp intact
    assert views == sorted(views, reverse=True)
    assert _FakeYDL.last_opts["playlistend"] == 200  # legacy window intact


def test_recent_preserves_listing_order(patched):
    out = _call(url="https://www.tiktok.com/@x", n=5, order="recent")
    urls = [v["url"] for v in out["top"]]
    assert urls == [
        f"https://www.tiktok.com/@x/video/{N_ENTRIES - i}" for i in range(5)
    ]


def test_recent_allows_n_50_and_narrows_playlistend(patched):
    out = _call(url="https://www.tiktok.com/@x", n=99, order="recent")
    assert len(out["top"]) == 50
    assert _FakeYDL.last_opts["playlistend"] == 50


def test_invalid_order_rejected(patched):
    with pytest.raises(HTTPException) as exc:
        _call(url="https://www.tiktok.com/@x", order="sideways")
    assert exc.value.status_code == 422
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
docker compose exec backend pip install -q pytest
docker compose exec backend python -m pytest test_channel_top.py -v
```
Attendu : 4 FAIL/ERROR (`channel_top() got an unexpected keyword argument 'order'` et `module 'main' has no attribute '_ENUM_SEMAPHORE'`).

- [ ] **Step 3: Implémenter**

Dans `backend/main.py`, juste au-dessus de `@app.get("/channel/top")`, ajouter :

```python
# /channel/top is public with no auth: bound concurrent yt-dlp enumerations
# so abusers can't saturate the threadpool nor burn the VPS IP's anti-bot
# budget with TikTok (spec 2026-07-20-channel-watch-design.md §3).
_ENUM_SEMAPHORE = asyncio.Semaphore(2)
```

Remplacer le corps de `channel_top` (lignes 1098-1138) par :

```python
@app.get("/channel/top")
async def channel_top(url: str, n: int = 10, order: str = "views"):
    """Enumerate a channel/profile page (yt-dlp flat playlist).
    order=views (default): top-N by view count — the format-study entry point.
    order=recent: platform listing order (newest first, pins included) — the
    channel-watch entry point (dedup happens downstream in n8n)."""
    _validate_url_domain(url)
    if order not in ("views", "recent"):
        raise HTTPException(status_code=422, detail="order must be 'views' or 'recent'")
    n = max(1, min(n, 50 if order == "recent" else 20))

    def enumerate_channel() -> list[dict]:
        opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            # recent: only the head of the listing is needed (less scraping
            # signal); views: wide window to find a channel's tops.
            "playlistend": n if order == "recent" else 200,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        vids = []
        for e in info.get("entries") or []:
            # Entries without a usable URL would poison the documented
            # pipe into /analyze/batch (urls: list[str] rejects null).
            if not e or not (e.get("url") or e.get("webpage_url")):
                continue
            vids.append(
                {
                    "url": e.get("url") or e.get("webpage_url"),
                    "title": e.get("title"),
                    "views": e.get("view_count") or e.get("play_count") or 0,
                    "duration": e.get("duration"),
                }
            )
        if order == "views":
            vids.sort(key=lambda v: v["views"] or 0, reverse=True)
        return vids

    try:
        async with _ENUM_SEMAPHORE:
            vids = await asyncio.to_thread(enumerate_channel)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Channel enumeration failed: {exc}")
    if not vids:
        raise HTTPException(status_code=404, detail="No videos found (not a channel/profile URL?)")
    return {"channel": url, "enumerated": len(vids), "top": vids[:n]}
```

- [ ] **Step 4: Vérifier que tout passe (nouveaux + anciens)**

```bash
docker compose exec backend python -m pytest test_channel_top.py test_guards.py -v
```
Attendu : 4 nouveaux PASS + tous les tests de test_guards.py PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/test_channel_top.py
git commit -m "feat: /channel/top order=recent + enumeration semaphore (channel watch)"
```

---

### Task 2: Déploiement VPS + vérification live

**Files:** aucun nouveau — déploiement du commit de Task 1.

**Interfaces:**
- Consumes: le commit Task 1 pushé sur master.
- Produces: `https://tiktok-analyzer.hen8n.com/channel/top?...&order=recent` live — pré-requis du workflow Task 5.

- [ ] **Step 1: Push**

```bash
git push
```

- [ ] **Step 2: Déployer via la skill VPS**

Invoquer la skill `VPS` pour ce repo. Contraintes (mémoire deploy_gotchas) : `docker-compose.prod.yml`, et comme main.py est copié dans l'image → **rebuild** du service backend, pas un simple restart.

- [ ] **Step 3: Vérification live des deux modes**

```bash
curl -s "https://tiktok-analyzer.hen8n.com/channel/top?url=https://www.tiktok.com/@the.wisejourney&n=5&order=recent"
curl -s "https://tiktok-analyzer.hen8n.com/channel/top?url=https://www.tiktok.com/@the.wisejourney&n=5"
```
Attendu : `recent` → 5 URLs dont les IDs vidéo (`/video/<id>`) sont ~décroissants (IDs TikTok horodatés ; les épinglés peuvent déroger en tête — normal) ; défaut → trié par vues décroissantes (comportement legacy intact). `order=zzz` → HTTP 422.

- [ ] **Step 4: Rien à committer** (déploiement seulement). Noter dans le rapport de task la sortie des 2 curls.

---

### Task 3: n8n — Data Tables `channels` et `seen_videos`

**Files:** aucun (objets n8n, instance hen8n.com via MCP officiel).

**Interfaces:**
- Produces: Data Table `channels` (colonnes : `url` string, `label` string, `niche` string, `active` boolean, `seeded` boolean) ; Data Table `seen_videos` (colonnes : `video_id` string, `url` string, `channel` string, `title` string, `views` number, `first_seen` string ISO). Noms exacts consommés par le workflow Task 5.

- [ ] **Step 1: Charger les tools MCP**

ToolSearch : `select:mcp__claude_ai_n8n_MCP__create_data_table,mcp__claude_ai_n8n_MCP__search_data_tables,mcp__claude_ai_n8n_MCP__add_data_table_rows`

- [ ] **Step 2: Créer les 2 tables** avec exactement les colonnes ci-dessus (`create_data_table` ×2), puis vérifier via `search_data_tables` qu'elles existent avec les bons schémas.

- [ ] **Step 3: Seed du registre** — insérer 2 lignes de test dans `channels` via `add_data_table_rows` :

```json
[
  {"url": "https://www.tiktok.com/@the.wisejourney", "label": "the.wisejourney", "niche": "psycho", "active": true, "seeded": false},
  {"url": "https://www.tiktok.com/@handle-inexistant-xyz987", "label": "canari-erreur", "niche": "test", "active": true, "seeded": false}
]
```
La 2ᵉ ligne est le canari du test d'erreur (Task 6) — elle sera désactivée après.

- [ ] **Step 4: Rapport** — IDs des tables créées + confirmation des schémas. Rien à committer.

---

### Task 4: Credential Telegram — étape David

**Files:** aucun.

**Interfaces:**
- Produces: credential n8n de type Telegram utilisable par le node Telegram de Task 5, + `chat_id` de David.

- [ ] **Step 1: Demander à David** (BLOQUANT — input humain) :
  1. Créer un bot via @BotFather sur Telegram (`/newbot`) → récupérer le **bot token**.
  2. Envoyer un message quelconque au bot, puis récupérer son **chat_id** (ex. via `https://api.telegram.org/bot<TOKEN>/getUpdates`, champ `message.chat.id`).
  3. Créer la credential dans l'UI n8n (hen8n.com → Credentials → Telegram API, coller le token) — les credentials ne se créent pas via MCP.

- [ ] **Step 2: Vérifier** via `mcp__claude_ai_n8n_MCP__list_credentials` qu'une credential Telegram existe, et noter son id + le chat_id pour Task 5.

---

### Task 5: n8n — workflow « Veille chaînes » (inactif)

**Files:** aucun fichier repo — workflow n8n créé via MCP. Nom exact : `Veille chaînes — TikTok Analyzer`.

**Interfaces:**
- Consumes: endpoint Task 2, tables Task 3 (`channels`, `seen_videos`), credential Telegram + chat_id Task 4.
- Produces: workflow **inactif** prêt pour les runs manuels de Task 6.

- [ ] **Step 1: Suivre le protocole MCP n8n dans l'ordre** (obligatoire, ne pas guessed le SDK) : `get_sdk_reference` → `get_workflow_best_practices` (techniques `scheduling` + `data_persistence`) → `search_nodes` (["schedule trigger","data table","http request","code","if","telegram","split in batches","wait"]) → `get_node_types` avec TOUS les node ids retenus.

- [ ] **Step 2: Construire le workflow** (`create_workflow_from_code`) avec ce graphe :

```
Schedule Trigger (cron 0 8 * * *, tz Europe/Brussels)
→ DataTable GetRows channels (filter active=true)
→ SplitInBatches (batchSize=1)                    ← boucle séquentielle
   ├─ HTTP Request GET https://tiktok-analyzer.hen8n.com/channel/top
   │    query: url={{$json.url}}, order=recent, n=50
   │    options: continueOnFail=true, timeout=120000
   ├─ DataTable GetRows seen_videos (filter channel = label de la chaîne courante)
   ├─ Code "diff-and-mark" (JS ci-dessous, mode run-once-per-item de boucle)
   ├─ DataTable Insert seen_videos (rows nouvelles, batch)
   ├─ DataTable Update channels (set seeded=true WHERE url = chaîne courante)
   ├─ Wait 8 s
   └─ retour SplitInBatches
→ (branche done) Code "build-digest" (JS ci-dessous)
→ IF items.length > 0
→ Telegram sendMessage (credential Task 4, chatId de David, 1 node exécuté par chunk)
```

Code node **diff-and-mark** (logique exacte ; adapter uniquement les accès `$('NodeName')` aux noms réels des nodes) :

```javascript
// Entrée : réponse HTTP de la chaîne courante + lignes seen_videos de cette
// chaîne + ligne channel courante. Sortie : {channel, newRows, digestItems, error}
const chan = $('SplitInBatches').item.json;            // {url,label,niche,active,seeded}
const http = $input.item.json;

// chaîne en erreur (continueOnFail) → item d'erreur pour le digest, rien d'autre
if (http.error || !http.top) {
  return [{ json: { channel: chan.label, error: true, newRows: [], digestItems: [] } }];
}

const idOf = (u) => {
  const m = u.match(/\/video\/(\d+)/) || u.match(/(?:v=|shorts\/)([\w-]{11})/);
  return m ? m[1] : u;                                  // fallback: URL brute
};

const seen = new Set($('Get seen_videos').all().map(r => r.json.video_id));
const now = new Date().toISOString();
const fresh = http.top
  .map(v => ({ ...v, video_id: idOf(v.url) }))
  .filter(v => !seen.has(v.video_id));

const newRows = fresh.map(v => ({
  video_id: v.video_id, url: v.url, channel: chan.label,
  title: v.title || "", views: v.views || 0, first_seen: now,
}));

// seed silencieux : première passe (seeded=false) → on insère tout, zéro digest
// garde-fou re-seed : >10 "nouveautés" d'un coup → ligne d'alerte unique
let digestItems = [];
if (chan.seeded) {
  digestItems = fresh.length > 10
    ? [{ warning: `⚠️ ${chan.label} : ${fresh.length} entrées d'un coup, probable re-seed — non listées` }]
    : fresh.map(v => ({
        title: v.title || "(sans titre)",
        views: v.views ? v.views.toLocaleString("fr-FR") : "?",
        duration: v.duration || "?",
        url: v.url,
      }));
}
return [{ json: { channel: chan.label, error: false, newRows, digestItems } }];
```

Code node **build-digest** (branche done, run once for all items) :

```javascript
const results = $input.all().map(i => i.json);
const errors = results.filter(r => r.error).map(r => `⚠️ ${r.channel} inaccessible`);
const groups = results.filter(r => !r.error && r.digestItems.length > 0);
const total = groups.reduce((s, g) => s + g.digestItems.filter(d => !d.warning).length, 0);

if (total === 0 && errors.length === 0) return [];      // IF suivant → rien envoyé

const lines = [`📡 Veille — ${total} nouveauté${total > 1 ? "s" : ""}`];
for (const g of groups) {
  lines.push(`\n▶ ${g.channel}`);
  for (const d of g.digestItems) {
    lines.push(d.warning ? d.warning : `• ${d.title} — ${d.views} vues, ${d.duration}s\n${d.url}`);
  }
}
lines.push(...errors);

// chunking : Telegram plafonne à 4096 chars/message
const MAX = 3500;
const chunks = [];
let cur = "";
for (const line of lines) {
  const cand = cur ? cur + "\n" + line : line;
  if (cand.length > MAX) { chunks.push(cur); cur = line; } else { cur = cand; }
}
if (cur) chunks.push(cur);
return chunks.map(c => ({ json: { text: c } }));
```

- [ ] **Step 3: Valider** — `validate_workflow` puis `n8n_validate_workflow`/`get_workflow_details` : zéro erreur de config, credential Telegram bien référencée, workflow **non activé**.

- [ ] **Step 4: Rapport** — id du workflow + capture de la structure des nodes. Rien à committer.

---

### Task 6: E2E + activation + doc

**Files:**
- Modify: `API.md` (section `/channel/top` : documenter `order`)

**Interfaces:**
- Consumes: workflow Task 5, tables Task 3.

- [ ] **Step 1: Run manuel n°1 (seed)** — `test_workflow` / exécution manuelle. Attendu : lignes insérées dans `seen_videos` pour the.wisejourney, `channels.seeded=true` pour elle, canari en erreur toléré, **aucun message Telegram** (seed silencieux + garde-fou).

- [ ] **Step 2: Run manuel n°2 (détection)** — supprimer 1 ligne de `seen_videos` (simule une nouveauté), relancer. Attendu : **1 message Telegram** reçu par David avec cette vidéo (titre, vues, durée, lien cliquable) + ligne `⚠️ canari-erreur inaccessible`. Vérifier que la ligne est réinsérée dans `seen_videos`.

- [ ] **Step 3: Nettoyage du canari** — passer `active=false` sur la ligne canari-erreur.

- [ ] **Step 4: Activer le workflow** (`publish_workflow`) — cron quotidien 08:00 armé.

- [ ] **Step 5: Documenter** — dans `API.md`, section `/channel/top` : param `order` (`views` défaut | `recent`), clamp n (20 vs 50), usage veille. Commit :

```bash
git add API.md
git commit -m "docs: /channel/top order param (channel watch)"
git push
```

- [ ] **Step 6: Rapport final** — ids workflow/tables, heure du cron, procédure d'ajout d'une chaîne (1 ligne dans la Data Table `channels`, `seeded=false`, URL YouTube toujours en `/videos` ou `/shorts`).

**Différé assumé (spec §2 « purge >12 mois »)** : à ~150 octets/ligne et ~50 nouveautés/jour, `seen_videos` met des années à approcher le cap 50 MB des Data Tables. Pas de workflow de purge en v1 — à créer (Schedule mensuel → delete `first_seen` < now−12 mois) quand la table dépassera ~100k lignes.
