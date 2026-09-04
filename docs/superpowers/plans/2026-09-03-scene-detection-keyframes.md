# Scene Detection & Representative Keyframes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une détection de changements de plans et une keyframe représentative par scène, sans casser les frames régulières, l’OCR, le hook microscope ni la transcription existante.

**Architecture:** PySceneDetect devient une couche complémentaire du pipeline actuel. `backend/scenes.py` encapsule la détection et la normalisation des timecodes ; `backend/main.py` conserve la responsabilité du traitement vidéo, de l’upload R2 et du contrat API. Les frames périodiques restent la source de l’OCR et les keyframes de scènes sont exposées séparément dans `scenes`.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, PySceneDetect `scenedetect<0.8`, OpenCV backend fourni par PySceneDetect, ffmpeg, pytest, React/Vite.

**Spec:** `API.md`, `CLAUDE.md`, et la documentation officielle PySceneDetect — `https://www.scenedetect.com/docs/latest/api.html`.

## Global Constraints

- `frames` reste inchangé : même extraction FPS/adaptive, même déduplication, même OCR et mêmes URLs R2.
- Ajouter `scenedetect<0.8` dans `backend/requirements.txt`, car l’API PySceneDetect est encore susceptible d’évoluer entre versions majeures.
- `SCENE_DETECTION_ENABLED` vaut `false` au premier déploiement ; il sera passé à `true` après le benchmark de qualité et de latence.
- Utiliser d’abord `ContentDetector(threshold=27.0, min_scene_len=15)` ; ne pas introduire `AdaptiveDetector` sans benchmark comparatif.
- La détection est best-effort : une erreur PySceneDetect, OpenCV ou keyframe ne doit jamais faire passer un job valide en `error`.
- Ne pas découper ni réencoder les vidéos ; cette feature produit des bornes temporelles et des images, pas des clips.
- Les timecodes sont des secondes flottantes arrondies à deux décimales, triées et non chevauchantes.
- Les jobs `transcribe=false` bénéficient aussi des scènes et keyframes, sans audio ni Whisper.
- Une requête `start_s`/`end_s` détecte uniquement la fenêtre demandée et conserve les timecodes absolus du fichier source.
- Limiter à 120 keyframes de scènes par job ; toutes les scènes restent décrites, mais les scènes non sélectionnées portent `keyframe: null`.
- Aucun nouveau statut de job : la détection reste incluse dans l’état existant `extracting`.

## Contrat de données cible

Ajouter au payload `/status/{job_id}` :

```json
{
  "scenes": [
    {
      "index": 0,
      "start": 0.0,
      "end": 2.4,
      "duration": 2.4,
      "keyframe": "https://r2-presigned-url/...jpg"
    }
  ]
}
```

Pendant le traitement, `keyframe` peut être un nom de fichier local ; après `done`, il devient une URL R2 présignée. Si la détection échoue, `scenes` vaut `[]` et le reste du payload reste exploitable.

---

### Task 1: Encapsuler PySceneDetect et définir la sélection des scènes

**Files:**
- Create: `backend/scenes.py`
- Create: `backend/test_scenes.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `scenes.detect_scenes(video_path: Path, start_s: float | None = None, end_s: float | None = None, threshold: float = 27.0, min_scene_len: int = 15) -> list[dict]`
- Produces: `scenes.select_keyframe_indices(scene_count: int, max_keyframes: int = 120) -> set[int]`
- Produces: `scenes.keyframe_time(scene: dict) -> float`
- Scene dict produced by `detect_scenes`: `{"index": int, "start": float, "end": float, "duration": float}`.

- [ ] **Step 1: Écrire les tests unitaires des fonctions pures**

Ajouter à `backend/test_scenes.py` :

```python
import pytest
import scenes


def test_keyframe_time_is_scene_midpoint():
    assert scenes.keyframe_time({"start": 1.0, "end": 5.0}) == pytest.approx(3.0)


def test_keyframe_selection_keeps_all_small_jobs():
    assert scenes.select_keyframe_indices(3, max_keyframes=120) == {0, 1, 2}


def test_keyframe_selection_is_even_when_scene_count_exceeds_cap():
    selected = scenes.select_keyframe_indices(240, max_keyframes=120)
    assert len(selected) == 120
    assert min(selected) == 0
    assert max(selected) == 239


def test_keyframe_time_handles_short_scene():
    assert scenes.keyframe_time({"start": 2.0, "end": 2.1}) == pytest.approx(2.05)
