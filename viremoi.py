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


def build_index(
    source_dir: Path, recursive: bool
) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    """
    Construit deux index sur le dossier source :
    - by_name : {nom_complet -> [chemins]}   utilisé quand une extension est précisée
    - by_stem : {nom_sans_extension -> [chemins]}  utilisé sinon
    """
    by_name: dict[str, list[Path]] = {}
    by_stem: dict[str, list[Path]] = {}

    iterator = source_dir.rglob("*") if recursive else source_dir.iterdir()
    for path in iterator:
        if path.is_file():
            by_name.setdefault(path.name, []).append(path)
            by_stem.setdefault(path.stem, []).append(path)

    return by_name, by_stem


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


def _apply_move(
    source_file: Path,
    destination_file: Path,
    requested_name: str,
    dry_run: bool,
    exclude: set[Path] | None,
) -> tuple[dict, str]:
    """
    Tente de déplacer source_file vers destination_file.
    Retourne (log_dict, outcome) où outcome est le nom du compteur à incrémenter.
    """
    if exclude and source_file.resolve() in exclude:
        print(f"[PROTÉGÉ] {source_file.name} -> fichier système ignoré")
        return {
            "requested_name": requested_name,
            "status": "protected",
            "source_path": str(source_file),
            "destination_path": str(destination_file),
            "detail": "Fichier protégé (liste source ou journal CSV).",
        }, "protected"

    if destination_file.exists():
        print(f"[DÉJÀ PRÉSENT] {source_file.name} -> ignoré")
        return {
            "requested_name": requested_name,
            "status": "already_exists",
            "source_path": str(source_file),
            "destination_path": str(destination_file),
            "detail": "Le fichier existe déjà dans le dossier destination.",
        }, "skipped"

    try:
        if dry_run:
            print(f"[TEST] {source_file} -> {destination_file}")
            return {
                "requested_name": requested_name,
                "status": "dry_run",
                "source_path": str(source_file),
                "destination_path": str(destination_file),
                "detail": "Simulation uniquement, aucun déplacement effectué.",
            }, "simulated"
        else:
            shutil.move(str(source_file), str(destination_file))
            print(f"[DÉPLACÉ] {source_file} -> {destination_file}")
            return {
                "requested_name": requested_name,
                "status": "moved",
                "source_path": str(source_file),
                "destination_path": str(destination_file),
                "detail": "Déplacement effectué avec succès.",
            }, "moved"

    except Exception as e:
        print(f"[ERREUR] {source_file.name} -> {e}")
        return {
            "requested_name": requested_name,
            "status": "error",
            "source_path": str(source_file),
            "destination_path": str(destination_file),
            "detail": str(e),
        }, "errors"


