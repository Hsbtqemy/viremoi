from pathlib import Path
import shutil
import csv
import sys


def load_filenames(txt_file: Path) -> list[str]:
    """Charge les noms de fichiers depuis un fichier texte."""
    if not txt_file.exists():
        raise FileNotFoundError(f"Fichier liste introuvable : {txt_file}")

    if not txt_file.is_file():
        raise ValueError(f"Le chemin indiqué n'est pas un fichier : {txt_file}")

    filenames = []
    with txt_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            filenames.append(line)

    return filenames


def ask_file_path(prompt: str) -> Path:
    """Demande un chemin vers un fichier existant."""
    while True:
        raw = input(prompt).strip().strip('"')
        path = Path(raw)

        if path.exists() and path.is_file():
            return path

        print("Fichier invalide. Réessaie.\n")


def ask_existing_directory(prompt: str) -> Path:
    """Demande un dossier existant."""
    while True:
        raw = input(prompt).strip().strip('"')
        path = Path(raw)

        if path.exists() and path.is_dir():
            return path

        print("Dossier invalide. Réessaie.\n")


def ask_destination_directory(prompt: str) -> Path:
    """Demande un dossier destination, avec création si nécessaire."""
    while True:
        raw = input(prompt).strip().strip('"')
        path = Path(raw)

        if path.exists():
            if path.is_dir():
                return path
            print("Ce chemin existe mais ce n'est pas un dossier.\n")
            continue

        answer = input(f"Le dossier {path} n'existe pas. Le créer ? (o/n) ").strip().lower()
        if answer in {"o", "oui", "y", "yes"}:
            path.mkdir(parents=True, exist_ok=True)
            return path

        print("Réessaie.\n")


def ask_yes_no(prompt: str) -> bool:
    """Pose une question oui/non."""
    while True:
        answer = input(prompt).strip().lower()
        if answer in {"o", "oui", "y", "yes"}:
            return True
        if answer in {"n", "non", "no"}:
            return False
        print("Réponds par o/n.\n")


def ask_log_file(default_dir: Path) -> Path:
    """Demande où enregistrer le journal CSV."""
    default_path = default_dir / "journal_deplacement.csv"
    raw = input(
        f"Chemin du journal CSV [Entrée pour défaut: {default_path}] : "
    ).strip().strip('"')

    if not raw:
        return default_path

    return Path(raw)


def build_recursive_index(source_dir: Path) -> dict[str, list[Path]]:
    """
    Construit un index {nom_de_fichier: [liste des chemins complets]}.
    Utile pour chercher rapidement dans toute l'arborescence.
    """
    index: dict[str, list[Path]] = {}

    for path in source_dir.rglob("*"):
        if path.is_file():
            index.setdefault(path.name, []).append(path)

    return index


