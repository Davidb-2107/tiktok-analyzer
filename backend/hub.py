"""Scan lecture seule du vault Wiki_Claude pour le Niche Hub.

Autonome (aucun import de main) : chaque requête rescanne, pas de cache.
Toute erreur sur un fichier individuel dégrade en warnings[], ne lève jamais
— sauf resolve_frame dont le 404 est le contrat.
"""

import json
from pathlib import Path

from fastapi import HTTPException

# Seule config du système (spec §Backend règle 1) : univers des niches.
NICHE_PROJECTS = {
    "neon_psycho": ("Neon Psycho", "Projects/TikTok/Neon_Psycho"),
    "pc-repair": ("PC Repair", "Projects/TikTok/Repost_Amélioré"),
    "stickman": ("Stickman Psycho", "Projects/TikTok/Stickman_3d_Psychologie"),
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
SOURCING = "Projects/Sourcing"


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _frontmatter(md_path):
    """Frontmatter YAML plat (key: value) d'un .md, best-effort.
    Les listes indentées (ex. videos:) sont ignorées — voulu."""
    fm = {}
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return fm
    if not text.startswith("---"):
        return fm
    for line in text.split("\n---", 1)[0].splitlines()[1:]:
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, v = line.split(":", 1)
            # " #" = commentaire YAML ; un "#hashtag" collé (titres) est gardé
            fm[k.strip()] = v.split(" #", 1)[0].strip().strip('"')
    return fm


def _cards(vault):
    """[(ref_vault, texte_brut)] des format cards — la jointure card↔vidéo
    se fait en cherchant l'id TikTok dans le texte (les URLs du frontmatter
    videos: contiennent l'id)."""
    out = []
    fdir = vault / SOURCING / "formats"
    if fdir.is_dir():
        for f in sorted(fdir.glob("*.md")):
            try:
                out.append((f"{SOURCING}/formats/{f.name}", f.read_text(encoding="utf-8")))
            except OSError:
                pass
    return out


def _thumbs(frames_niche_dir, niche):
    """{video_id: chemin_relatif_a_frames_root} — id lu dans manifest.json
    (le nom du dossier est un slug, pas un id), vignette = première image
    de <slug>/frames/."""
    thumbs = {}
    if not frames_niche_dir.is_dir():
        return thumbs
    for d in sorted(frames_niche_dir.iterdir()):
        manifest = d / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            mtext = manifest.read_text(encoding="utf-8")
        except OSError:
            continue
        imgs = (
            sorted(p for p in (d / "frames").glob("*") if p.suffix.lower() in IMAGE_EXTS)
            if (d / "frames").is_dir()
            else []
        )
        if not imgs:
            continue
        rel = f"{niche}/{d.name}/frames/{imgs[0].name}"
        for token in mtext.replace('"', " ").replace("/", " ").split():
            if token.isdigit() and len(token) >= 15:  # id TikTok dans l'url
                thumbs[token] = rel
    return thumbs


def _transcript_entries(vault, niche):
    tdir = vault / SOURCING / "transcripts" / niche
    if not tdir.is_dir():
        return []
    cards = _cards(vault)
    thumbs = _thumbs(vault / SOURCING / "frames" / niche, niche)
    entries = []
    for f in sorted(tdir.glob("*.md")):
        if f.stem == "AGENTS":
            continue
        fm = _frontmatter(f)
        vid = f.stem
        entries.append(
            {
                "source": "transcript",
                "id": vid,
                "titre": fm.get("title"),
                "chaine": fm.get("channel"),
                "vues": _int_or_none(fm.get("views")),
                "note": None,
                "used": False,
                "captured": fm.get("captured"),
                "transcript_ref": f"{SOURCING}/transcripts/{niche}/{f.name}",
                "card_ref": next((ref for ref, txt in cards if vid in txt), None),
                "thumb": thumbs.get(vid),
            }
        )
    return entries


def _library_entries(vault, niche, warnings):
    ldir = vault / SOURCING / "library" / niche
    entries = []
    if not ldir.is_dir():
        return entries
    for meta_path in sorted(ldir.glob("*/meta.json")):
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            warnings.append(f"meta.json illisible : {meta_path.parent.name}")
            continue
        entries.append(
            {
                "source": "library",
                "id": m.get("video_id"),
                "titre": m.get("title"),
                "chaine": m.get("channel"),
                "vues": None,  # n'existe pas dans meta.json (spec §Réalité)
                "note": m.get("note"),
                "used": bool(m.get("usage")),
                "captured": m.get("vetted"),
                "vetted": m.get("vetted"),
                "transcript_ref": None,
                "card_ref": None,
                "thumb": None,
                "duree_s": m.get("duration_s"),
            }
        )
    return entries


def _channels(vault, niche, warnings):
    cj = vault / SOURCING / "channels.json"
    if not cj.is_file():
        return []
    try:
        return json.loads(cj.read_text(encoding="utf-8")).get(niche, [])
    except (OSError, ValueError):
        warnings.append("channels.json illisible")
        return []


def _production(vault, projet_dir, warnings):
    videos = []
    if not projet_dir:
        return {"videos": videos}
    proj = vault / projet_dir
    pub = {}
    pj = proj / "_feedback" / "published.json"
    if pj.is_file():
        try:
            pub = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            warnings.append("published.json invalide")
    outdir = proj / "outputs"
    if outdir.is_dir():
        for d in sorted(outdir.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue  # drafts exclus (spec §Backend règle 4)
            p = pub.get(d.name, {})
            videos.append(
                {
                    "slug": d.name,
                    "date": p.get("scheduled_at"),
                    "caption": p.get("caption"),
                    "tiktok_url": p.get("tiktok_url"),
                    "vues": p.get("views"),  # convention future, null aujourd'hui
                    "compte": p.get("account_name"),
                    "status": p.get("status"),
                }
            )
    videos.sort(key=lambda v: v["date"] or "", reverse=True)
    return {"videos": videos}


def build_hub(vault):
    vault = Path(vault)
    keys = set(NICHE_PROJECTS)
    for sub in ("transcripts", "library", "frames"):
        d = vault / SOURCING / sub
        if d.is_dir():
            keys |= {p.name for p in d.iterdir() if p.is_dir()}
    cj = vault / SOURCING / "channels.json"
    try:
        keys |= set(json.loads(cj.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass

    niches = []
    for key in sorted(keys):
        nom, projet_dir = NICHE_PROJECTS.get(key, (key, None))
        warnings = []
        videos = _transcript_entries(vault, key) + _library_entries(vault, key, warnings)
        # Tri : vues décroissantes puis date décroissante (spec §Backend règle 3)
        videos.sort(key=lambda v: (v["vues"] or 0, v.get("captured") or ""), reverse=True)
        niches.append(
            {
                "key": key,
                "nom": nom,
                "projet_dir": projet_dir,
                "warnings": warnings,
                "sourcing": {"chaines": _channels(vault, key, warnings), "videos": videos},
                "production": _production(vault, projet_dir, warnings),
            }
        )
    return {"niches": niches}


def resolve_frame(frames_root, rel_path):
    """Chemin absolu d'une frame sous frames_root, sinon 404 (anti-traversal
    + images uniquement)."""
    target = (Path(frames_root) / rel_path).resolve()
    root = Path(frames_root).resolve()
    if not target.is_relative_to(root) or target.suffix.lower() not in IMAGE_EXTS or not target.is_file():
        raise HTTPException(status_code=404, detail="Frame introuvable.")
    return target
