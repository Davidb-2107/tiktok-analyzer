# Archivage et validation des FORMAT CARDs par vidéo — Plan d'implémentation

> **Pour les agents :** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Chaque tâche se termine par une vérification indépendante.

**Goal:** rendre la taxonomie `style / realism / hook_mechanic` fiable et traçable pour chaque vidéo enregistrée dans une niche, sans modifier le contrat de production du brief.

**Architecture:** conserver la FORMAT CARD dans le fichier transcript de la vidéo, mais faire valider sa structure et ses trois champs taxonomiques par un petit module partagé. `brief_compiler.py` n'utilise la voie cards que si la couverture est complète et valide ; sinon il reste permissif en développement et signale explicitement le fallback. Le mode `--strict` bloque uniquement la sortie taxonomique incomplète, pas les sujets voix ou moteurs hors périmètre.

**Tech Stack:** Python 3.8+ standard library, Markdown, `unittest`, Obsidian vault, Git Bash sous Windows.

**Spec:** `C:/Users/dbele/Documents/ObsidianVault/Wiki_Claude/Projects/Sourcing/SPEC-transcripts.md` et `C:/Users/dbele/Documents/ObsidianVault/Wiki_Claude/Shared/claude-plugins/tiktok-analyzer/skills/extract-format/SKILL.md`.

**État d'avancement au 2026-09-11:**

- Tâches 1 et 2 sont terminées et vérifiées dans le vault (`e770620`, `ec3283e`, puis correctifs de statut/backfill).
- La couverture cards, les tests du compilateur et le backfill des données sont terminés pour Tâches 3 à 5, avec une exception explicite : `dark_psycho` possède 7 cards valides et 1 source vidéo bloquée (`blocked_source_unavailable`).
- Tâche 3 est maintenant terminée : FCR est chargé par `importlib.util.spec_from_file_location` sans mutation de `sys.path`, avec vérification d'import isolée et erreur actionnable chaînée.
- Le garde-fou `FCR_MODULE.is_file()` et l'erreur d'import actionnable chaînée sont conservés ; les tests Analyzer et le self-check restent verts.
- La revue globale a aussi corrigé la validation des champs dupliqués dans le module canonique, aligné le fixture CI et actualisé `POSITIONING.md` ; le commit vault reste isolé jusqu'à intégration explicite.
- La régénération finale de Tâche 6 reste conditionnée par la décision sur l'hétérogénéité de `neon_psycho` et la récupération de la source bloquée de `dark_psycho`.

## Global Constraints

- L'archivage est obligatoire uniquement lorsqu'une niche est connue ; une analyse `extract-format` sans projet cible ne crée aucun fichier.
- Le template et la taxonomie existants de `extract-format` restent le contrat canonique ; aucun champ ni libellé existant n'est renommé.
- Une card existante n'est jamais écrasée par défaut ; le remplacement exige une option explicite.
- Le bloc `Transcript (verbatim)` ne doit jamais être réécrit si l'analyse ou la validation échoue ; seul le statut de validation peut être mis à jour séparément.
- `brief.schema.json`, les gates TikTok, le WPM et `ENGINE-FACTS` restent inchangés.
- Aucune dépendance Python externe n'est ajoutée au pipeline Sourcing.
- Les scripts sont lancés depuis Git Bash avec Python ; les chemins utilisés ci-dessous sont ceux du vault réel.

---

## 1. État initial vérifié au 2026-08-28

- La skill `extract-format` contient déjà l'archivage à l'étape 5 et demande déjà de remplir tous les champs : il ne faut pas créer une seconde étape d'archivage.
- `brief_compiler.py:147` parse actuellement toute section commençant par `## FORMAT CARD`, vote sur les cards présentes, puis remplace l'inférence par mots-clés dès qu'au moins une card existe.
- Le parser accepte actuellement des labels absents ou inconnus en les transformant silencieusement en `other` et en realism `3`.
- Le registre contient actuellement 10 vidéos pour `neon_psycho`, dont 5 avec card, et 8 vidéos pour `dark_psycho`, dont 0 avec card.
- Les frames persistées couvrent 5 vidéos neon et 3 vidéos dark ; 10 vidéos nécessitent donc probablement une nouvelle analyse avant rédaction de leur card.
- Le test d'intégration existant échoue déjà car il attend exactement 5 vidéos alors que le registre en contient 10 : `test_brief_compiler.py:21`.
- `dark_psycho` conserve actuellement deux signaux hors périmètre — voix non calibrée et verdict moteur absent — donc sa readiness globale ne peut pas devenir vide dans ce plan.
- Le schéma du brief interdit les propriétés supplémentaires dans `source`. La couverture des cards sera donc un rapport de validation/log, pas un nouveau champ JSON.

