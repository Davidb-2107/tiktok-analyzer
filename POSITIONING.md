# TikTok Analyzer — Positionnement marché & pivot produit

> Consolidation du fil de recherche 2026-07-17 : où se situe le système face au
> marché, et quelle est la stratégie SaaS défendable. Sources = 2 passes
> deep-research (fan-out web + vérification adversariale), ~210 agents, prix 2026.

## TL;DR

1. **"Analyseur de virality" = océan rouge.** Ni l'analyse (hook/arc/pacing) ni
   l'extraction de "formule reproductible par niche" ne sont un moat — ≥4
   concurrents dédiés les font déjà.
2. **Seul actif défendable** : l'intégration verticale *analyse → production*
   dans un stack de prod opinioné (prosodie mesurée, engine facts, voix calibrées,
   gates spec) — un coin *workflow*, pas un coin *feature*.
3. **Décision** : pivot vers un **compilateur de briefs** = dé-risqueur de
   production. Shape B (Format→Brief, pas de rendu), interne d'abord, mono-niche.
4. **v1 livré et testé** : gain réel mais **borné au cadrage** (chiffrage +
   conformité), pas à la créa.

---

## 1. La carte du marché (4 couches)

| Couche | Acteurs | Prix 2026 | Font-ils la déconstruction de contenu ? |
|---|---|---|---|
| **A. Analytics TikTok** | Exolyt (CHF 240-575/mo), Pentos, Analisa.io (59-239$/mo) | 60 → 950 $/mo | ❌ tracking comptes/hashtags/sons + social listening uniquement |
| **B. IA repurposing** | Opus Clip (15$), Vizard (29$), Submagic (~12-20$), Gling | 12 → 99 $/mo | ⚠️ PRODUCTION (découpe+captions). Opus Clip = seul à scorer (0-99, tri de clips d'UNE vidéo). Gling = coupe silences seulement |
| **C. Data API** | Apify (1,70$/1000), EnsembleData (100-1400$/mo), TikAPI | à l'usage | ❌ métadonnées brutes. **Scraping contre les ToS TikTok** |
| **D. Swipe viral** | ViralFindr (15$), Foreplay (59-459$) | 15 → 459 $/mo | ⚠️ discovery / inspiration, pas de déconstruction profonde |

**Prix qui fonctionnent** : créateur solo 15-89 $/mo (churn élevé), agence
175-950 $/mo (ARPU haut, déjà servie par Hook/Exolyt), freemium dominant chez les
entrants IA.

## 2. Les concurrents qui touchent notre cœur (catégorie ANALYSE dédiée)

Une classe distincte, en croissance, vise *exactement* notre proposition :

- **Hook** (askhook.com) — freemium, Starter 89$/mo. Track chaque vidéo d'une
  catégorie sur IG/TikTok/Shorts, analyse hook/pacing/script, réécrit en brand
  voice, natif Slack/Claude/WhatsApp. **Différenciateur qu'on n'a pas** :
  détection organique-vs-boosté via Meta Ad Library. *Menace n°1.*
- **Viral Finder** (viralfinder.ai) — score 0-100 frame-by-frame (5 dims), hook
  3s, **Format Detector** (connecte une chaîne, 500+ vidéos, Gold vs Bronze,
  "formule de viralisation par format"). Chevauche notre moat "formule de niche".
- **Format Finder** (onepeakcreative) — "Analyse Your Videos" (transcript →
  hook rate, watch %, drop-off) + bibliothèque **65+ formats prouvés** → script.
- **ViralShorts Studio** — reverse-engineering (storyboard, script, pacing) +
  comparaison batch 5-20 vidéos. 49$/mo.
- **ViralDecode** — URL → hook/structure/arc/pacing + score + **génère ta version
  pour ta niche**. free 3/mo, Pro 50/mo.

## 3. La correction de moat (le point clé)

Le premier rapport croyait la "formule reproductible par niche" unique. **Faux**
(high confidence) : Viral Finder et Format Finder la vendent déjà.

**Seul delta qu'aucun concurrent surveillé n'affiche** :
- prosodie / voix acoustique (pitch, genre, débit) ;
- transcript **word-level timing** ;
- extraction du **texte overlay** à l'écran ;
- profondeur vision Claude frame-par-frame.

Moat **étroit** (`medium confidence` — c'est une absence *marketing*, pas prouvée
sous le capot). ⇒ Le coin défendable est **distribution/workflow** (intégration
verticale dans un stack de prod précis), pas une feature d'analyse isolée.

**Risque structurel** : le download par URL a la même dépendance ToS que le
scraping (interdit sauf accord écrit ; violation ToS ≠ illégalité *hiQ v. LinkedIn*,
mais risque blocage/coupure pour un produit payant). À neutraliser avant de facturer.

## 4. Le pivot : compilateur de briefs (dé-risqueur de prod)

**Insight** : tous les concurrents s'arrêtent à une moitié du fossé (analyse OU
production). Personne ne ferme la boucle *format gagnant → plan de tournage
exécutable* couplé à un stack de prod opinioné. Or ce stack existe déjà, éclaté :