```

- [ ] **Step 2: Exécuter les tests pour confirmer l’échec initial**

Run: `cd backend && python -m pytest test_scenes.py -v`

Expected: FAIL avec `ModuleNotFoundError: No module named 'scenes'`.

- [ ] **Step 3: Ajouter la dépendance versionnée**

Ajouter exactement cette ligne à `backend/requirements.txt` :

```text
scenedetect<0.8
```

- [ ] **Step 4: Implémenter l’adaptateur PySceneDetect**

Dans `backend/scenes.py`, importer l’API publique et appeler `detect` avec `start_in_scene=True` afin qu’une vidéo sans cut produise une scène couvrant toute la plage analysée :

```python
from pathlib import Path


def detect_scenes(
    video_path: Path,
    start_s: float | None = None,
    end_s: float | None = None,
    threshold: float = 27.0,
    min_scene_len: int = 15,
) -> list[dict]:
    from scenedetect import ContentDetector, detect

    raw_scenes = detect(
        str(video_path),
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
        show_progress=False,
        start_time=start_s,
        end_time=end_s,
        start_in_scene=True,
    )
    result = []
    for index, (start, end) in enumerate(raw_scenes):
        start_sec = round(float(start.get_seconds()), 2)
        end_sec = round(float(end.get_seconds()), 2)
        if end_sec > start_sec:
            result.append({
                "index": index,
                "start": start_sec,
                "end": end_sec,
                "duration": round(end_sec - start_sec, 2),
            })
    return result
```

La fonction ne doit pas avaler les exceptions : l’appelant du pipeline les journalisera et appliquera le fallback `[]`. Cela rend l’adaptateur testable et garde la politique de tolérance dans `main.py`.

- [ ] **Step 5: Implémenter la sélection bornée et la keyframe temporelle**

Sélectionner tous les indices si `scene_count <= max_keyframes`; sinon répartir les indices régulièrement avec un premier et un dernier élément garantis. La keyframe est le milieu de la scène, borné par ses deux extrémités.

- [ ] **Step 6: Ajouter les tests d’intégration mockés de l’appel PySceneDetect**

Tester que `detect_scenes` transmet `threshold`, `min_scene_len`, `start_time`, `end_time` et `start_in_scene=True` à une fausse fonction `detect`, puis normalise des objets `FrameTimecode` simulés. Tester aussi que les scènes nulles ou inversées sont supprimées.

- [ ] **Step 7: Vérifier la tâche**

Run: `cd backend && python -m pytest test_scenes.py -v`

Expected: tous les tests de l’adaptateur et des fonctions pures PASS.

- [ ] **Step 8: Committer**

```bash
git add backend/scenes.py backend/test_scenes.py backend/requirements.txt
git commit -m "feat: add scene detection adapter"
```

---

### Task 2: Intégrer les scènes et keyframes dans le pipeline backend

**Files:**
- Modify: `backend/main.py:386-410, 432-450, 467-490, 542-665, 666-703, 705-830, and the job deletion handler`
- Create: `backend/test_scene_pipeline.py`

**Interfaces:**
- Consumes: `scenes.detect_scenes`, `scenes.select_keyframe_indices`, `scenes.keyframe_time`.
- Produces: `JobResponse.scenes: list[dict] | None`, `_scene_frames_dir(job_id) -> Path`, `_extract_scene_keyframes(video_path: Path, job_id: str, scene_list: list[dict], max_keyframes: int) -> list[dict]`, `_upload_scene_keyframes(job_id: str, scene_list: list[dict]) -> list[dict]`.

- [ ] **Step 1: Écrire les tests de contrat avant l’intégration**

Ajouter des tests hermétiques qui vérifient :

```python
def test_job_response_exposes_scenes():
    from main import JobResponse

    response = JobResponse(
        job_id="x",
        status="done",
        scenes=[{"index": 0, "start": 0.0, "end": 1.0, "duration": 1.0, "keyframe": None}],
    )
    assert response.scenes[0]["duration"] == 1.0


def test_scene_detection_failure_returns_empty_without_raising(monkeypatch, tmp_path):
    import main

    def boom(*args, **kwargs):
        raise RuntimeError("unsupported codec")

    monkeypatch.setattr(main.scene_detection, "detect_scenes", boom)
    assert main._detect_scenes_best_effort(tmp_path / "video.mp4") == []
```

Utiliser le même stub R2 déjà présent dans `test_guards.py` pour importer `main.py` sans secrets réels.

- [ ] **Step 2: Ajouter la configuration et le champ API**

Dans `backend/main.py`, ajouter les paramètres d’environnement suivants :

```python
SCENE_DETECTION_ENABLED = os.environ.get("SCENE_DETECTION_ENABLED", "false").lower() in {"1", "true", "yes"}
SCENE_DETECT_THRESHOLD = float(os.environ.get("SCENE_DETECT_THRESHOLD", "27"))
SCENE_MIN_LEN_FRAMES = int(os.environ.get("SCENE_MIN_LEN_FRAMES", "15"))
SCENE_MAX_KEYFRAMES = int(os.environ.get("SCENE_MAX_KEYFRAMES", "120"))
```

Ajouter `scenes: list[dict] | None = None` à `JobResponse`. Les anciens `job.json` sans ce champ doivent continuer à être servis avec `null` ou `[]` sans migration.

- [ ] **Step 3: Ajouter les helpers de détection best-effort et de stockage local**

Importer le nouveau module sous un nom explicite, par exemple `import scenes as scene_detection`, puis ajouter :

```python
def _scene_frames_dir(job_id: str) -> Path:
    return TEMP_DIR / job_id / "scene_frames"


