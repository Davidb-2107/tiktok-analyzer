---
statut: "Option B validée ; contrat métier de clustering défini au niveau conceptuel ; --cluster non implémenté"
prochaine_action: "produire le mapping canonique vidéo → sous-formula à partir des cards de @the.wisejourney et @viraldtoprw, puis seulement implémenter --cluster"
maj: 2026-09-15
---

# TikTok Analyzer

Contexte projet — service d'analyse vidéo self-hosted (voir API.md).

## Glossaire

- **Scène** : unité visuelle délimitée par un changement de plan détecté dans la vidéo ; ce terme ne désigne pas encore une interprétation sémantique comme « hook » ou « conclusion ».
- **Keyframe de scène** : image représentative d’une scène, choisie au milieu de celle-ci.
- **Frames régulières** : échantillons temporels conservés pour l’analyse visuelle continue, notamment le texte à l’écran et le hook.
- **Chaîne** : partition d’analyse indépendante à l’intérieur d’une niche ; ses cards, son style observé et ses formulas ne sont jamais hérités d’une autre chaîne.
- **Channel Formula** : enveloppe reproductible propre à une chaîne, décrivant ses constantes communes sans prétendre que toute la chaîne constitue une seule recette de contenu.
- **Sous-formula** : recette de contenu reproductible à l’intérieur d’une Channel Formula, définie par des mécaniques narratives et un angle de contenu communs ; un style visuel ou un niveau de Realism commun ne suffit pas à la créer.
- **Style visuel** : description de la réalisation et du rendu observés (`Video style`, `Realism`, caméra, palette, assets) ; il ne constitue pas à lui seul une formula de contenu.
- **Formula de contenu** : combinaison reproductible du hook, de la promesse ou de l’angle, de la progression narrative et du payoff ; elle peut produire plusieurs sous-formulas dans une même chaîne.