### État vérifié au 2026-09-11

- `neon_psycho` : 10/10 cards valides ; `format_card_registry.py --verify` et `backfill_cards.py --verify` passent.
- `dark_psycho` : 7/8 cards valides et 1 vidéo explicitement bloquée faute de flux vidéo exploitable ; aucun contenu n'est inventé pour cette entrée.
- Le statut `blocked_source_unavailable` est une exception documentée, pas une card valide : il reste dans `n_videos`, est séparé des erreurs ordinaires et empêche `parse_cards()` d'activer la voie taxonomique complète.
- La vérification du vault couvre le chemin blocked ; la suite Sourcing actuelle compte 20 tests verts. Le test analyzer couvre également `n_blocked`, le warning readiness et le refus de la voie cards en couverture incomplète.

## 2. Décisions de conception

1. Une card est **présente** si le fichier contient exactement une section `## FORMAT CARD`.
2. Une card est **valide** si elle contient exactement une valeur reconnue pour chacun des champs `Video style`, `Realism` et `Hook mechanic`. Une explication après un tiret long est permise ; une phrase comme `not a talking head` ne doit pas être reconnue comme `talking head`.
3. Une niche est **complète** seulement si chaque vidéo du registre possède une card valide et unique.
4. `parse_cards()` ne retourne une taxonomie que pour une niche complète. Une couverture partielle utilise le fallback et produit un avertissement avec `n_valid/n_total`.
5. Le mode strict échoue si une card manque, est dupliquée, contient un champ inconnu ou si aucune modalité ne représente au moins deux tiers des cards. Cette dernière règle empêche de faire passer une niche multi-format pour un format unique.
6. Le backfill complète uniquement les cards absentes. Il ne relance pas une skill LLM depuis Python et ne remplace pas une card existante sans `--replace` explicite.
7. `blocked_source_unavailable` est un statut source explicite : il est accepté par les vérificateurs du registre/backfill, mais compte toujours dans le total analyzer et n'est jamais traité comme une card valide. Le mode analyzer `--strict` reste en échec explicite tant que cette vidéo ne peut pas être analysée.

## 3. Fichiers impactés

| Fichier | Action | Responsabilité |
|---|---|---|
| `Projects/Sourcing/tools/format_card_registry.py` | Créer | Contrat canonique, extraction de sections, validation et upsert idempotent |
| `Projects/Sourcing/tests/test_format_card_registry.py` | Créer | Tests purs du contrat et de l'écriture sûre |
| `Projects/Sourcing/tools/backfill_cards.py` | Créer | Inventaire et vérification du backfill ; aucune génération LLM implicite |
| `Projects/Sourcing/SPEC-transcripts.md` | Modifier | Décrire transcript + card et le statut de validation |
| `Shared/claude-plugins/tiktok-analyzer/skills/extract-format/SKILL.md` | Modifier | Ajouter la postcondition de validation à l'étape 5 existante |
| `brief_compiler.py` | Modifier | Utiliser le contrat partagé, gérer couverture/strict/fallback |
| `test_brief_compiler.py` | Modifier | Corriger le smoke test réel et tester la couverture partielle |
| `brief_neon_psycho.json`, `brief_dark_psycho.json` | Régénérer | Produire les briefs après backfill validé |
| `POSITIONING.md` | Modifier | Marquer uniquement la dette taxonomique comme résolue |

## 4. Plan d'exécution

### Tâche 1 — Créer le contrat et le validateur de FORMAT CARD — terminée

**Files:**

- Create: `Projects/Sourcing/tools/format_card_registry.py`
- Create: `Projects/Sourcing/tests/test_format_card_registry.py`

**Interfaces produites:**