def write_log_csv(log_path: Path, rows: list[dict]) -> None:
    """Écrit le journal CSV des opérations."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "requested_name",
        "status",
        "source_path",
        "destination_path",
        "detail",
    ]

    with log_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def move_files(
    file_list_path: Path,
    source_dir: Path,
    destination_dir: Path,
    recursive: bool = False,
    dry_run: bool = False,
    exclude: set[Path] | None = None,
) -> list[dict]:
    """
    Déplace les fichiers listés dans file_list_path de source_dir vers destination_dir.

    Retourne une liste de lignes pour le journal CSV.
    """
    filenames = load_filenames(file_list_path)
    logs: list[dict] = []

    recursive_index = build_recursive_index(source_dir) if recursive else None

    moved = 0
    simulated = 0
    missing = 0
    skipped = 0
    ambiguous = 0
    errors = 0
    protected = 0

    for filename in filenames:
        destination_file = destination_dir / filename

        # Recherche du fichier source
        if recursive:
            matches = recursive_index.get(filename, []) if recursive_index else []
            if len(matches) == 0:
                print(f"[ABSENT] {filename}")
                missing += 1
                logs.append({
                    "requested_name": filename,
                    "status": "missing",
                    "source_path": "",
                    "destination_path": str(destination_file),
                    "detail": "Aucun fichier trouvé dans l'arborescence source.",
                })
                continue

            if len(matches) > 1:
                print(f"[AMBIGU] {filename} -> plusieurs fichiers portent ce nom")
                ambiguous += 1
                logs.append({
                    "requested_name": filename,
                    "status": "ambiguous",
                    "source_path": " | ".join(str(p) for p in matches),
                    "destination_path": str(destination_file),
                    "detail": "Plusieurs fichiers trouvés avec le même nom.",
                })
                continue

            source_file = matches[0]

        else:
            source_file = source_dir / filename
            if not source_file.exists():
                print(f"[ABSENT] {filename}")
                missing += 1
                logs.append({
                    "requested_name": filename,
                    "status": "missing",
                    "source_path": str(source_file),
                    "destination_path": str(destination_file),
                    "detail": "Fichier absent du dossier source.",
                })
                continue

        # Protection contre le déplacement de fichiers système (liste, journal)
        if exclude and source_file.resolve() in exclude:
            print(f"[PROTÉGÉ] {filename} -> fichier système ignoré")
            protected += 1
            logs.append({
                "requested_name": filename,
                "status": "protected",
                "source_path": str(source_file),
                "destination_path": str(destination_file),
                "detail": "Fichier protégé (liste source ou journal CSV).",
            })
            continue

        # Vérification dossier cible
        if destination_file.exists():
            print(f"[DÉJÀ PRÉSENT] {filename} -> ignoré")
            skipped += 1
            logs.append({
                "requested_name": filename,
                "status": "already_exists",
                "source_path": str(source_file),
                "destination_path": str(destination_file),
                "detail": "Le fichier existe déjà dans le dossier destination.",
            })
            continue

        # Déplacement réel ou simulé
        try:
            if dry_run:
                print(f"[TEST] {source_file} -> {destination_file}")
                simulated += 1
                logs.append({
                    "requested_name": filename,
                    "status": "dry_run",
                    "source_path": str(source_file),
                    "destination_path": str(destination_file),
                    "detail": "Simulation uniquement, aucun déplacement effectué.",
                })
            else:
                shutil.move(str(source_file), str(destination_file))
                print(f"[DÉPLACÉ] {source_file} -> {destination_file}")
                moved += 1
                logs.append({
                    "requested_name": filename,
                    "status": "moved",
                    "source_path": str(source_file),
                    "destination_path": str(destination_file),
                    "detail": "Déplacement effectué avec succès.",
                })

        except Exception as e:
            print(f"[ERREUR] {filename} -> {e}")
            errors += 1
            logs.append({
                "requested_name": filename,
                "status": "error",
                "source_path": str(source_file),
                "destination_path": str(destination_file),
                "detail": str(e),
            })

    print("\nRésumé :")
    print(f"  Déplacés          : {moved}")
    print(f"  Simulés (test)    : {simulated}")
    print(f"  Absents           : {missing}")
    print(f"  Ambigus           : {ambiguous}")
    print(f"  Ignorés           : {skipped}")
    print(f"  Protégés          : {protected}")
    print(f"  Erreurs           : {errors}")

    return logs


def main():
    print("=== Déplacement de fichiers à partir d'une liste ===\n")

    try:
        file_list_path = ask_file_path("Fichier texte contenant la liste des fichiers : ")
        source_dir = ask_existing_directory("Dossier source : ")
        destination_dir = ask_destination_directory("Dossier destination : ")

        recursive = ask_yes_no("Chercher aussi dans les sous-dossiers ? (o/n) : ")
        dry_run = ask_yes_no("Faire un test sans déplacer réellement les fichiers ? (o/n) : ")
        log_path = ask_log_file(destination_dir)

        print("\nLancement...\n")
        logs = move_files(
            file_list_path=file_list_path,
            source_dir=source_dir,
            destination_dir=destination_dir,
            recursive=recursive,
            dry_run=dry_run,
            exclude={file_list_path.resolve(), log_path.resolve()},
        )

        write_log_csv(log_path, logs)
        print(f"\nJournal CSV enregistré dans : {log_path}")

    except KeyboardInterrupt:
        print("\nOpération annulée par l'utilisateur.")
        sys.exit(1)
    except Exception as e:
        print(f"\nErreur : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()