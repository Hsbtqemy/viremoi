# VireMoi

Déplace un ensemble de fichiers d'un dossier source vers un dossier destination, à partir d'une liste de noms de fichiers. Supporte la recherche récursive, le mode simulation et la journalisation CSV.

## Prérequis

Python 3.10+, aucune dépendance externe.

## Lancement

```bash
python viremoi.py
```

Le script pose une série de questions interactives :

| Question | Description |
|---|---|
| Fichier texte contenant la liste des fichiers | Chemin vers un `.txt` listant un nom de fichier par ligne |
| Dossier source | Dossier (ou arborescence) dans lequel chercher les fichiers |
| Dossier destination | Dossier vers lequel déplacer les fichiers (créé si besoin) |
| Chercher dans les sous-dossiers ? | Recherche récursive dans toute l'arborescence source |
| Faire un test sans déplacer ? | Mode simulation — aucun fichier n'est réellement déplacé |
| Chemin du journal CSV | Fichier de log des opérations (défaut : `journal_deplacement.csv` dans la destination) |

## Fichier liste

Un fichier texte plain, un nom de fichier par ligne. Les lignes vides et les commentaires (`#`) sont ignorés.

```
# Fichiers à déplacer
rapport_2024.pdf     ← extension précisée  : cherche exactement ce nom
photo_vacances       ← sans extension      : cherche photo_vacances.* (jpg, png…)
# archive.zip        ← ignoré
notes.txt
```

**Règle d'extension :**
- Sans extension → le script cherche tout fichier dont le nom de base correspond (ex. `photo_vacances` trouve `photo_vacances.jpg`). Si plusieurs fichiers portent ce stem, l'entrée est marquée `ambiguous` et ignorée.
- Avec extension → correspondance exacte uniquement.

## Statuts de sortie

| Statut | Signification |
|---|---|
| `moved` | Fichier déplacé avec succès |
| `dry_run` | Déplacement simulé (mode test) |
| `missing` | Fichier introuvable dans la source |
| `ambiguous` | Plusieurs fichiers portent ce nom (mode récursif uniquement) |
| `already_exists` | Fichier déjà présent dans la destination |
| `protected` | Fichier ignoré car il s'agit de la liste source ou du journal CSV |
| `error` | Erreur lors du déplacement |

## Journal CSV

Après chaque exécution, un fichier CSV est écrit avec les colonnes :

- `requested_name` — nom demandé
- `status` — statut de l'opération
- `source_path` — chemin source résolu
- `destination_path` — chemin destination
- `detail` — message explicatif

## Exemples

**Déplacement simple (dossier plat) :**
```
Fichier texte : /home/user/liste.txt
Dossier source : /home/user/downloads
Dossier destination : /home/user/archives
Sous-dossiers : n
Test : n
```

**Recherche récursive avec simulation préalable :**
```
Fichier texte : /home/user/liste.txt
Dossier source : /home/user/projets
Dossier destination : /home/user/exports
Sous-dossiers : o
Test : o   ← vérifier sans risque avant de lancer pour de vrai
```