```python
def parse_card(card_text: str) -> dict:
    """Return valid, canonical fields and a list of validation errors."""

def inspect_file(path: Path) -> dict:
    """Return n_sections, valid, errors and the parsed card for one registry file."""

def upsert_card(path: Path, card_text: str, replace: bool = False) -> str:
    """Append one missing card; replace only when replace=True; return an action label."""
```

Interface CLI de vérification :

```bash
python Projects/Sourcing/tools/format_card_registry.py --verify --niche neon_psycho
python Projects/Sourcing/tools/format_card_registry.py --verify --niche dark_psycho
```

- [x] Écrire les tests `test_valid_card`, `test_missing_required_label`, `test_unknown_taxonomy_value`, `test_rejects_substring_match`, `test_duplicate_card_sections` et `test_upsert_is_idempotent`.
- [x] Exécuter `python -m unittest discover -s Projects/Sourcing/tests -p "test_*.py" -v` depuis le vault et constater les échecs initiaux.
- [x] Implémenter l'extraction bornée d'une section card jusqu'au prochain titre `##`, au lieu de capturer tout le fichier jusqu'à EOF.
- [x] Implémenter la validation exacte des trois valeurs : les explications après `—` sont ignorées, les valeurs libres et les sous-chaînes ambiguës sont rejetées.
- [x] Implémenter `upsert_card()` afin que le second appel retourne `already_present` et ne duplique pas la section ; `replace=True` est le seul mode qui remplace une section existante.
- [x] Relancer la suite `unittest` et obtenir un résultat vert ; les tests couvrent aussi le filtre transcript et le résumé CLI ASCII.

### Tâche 2 — Aligner la spec Sourcing et la skill existante — terminée

**Files:**

- Modify: `Projects/Sourcing/SPEC-transcripts.md:14-20,46-78,157-161`
- Modify: `Shared/claude-plugins/tiktok-analyzer/skills/extract-format/SKILL.md:76-83`

- [x] Remplacer la description « transcript uniquement » par « transcript verbatim + FORMAT CARD par vidéo lorsque la niche est connue ».
- [x] Documenter les états `complete`, `needs_review` et `blocked_source_unavailable`, les trois labels validés et la règle d'absence de niche.
- [x] Conserver l'étape 5 d'archivage existante ; préciser qu'après l'écriture l'agent relit le fichier et vérifie qu'il existe exactement une card valide.
- [x] Préciser qu'une erreur de validation marque le fichier `format_card_status: needs_review` sans modifier le bloc transcript ni masquer l'échec.
- [x] Documenter que le backfill ne remplace pas les cards existantes sans option explicite.
- [x] Relire les deux documents et vérifier qu'ils ne contiennent plus deux contrats contradictoires sur le contenu du registre ; l'exception source bloquée est désormais explicitement décrite.

### Tâche 3 — Rendre `brief_compiler.py` conscient de la couverture — terminée

**Files:**

- Modify: `brief_compiler.py:124-168,340-350,440-462`
- Modify: `brief.schema.json` — ne pas modifier ; confirmer par le self-check que le schéma reste inchangé

**Résultat:** le chargement FCR utilise `importlib.util.spec_from_file_location` depuis `FCR_MODULE`, sans préfixer `sys.path`; l'import configuré et le fixture CI sont vérifiés, les erreurs restent actionnables et chaînées, et les checks Analyzer sont verts.

**Interfaces produites:**

```python
def inspect_cards(videos: list) -> dict:
    """Return n_videos, n_present, n_valid, n_blocked, errors and majority shares."""

def parse_cards(videos: list):
    """Return (style, realism, hook_mechanic) only for complete valid input; else None."""

def compile_brief(niche, voice=None, language="fr", strict=False):
    """Compile a brief; strict=True raises on incomplete or heterogeneous cards."""

def readiness(brief, format_report=None) -> list:
    """Keep existing readiness checks and optionally add card coverage diagnostics."""
```

