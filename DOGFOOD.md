# Dogfood — le test décisif du pivot brief-compiler

**Portée : TOUS les projets de création vidéo TikTok** (Neon_Psycho, Stickman,
Psycho, Niche_PC…) — règle consignée dans `Shared/PRODUCTION-RULES.md`
§Dogfood : chaque session de prod remplit une ligne en fin de vidéo. Les vidéos
produites SANS brief (projets pas encore migrés) sont les lignes `baseline` —
c'est l'A/B naturel inter-projets.

**Question** : le brief fait-il gagner du temps *répété* sur la prod réelle ?
Verdict après **5 vidéos produites avec brief** (10 si ambigu) :
`gain médian X min/vidéo` ou `abandon` (ou reframe en outil d'onboarding de niche
si le gain se concentre sur la vidéo 1 — voir Effets ci-dessous).

## Deux effets à mesurer SÉPARÉMENT

Dans une même niche, les briefs 2..N sont quasi identiques (seul le topic change).
L'érosion du gain brut est donc attendue par construction — la mesure naïve
conclurait « abandon » à tort. On sépare :

- **Onboarding** (vidéo 1 d'une niche) : cadrage complet — budgets mots, verdict
  moteurs, gates, shot-list.
- **Répété** (vidéos 2+) : la discipline — script écrit au bon budget de mots du
  premier coup → rendu dans la fenêtre 62–75s **sans re-render**. C'est LE gain
  qui décide du pivot.

## Protocole (par vidéo produite, ~1 min de saisie)

Au moment de produire une vidéo TikTok (quel que soit le projet), remplir une
ligne du tableau :

- **cadrage_min** : minutes passées sur ce que le brief prétend remplacer —
  calcul mots/durée, relecture specs (fenêtre, pacing, captions), choix/rappel
  moteur, comptage plans. PAS l'écriture créative du script.
- **rerenders_durée** : nombre de re-renders causés par une durée hors fenêtre
  (le coût caché que le brief doit tuer ; un re-render TTS+montage ≈ le vrai gain).
- **hors_brief** : ce qu'il a fallu chercher/décider À CÔTÉ du brief (le backlog
  produit gratuit).

**Baseline** : toute vidéo produite sans brief (autres projets TikTok, au fil de
l'eau), + une estimation de mémoire des 2-3 dernières vidéos pré-brief, une
seule fois.

## Journal

| date | projet | vidéo (topic) | type (baseline/onboarding/répété) | cadrage_min | rerenders_durée | hors_brief | notes |
|---|---|---|---|---|---|---|---|
| 2026-05→07 | Stickman | couper-les-gens, hyper-independance, surpenser-ses-messages | baseline | n/d | 3 vidéos sous 62s (56.5/60.0/55.7s) | — | produites sous l'ancienne cible/WPM non calibré → non monétisables en l'état (obs #15959) |
| 2026-06-08 | Psycho | épisode (Darling v1→v2) | baseline | n/d | 2 (49.8s puis 59.7s avant fenêtre) | — | voice_wpm.json, phase-3 réel |
| 2026-06-11 | Psycho | épisode (Darling) | baseline | n/d | 1 (58.0s) | — | voice_wpm.json |
| 2026-06-21→07-09 | Psycho | 3 épisodes (Darling_at1.05) | baseline | n/d | 0 (68.0/71.6/68.1s) | — | post-calibration WPM : 3/3 dans la fenêtre du 1er coup |
| 2026-07-15 | Neon_Psycho | épisode-pilote | baseline | n/d | 1 (at1.10 56.5s ; base 62.5/63.1s ok) | — | gate_2_3 PASS à 62.5s (obs #19291) |

**Baseline reconstruite (2026-07-17, depuis voice_wpm.json + claude-mem — runs de
calibration exclus) : avant le budget de mots calibré, ~1-2 rendus hors fenêtre
par vidéo (juin) et 3 vidéos legacy sous le plancher de monétisation ; après
calibration WPM, 0/3.** Le mécanisme central du brief (budget de mots depuis le
WPM mesuré) a donc déjà un A/B historique en sa faveur — ce que le dogfood doit
montrer, c'est que le brief le rend systématique (chaque niche, chaque fois) et
que le reste du brief (moteurs, shot-list, gates) tient la même promesse.
`cadrage_min` baseline : non mesurable rétroactivement (prod pilotée en session).

## Verdict (à remplir après N=5)

- Gain médian cadrage (répété) : ___ min/vidéo
- Re-renders durée évités : ___ / N vidéos
- Décision : **produit** (gain répété net) / **outil d'onboarding** (gain
  concentré vidéo 1 — le pivot SaaS ne tient pas, l'outil interne oui) /
  **abandon** (gain < ~5 min et rien sur les re-renders)