def _detect_scenes_best_effort(
    video_path: Path,
    start_s: float | None = None,
    end_s: float | None = None,
) -> list[dict]:
    if not SCENE_DETECTION_ENABLED:
        return []
    try:
        return scene_detection.detect_scenes(
            video_path,
            start_s=start_s,
            end_s=end_s,
            threshold=SCENE_DETECT_THRESHOLD,
            min_scene_len=SCENE_MIN_LEN_FRAMES,
        )
    except Exception:
        logger.warning("scene detection failed; continuing without scenes", exc_info=True)
        return []
```

- [ ] **Step 4: Implémenter l’extraction d’une image par scène**

Utiliser ffmpeg avec le timestamp médian de chaque scène et écrire des fichiers déterministes `scene_000.jpg`, `scene_001.jpg`, etc. Réutiliser les mêmes options de qualité JPEG et le même retry `hevc_metadata` que `_extract_frames`. Une erreur sur une scène doit seulement produire `keyframe: null` pour cette scène ; elle ne doit pas supprimer les autres scènes.

Ne pas ajouter ces images à `frames` : elles forment un flux distinct pour éviter de changer le nombre de frames envoyé à l’OCR et les attentes du frontend existant.

- [ ] **Step 5: Brancher la détection dans `_run_job`**

Après le téléchargement et avant `video_path.unlink(...)` :

1. conserver l’extraction actuelle des frames principales et du hook ;
2. appeler `_detect_scenes_best_effort(video_path, start_s, end_s)` ;
3. générer les keyframes dans `_scene_frames_dir(job_id)` ;
4. fusionner les noms de fichiers dans chaque élément `scene["keyframe"]` ;
5. persister `scenes` avec le job ;
6. laisser inchangés les branches captions, Whisper, OCR, prosodie et `transcribe=false`.

Les scènes doivent être calculées avant la suppression de la vidéo source. En cas de liste vide, le job suit exactement le chemin existant.

- [ ] **Step 6: Uploader les keyframes de scènes et présigner les URLs**

Ajouter un préfixe R2 distinct : `<job_id>/scenes/scene_000.jpg`. L’upload des keyframes est best-effort et ne doit pas faire échouer l’upload des frames principales. Dans `_resolve_frames`, lorsque `status == "done"`, présigner aussi `scene["keyframe"]` si elle contient une clé R2 ; conserver `null` pour les échecs individuels.

- [ ] **Step 7: Nettoyer les fichiers temporaires sans toucher à l’audio**

Supprimer `scene_frames` avec les répertoires `frames` et `frames_hook` après l’upload. Conserver `audio.mp3` exactement comme aujourd’hui pour les endpoints audio et les analyses downstream.

- [ ] **Step 8: Tester l’intégration**

Ajouter des tests pour :

- un job avec scènes conserve `frames` et ajoute `scenes` ;
- une erreur de détection laisse le job exploitable ;
- une fenêtre `start_s`/`end_s` conserve des timestamps absolus ;
- `transcribe=false` n’extrait toujours pas d’audio mais produit des scènes ;
- la résolution finale présigne les keyframes sans présigner les noms locaux pendant `frames_ready` ;
- le plafond de 120 keyframes est respecté.

- [ ] **Step 9: Vérifier la tâche**

Run: `cd backend && python -m pytest -q`

Expected: tous les tests backend PASS, y compris les tests historiques OCR, voice, guards, hub et channel watch.

- [ ] **Step 10: Committer**

```bash
git add backend/main.py backend/test_scene_pipeline.py
git commit -m "feat: expose scene keyframes in analysis jobs"
```

---

### Task 3: Documenter le contrat et afficher les scènes dans l’interface

**Files:**
- Modify: `API.md`
- Modify: `CLAUDE.md`
- Modify: `frontend/src/App.jsx:134-175 and 496-501`
- Create: `frontend/src/components/SceneTimeline.jsx`
- No modification to `frontend/src/index.css`; follow the existing component-level styling pattern.

**Interfaces:**
- Consumes: `jobStatus.scenes[]` returned by `/status/{job_id}`.
- Produces: a read-only scene timeline with timestamps, duration and representative image; no new frontend API call.

- [ ] **Step 1: Ajouter le contrat API et les paramètres d’exploitation**

Documenter dans `API.md` : le champ `scenes`, la différence entre `frames` et `scenes[].keyframe`, le comportement best-effort, le plafond de 120 images et les variables `SCENE_DETECTION_ENABLED`, `SCENE_DETECT_THRESHOLD`, `SCENE_MIN_LEN_FRAMES` et `SCENE_MAX_KEYFRAMES`.

Documenter dans `CLAUDE.md` que PySceneDetect détecte des changements de plans et ne remplace pas l’échantillonnage régulier utilisé par l’OCR.

- [ ] **Step 2: Écrire le composant UI minimal**

`SceneTimeline` reçoit `scenes` et rend une grille de cartes : `Scene 1`, `0.00s → 2.40s`, durée et image si `keyframe` est une URL. Si `scenes` est vide, ne rien rendre. Les images doivent utiliser `object-fit: cover` et rester compatibles avec l’affichage 9:16 existant.

- [ ] **Step 3: Brancher le composant dans `App.jsx`**

Afficher `SceneTimeline` après `FrameGallery` et avant le transcript, uniquement quand `jobStatus.status === 'done'` et `jobStatus.scenes?.length` est non nul ; à ce stade les `keyframe` sont des URLs R2 présignées. Ne pas modifier la logique de polling, la galerie principale, les téléchargements SRT/MP3 ou l’historique.

- [ ] **Step 4: Vérifier la tâche**

Run: `npm --prefix frontend run build`

Expected: build Vite PASS sans changer le comportement des jobs existants.

- [ ] **Step 5: Committer**

```bash
git add API.md CLAUDE.md frontend/src/App.jsx frontend/src/components/SceneTimeline.jsx frontend/src/index.css
git commit -m "feat: display detected scenes"
```

---

### Task 4: Valider la qualité, le coût et le rollback

**Files:**
- No source files; validation only. Toute correction documentaire identifiée est ajoutée à `API.md` ou `CLAUDE.md` dans une modification séparée et explicite.

- [ ] **Step 1: Construire l’image backend avec la nouvelle dépendance**

Run: `docker compose build backend`

Expected: installation de `scenedetect<0.8` et démarrage de l’application sans erreur d’import.

- [ ] **Step 2: Exécuter un smoke test sur trois profils vidéo**

Tester un clip avec cuts rapides, un clip avec caméra stable et un clip avec texte incrusté fréquent. Pour chaque job, vérifier :

- `status == "done"` ;
- `frames` non vide et OCR toujours présent quand il fonctionnait avant ;
- scènes triées, positives et couvrant la durée analysée ;
- au plus 120 keyframes non nulles ;
- transcript/segments inchangés par rapport à l’exécution sans scène ;
- `scenes == []` en cas d’échec simulé, sans `status == "error"`.

- [ ] **Step 3: Mesurer le coût**

Comparer le temps total et le nombre d’images R2 avant/après sur les mêmes vidéos. Considérer une régression à investiguer si la durée totale augmente de plus de 30 % sur les clips courts ou si la détection produit systématiquement plus de 120 scènes utiles par vidéo. Consigner les mesures dans le compte-rendu de livraison, sans ajouter de fichier runtime au dépôt.

- [ ] **Step 4: Régler uniquement les paramètres nécessaires**

Si les cuts rapides sont manqués, tester `SCENE_DETECT_THRESHOLD` plus bas. Si les mouvements ou textes créent trop de faux cuts, tester un seuil plus haut ou augmenter `SCENE_MIN_LEN_FRAMES`. Conserver les valeurs par défaut dans le code jusqu’à ce qu’un réglage soit confirmé sur plusieurs niches.

- [ ] **Step 5: Vérifier le rollback**

Relancer avec `SCENE_DETECTION_ENABLED=false`. Le payload doit revenir à `scenes: []` tandis que `frames`, OCR, captions, Whisper, audio et les endpoints existants restent fonctionnels.

- [ ] **Step 6: Vérification finale**

Run: `cd backend && python -m pytest -q`

Run: `npm --prefix frontend run build`

Run: `git diff --check`

Expected: tests et build PASS, aucune modification inattendue, et le rollback par variable d’environnement est opérationnel.


## Critères d’acceptation finaux

- Un job standard expose des scènes avec `start`, `end`, `duration` et une keyframe R2 quand l’extraction réussit.
- Les frames régulières, l’OCR, le hook microscope, les captions, Whisper, l’audio et la prosodie restent inchangés.
- Un échec de PySceneDetect ou d’une keyframe ne fait pas échouer le job global.
- Les fenêtres temporelles produisent des timestamps absolus cohérents.
- Le frontend affiche les scènes sans nouvel appel réseau.
- Le pipeline peut être désactivé par `SCENE_DETECTION_ENABLED=false`.
- Les tests backend et le build frontend passent.