```
TikTok Analyzer → extract-format → Sourcing registry     (ANALYSE, en place)
──────────── LE PRODUIT = CETTE COUTURE ────────────
format card → brief.json  (script beaté + budgets mots WPM + shot-list +
                           prompt-pack moteur + gates spec importées)
──────────────────────────────────────────────────
Higgsfield/Kling/Seedance + ElevenLabs + cutcli/CapCut   (PROD, en place)
```

**Config verrouillée** : shape **B** (Format→Brief, PAS de rendu vidéo — coût/user
et multi-tenant prohibitifs) · **interne d'abord**, SaaS ensuite · **mono-niche**
(neon_psycho), profondeur avant largeur.

### Ce que le brief verrouille (= le delta, mis en dur dans le contrat)
- WPM par beat avec provenance voix calibrée (`wpm_source` requis).
- prompt_pack moteur exécutable, `provenance` ENGINE-FACTS **requise**.
- overlay_text par shot.
- gates **importées** du SOT `Shared/tiktok-spec/tiktok_duration.py`, jamais figées.
- captions `max_lines: 1` en `const`.

Artefacts : `brief.schema.json` (contrat), `brief_compiler.py` (compilateur),
`test_brief_compiler.py` + `brief_selfcheck.py` (verts, couplés au vrai SOT),
`brief_neon_psycho_<channel>.json` (briefs channel-scoped générés) ;
`legacy/brief_neon_psycho.json` (artefact agrégé historique, non-production).

Le vault reste l'unique source de production. `tests/fixtures/vault/` ne contient
que des données de test. Chaque brief identifie sa chaîne dans `source.channel`
et cite des références auto-descriptives et qualifiées par chaîne :
`format_card_ref` et `channel_formula_ref`. Aucun style, réalisme, hook ou formula
de projet n'est inféré avant l'analyse de la chaîne sélectionnée : les styles peuvent
différer d'une chaîne à l'autre.

## 5. Verdict v1 (honnête, testé sur un gagnant @viraldtoprw)

**Gain réel mais borné.**
- ✅ Cadrage chiffré + conformité en 1 commande : budgets mots/beat depuis le WPM
  mesuré *avant* d'écrire (fin des rendus à 58s ou 82s), gates jamais recopiées,
  décisions moteur citées (kling std vs turbo, sound off, Seedance=hero), shot-list
  pré-comptée (25 plans conformes, hook sans coupe, total = durée beats).
- ❌ Pas la créa : beats et prompts par plan restent manuels ; prompts génériques
  sans image_ref character-sheet.

**Repositionnement** : *"un format gagnant → plan de tournage chiffré et
spec-conforme, instantané"* — un **dé-risqueur de production**, pas un créateur de
contenu. Proposition étroite mais plus défendable que toute la catégorie B.

## 6. Dette & prochaines étapes

- **Dette amont — tooling livré, couverture presque complète** : le contrat de validation
  des FORMAT CARDs (`Projects/Sourcing/tools/format_card_registry.py` dans le
  vault) et le compilateur conscient de la couverture
  (`inspect_cards`/`parse_cards`/`compile_brief(..., strict=True)` dans
  `brief_compiler.py`) sont livrés et testés. `neon_psycho` a désormais 10/10
  cards valides, mais reste hétérogène : sa majorité de hook est sous le seuil
  des deux tiers. `dark_psycho` a 7/8 cards valides ; la huitième source porte
  le statut explicite `blocked_source_unavailable`. Le mode `--strict` échoue
  donc encore pour deux raisons distinctes et non résolues : homogénéité
  insuffisante pour `neon_psycho`, couverture bloquée pour `dark_psycho`.
  **Prochaine étape** : récupérer ou remplacer la source bloquée de
  `dark_psycho` avant de re-générer les briefs stricts.
- `--cluster` reste différé : il exige d'abord un mapping canonique
  vidéo → sous-formula. Il n'existe pas de formula `neon_psycho` partagée
  prête pour la production.
- **Questions ouvertes non résolues** : (1) Viral Finder/ViralDecode font-ils déjà
  de la prosodie sous le capot sans l'annoncer ? Si oui, le dernier moat tombe.
  (2) Voie d'accès *autorisée* aux données (Research API, contenu uploadé par
  l'user) qui neutralise le risque ToS. (3) Précision réelle des virality scores —
  aucun benchmark indépendant n'en valide un seul.
- **Angles sous-couverts par la recherche** : Munch (tué 0-3), Crayo, Klap, Nova.

---
*Méthode : deep-research harness (fan-out 6 angles → fetch 25 sources/pass →
extraction claims → vérif adversariale 3 votes → synthèse citée). Passe 1 : 20/25
claims confirmés. Passe 2 : 18/25. Prix datés 2026-07-17, volatils chez les
entrants IA.*