- [x] Déplacer les constantes `STYLES` et `MECHANICS` vers `format_card_registry.py`, puis les importer dans `brief_compiler.py` pour éviter deux taxonomies divergentes.
- [x] Remplacer la regex de card ouverte par l'extracteur borné du module partagé et détecter les sections multiples.
- [x] Faire retourner `None` à `parse_cards()` dès qu'une vidéo est absente, dupliquée ou invalide ; une card partielle ne doit plus activer la voie noble.
- [x] Ajouter `inspect_cards()` et un avertissement explicite du type `[niche] n_valid/n_total cards — fallback keywords` lorsque la couverture est incomplète ; les sources blocked sont reportées séparément.
- [x] Ajouter `--strict` à `main()`. En mode strict, lever une erreur lisible avec les chemins des fichiers fautifs ; ne pas faire échouer le mode permissif de développement.
- [x] Faire accepter à `readiness()` un rapport optionnel sans ajouter de propriété au JSON. Les avertissements voix/moteur restent distincts des avertissements cards.
- [x] Ajouter le contrôle de majorité minimale de deux tiers en strict ; une niche hétérogène est orientée vers un nouveau cluster/formula, pas forcée dans un vote unique.
- [x] Remplacer l'injection globale `sys.path.insert(0, ...)` du compilateur par un chargement explicite via `importlib.util.spec_from_file_location` depuis `FCR_MODULE`, afin d'éviter qu'un module homonyme du dossier vault ne masque un import local ou standard-library ; conserver une erreur chaînée et actionnable si le fichier est absent ou non importable.
- [x] Ajouter une vérification d'import isolée (sans modifier `sys.path`) et confirmer que le compilateur charge bien le fichier `Projects/Sourcing/tools/format_card_registry.py` du vault configuré.
- [x] Exécuter `python brief_selfcheck.py` et vérifier que `brief.schema.json` n'a pas été modifié.

### Tâche 4 — Corriger la suite de tests du compilateur — terminée

**Files:**

- Modify: `test_brief_compiler.py:21-24,63-88`

- [x] Remplacer l'assertion rigide `len(...) == 5` par des assertions de présence, d'unicité et de cohérence avec le registre réel.
- [x] Ajouter des fixtures en mémoire pour une niche complète, une niche partielle, une card invalide, une card dupliquée et un libellé qui ne doit pas matcher par sous-chaîne.
- [x] Tester que la niche partielle utilise le fallback en mode permissif et échoue avec `--strict`.
- [x] Tester que `readiness(brief)` continue à signaler séparément les valeurs de voix et de moteur non résolues, y compris le warning de source bloquée.
- [x] Utiliser la commande réellement applicable au fichier actuel : `python test_brief_compiler.py`. Ne pas documenter `pytest -k cards` tant que le fichier ne contient pas de fonctions pytest collectables.
- [x] Exécuter `python test_brief_compiler.py` depuis le contexte analyzer et obtenir un résultat vert sur les données présentes.

### Tâche 5 — Produire le worklist de backfill sans automatisation LLM implicite — terminée

**Files:**

- Create: `Projects/Sourcing/tools/backfill_cards.py`

**Commandes produites:**

```bash
python Projects/Sourcing/tools/backfill_cards.py --niche neon_psycho --check
python Projects/Sourcing/tools/backfill_cards.py --niche dark_psycho --check
python Projects/Sourcing/tools/backfill_cards.py --niche neon_psycho --verify
python Projects/Sourcing/tools/backfill_cards.py --niche dark_psycho --verify
```

- [x] Faire de `--check` une opération sans écriture qui liste chaque fichier sans card, chaque card invalide, l'URL et la disponibilité d'un manifest de frames.
- [x] Faire de `--verify` une opération sans écriture qui retourne un code non nul pour toute card manquante/invalide/dupliquée non justifiée ; une source explicitement `blocked_source_unavailable` est reportée séparément et acceptée.
- [x] Pour chaque entrée traitable du worklist, lancer `/extract-format` dans le contexte de la niche ; la card est ensuite validée et archivée par `format_card_registry.py`. La source non récupérable reste bloquée sans card inventée.
- [x] Ne pas demander à `backfill_cards.py` de « relancer extract-format » : une skill est un workflow agentique, pas une fonction Python appelable implicitement.
- [x] Ne traiter que les cards absentes durant le backfill initial ; réserver `--replace` à une correction manuelle explicitement revue.
- [x] Exécuter d'abord les deux `--check`, puis analyser les frames existantes avant de relancer l'API pour les vidéos sans manifest.
- [x] Après chaque lot, exécuter le `--verify` correspondant et conserver le diff des fichiers transcripts comme preuve de l'absence de modification du verbatim.

### Tâche 6 — Régénérer, vérifier et documenter — à venir

