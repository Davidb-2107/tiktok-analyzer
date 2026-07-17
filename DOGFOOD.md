# Dogfood — le test décisif du pivot brief-compiler

**Question** : sur la prod Neon_Psycho hebdo, le brief fait-il gagner du temps
*répété* ? Verdict après **5 vidéos produites avec brief** (10 si ambigu) :
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

Au moment de produire une vidéo Neon_Psycho, remplir une ligne du tableau :

- **cadrage_min** : minutes passées sur ce que le brief prétend remplacer —
  calcul mots/durée, relecture specs (fenêtre, pacing, captions), choix/rappel
  moteur, comptage plans. PAS l'écriture créative du script.
- **rerenders_durée** : nombre de re-renders causés par une durée hors fenêtre
  (le coût caché que le brief doit tuer ; un re-render TTS+montage ≈ le vrai gain).
- **hors_brief** : ce qu'il a fallu chercher/décider À CÔTÉ du brief (le backlog
  produit gratuit).

**Baseline** : les 2-3 dernières vidéos produites AVANT le brief, estimées de
mémoire une seule fois (lignes `baseline`), + les gate-failures historiques du
pipeline Psycho si retrouvables.

## Journal

| date | vidéo (topic) | type (baseline/onboarding/répété) | cadrage_min | rerenders_durée | hors_brief | notes |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## Verdict (à remplir après N=5)

- Gain médian cadrage (répété) : ___ min/vidéo
- Re-renders durée évités : ___ / N vidéos
- Décision : **produit** (gain répété net) / **outil d'onboarding** (gain
  concentré vidéo 1 — le pivot SaaS ne tient pas, l'outil interne oui) /
  **abandon** (gain < ~5 min et rien sur les re-renders)