def resolve_ambiguous(
    pending: list[tuple[str, list[Path]]],
    destination_dir: Path,
    dry_run: bool,
    exclude: set[Path] | None,
) -> tuple[list[dict], dict[str, int]]:
    """
    Résout interactivement les entrées ambiguës collectées pendant le traitement.
    Retourne (logs, counters).
    """
    print(f"\n{'='*60}")
    print(f"  {len(pending)} entrée(s) ambiguë(s) à résoudre\n")
    for i, (filename, matches) in enumerate(pending, 1):
        print(f"  {i}. {filename}")
        for j, p in enumerate(matches, 1):
            print(f"       {j}. {p}")

    print(f"\n  (t) Tout accepter — déplacer tous les fichiers correspondants")
    print(f"  (r) Refuser tout  — ignorer toutes les entrées ambiguës")
    print(f"  (c) Cas par cas   — choisir fichier par fichier")
    while True:
        choice = input("\nChoix : ").strip().lower()
        if choice in {"t", "tout"}:
            mode = "all"
            break
        if choice in {"r", "refuser"}:
            mode = "none"
            break
        if choice in {"c", "cas"}:
            mode = "one_by_one"
            break
        print("Réponds par t / r / c.")

    logs: list[dict] = []
    counters: dict[str, int] = {
        "moved": 0, "simulated": 0, "skipped": 0,
        "ambiguous": 0, "protected": 0, "errors": 0,
    }

    for filename, matches in pending:
        if mode == "none":
            counters["ambiguous"] += 1
            logs.append({
                "requested_name": filename,
                "status": "ambiguous",
                "source_path": " | ".join(str(p) for p in matches),
                "destination_path": "",
                "detail": "Refusé par l'utilisateur.",
            })
            continue

        if mode == "all":
            selected = matches

        else:  # cas par cas
            print(f"\n[AMBIGU] {filename}")
            for j, p in enumerate(matches, 1):
                print(f"  {j}. {p}")
            raw = input("  Numéros à déplacer (séparés par virgule, 0 pour ignorer) : ").strip()

            if not raw or raw == "0":
                counters["ambiguous"] += 1
                logs.append({
                    "requested_name": filename,
                    "status": "ambiguous",
                    "source_path": " | ".join(str(p) for p in matches),
                    "destination_path": "",
                    "detail": "Ignoré par l'utilisateur.",
                })
                continue

            try:
                indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip()]
                selected = [matches[i] for i in indices if 0 <= i < len(matches)]
                if not selected:
                    raise ValueError("Aucun indice valide.")
            except (ValueError, IndexError):
                print("  Sélection invalide, entrée ignorée.")
                counters["ambiguous"] += 1
                logs.append({
                    "requested_name": filename,
                    "status": "ambiguous",
                    "source_path": " | ".join(str(p) for p in matches),
                    "destination_path": "",
                    "detail": "Sélection invalide, ignorée.",
                })
                continue

        for source_file in selected:
            destination_file = destination_dir / source_file.name
            log, outcome = _apply_move(source_file, destination_file, filename, dry_run, exclude)
            logs.append(log)
            counters[outcome] += 1

    return logs, counters


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

    by_name, by_stem = build_index(source_dir, recursive)

    counters: dict[str, int] = {
        "moved": 0, "simulated": 0, "missing": 0, "skipped": 0,
        "ambiguous": 0, "protected": 0, "errors": 0,
    }

    pending_ambiguous: list[tuple[str, list[Path]]] = []

    for filename in filenames:
        has_extension = Path(filename).suffix != ""

        matches = by_name.get(filename, []) if has_extension else by_stem.get(filename, [])

        if len(matches) == 0:
            print(f"[ABSENT] {filename}")
            counters["missing"] += 1
            logs.append({
                "requested_name": filename,
                "status": "missing",
                "source_path": "",
                "destination_path": str(destination_dir / filename),
                "detail": "Aucun fichier trouvé dans la source.",
            })
            continue

        if len(matches) > 1:
            print(f"[AMBIGU] {filename} -> {', '.join(p.name for p in matches)}")
            pending_ambiguous.append((filename, matches))
            continue

        source_file = matches[0]
        destination_file = destination_dir / source_file.name
        log, outcome = _apply_move(source_file, destination_file, filename, dry_run, exclude)
        logs.append(log)
        counters[outcome] += 1

    # Résolution interactive des ambigus
    if pending_ambiguous:
        extra_logs, extra_counters = resolve_ambiguous(
            pending_ambiguous, destination_dir, dry_run, exclude
        )
        logs.extend(extra_logs)
        for key, val in extra_counters.items():
            counters[key] = counters.get(key, 0) + val

    print("\nRésumé :")
    print(f"  Déplacés          : {counters['moved']}")
    print(f"  Simulés (test)    : {counters['simulated']}")
    print(f"  Absents           : {counters['missing']}")
    print(f"  Ambigus           : {counters['ambiguous']}")
    print(f"  Ignorés           : {counters['skipped']}")
    print(f"  Protégés          : {counters['protected']}")
    print(f"  Erreurs           : {counters['errors']}")

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