**Files:**

- Regenerate: `brief_neon_psycho.json`, `brief_dark_psycho.json`
- Modify: `POSITIONING.md:118-122`

- [ ] Vérifier que les 10 fichiers `neon_psycho` et les 8 fichiers `dark_psycho` ont chacun exactement une card valide.
- [ ] Exécuter `python brief_compiler.py neon_psycho --strict` et `python brief_compiler.py dark_psycho --strict`.
- [ ] Exécuter `python brief_selfcheck.py` puis `python test_brief_compiler.py`.
- [ ] Vérifier que les briefs prennent leur taxonomie depuis les cards et que `style` et `hook_mechanic` ne proviennent plus d'un fallback dans le chemin strict.
- [ ] Accepter comme résultat normal que `dark_psycho` conserve encore ses avertissements voix/moteur ; ils ne doivent pas être déclarés résolus par ce plan.
- [ ] Mettre à jour `POSITIONING.md` pour déclarer résolue uniquement la dette d'archivage/parsing taxonomique.
- [ ] Vérifier le diff et séparer les éventuels commits Sourcing, skill et Analyzer selon le dépôt qui les contient ; ne pas regrouper des changements de données non vérifiés avec le code.

## 5. Critères d'acceptation

- Chaque fichier transcript ciblé possède exactement une section `## FORMAT CARD`, sauf une entrée portant le statut explicite `blocked_source_unavailable` et sa justification.
- `python Projects/Sourcing/tools/format_card_registry.py --verify --niche <niche>` ne signale aucune card manquante, dupliquée ou invalide ; les sources blocked sont comptées séparément et restent visibles.
- Une entrée inconnue ou partielle est refusée par le validateur et n'est jamais convertie silencieusement en valeur exploitable.
- Une couverture partielle active le fallback uniquement en mode permissif et produit un avertissement `n_valid/n_total`.
- `python brief_compiler.py neon_psycho --strict` réussit après backfill ; `dark_psycho --strict` ne devient vert qu'après récupération de la source bloquée, et son échec actuel doit rester explicite.
- `python brief_selfcheck.py` et `python test_brief_compiler.py` réussissent.
- Aucun champ du `brief.schema.json` n'est ajouté ou retiré.
- La readiness taxonomique est propre pour les cards valides ; le warning de source bloquée et les valeurs non résolues de voix/moteur de `dark_psycho` restent explicitement hors périmètre de résolution immédiate.
- Une seconde exécution du backfill ne duplique aucune section et ne modifie pas un transcript existant.

## 6. Risques et réponses

| Risque | Réponse |
|---|---|
| La skill produit un libellé libre | Validation post-écriture ; card `needs_review`, jamais acceptée par `--strict`. |
| Une card existante est réécrite par erreur | `upsert_card()` refuse par défaut ; remplacement réservé à `--replace`. |
| Une niche contient plusieurs formats | Exiger deux tiers de majorité en strict et ouvrir un cluster/formula séparé si le seuil échoue. |
| Le dossier vault contient un module homonyme | Charger `format_card_registry.py` par chemin explicite avec `importlib`, sans préfixer `sys.path`. |
| Les frames historiques manquent | Produire d'abord le worklist ; ne relancer l'API qu'après inventaire et conserver le manifest. |
| Le registre grossit et rend le smoke test instable | Tester les propriétés du registre, pas un nombre historique codé en dur. |
| La readiness globale reste non vide | Distinguer les gates cards des dépendances voix/moteurs, qui ont leur propre plan. |
| Une source vidéo reste indisponible | Marquer `blocked_source_unavailable`, conserver la justification et empêcher la voie cards complète ; reprendre le backfill si une preuve vidéo fiable réapparaît. |

## 7. Estimation corrigée

- Contrat, validateur, docs et tests : 1 à 1,5 jour.
- Durcissement du compilateur : 0,5 à 1 jour.
- Worklist et backfill de 13 cards manquantes, dont environ 10 analyses nécessitant probablement de nouvelles frames : 1,5 à 3 jours selon les téléchargements et la revue.
- Régénération et vérification : 0,5 jour.

**Total réaliste : 3,5 à 6 jours**, plutôt que 3 à 4 jours, car le travail restant est principalement une revue vidéo/LLM et non une simple écriture de fichiers.
