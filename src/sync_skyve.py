from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import httpx
import msgspec


API_URL = "https://skyve-mod.com/v2/api/CompatibilityData"
CSV_PATH = Path("ModsData.csv")
CODE_PACKAGE_TYPES = {0, 9, 10}
BROKEN_STABILITIES = {4, 5, 10}
CAUTION_STABILITIES = {9, 11, 13}
# CAUTION_SAVEGAME_EFFECTS = {3}
# CAUTION_STATUS_TYPES = {7, 8, 9}
# CAUTION_INTERACTION_TYPES = {3}
TAG_ORDER = ("ALPHA", "BETA", "EXP", "RC", "BROKEN")
FIELDNAMES = (
    "ModName",
    "ModId",
    "Beta",
    "Warning",
    "Badge",
    "Srcs",
    "BuiltIn",
    "Style",
    "ParadoxId",
)

BRACKET_RE = re.compile(r"\[([^\]]+)\]")
NAME_TAGS = {
    "ALPHA": "ALPHA",
    "BETA": "BETA",
    "EXP": "EXP",
    "EXPERIMENTAL": "EXP",
    "UNSTABLE": "EXP",
    "RC": "RC",
    "RELEASE CANDIDATE": "RC",
    "BROKEN": "BROKEN",
}


class PackageStatus(msgspec.Struct, omit_defaults=True):
    type: int


class PackageInteraction(msgspec.Struct, omit_defaults=True):
    type: int


class CompatibilityPackage(msgspec.Struct, omit_defaults=True):
    id: int
    name: str | None = None
    stability: int = 0
    savegameEffect: int = 0
    type: int = 0
    statuses: list[PackageStatus] | None = None
    interactions: list[PackageInteraction] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync Skyve compatibility data into ModsData.csv."
    )
    parser.add_argument("api_key", help="Skyve API key")
    parser.add_argument(
        "--input-json",
        type=Path,
        help="Read Skyve response from a local JSON file instead of calling the API.",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=CSV_PATH,
        help="CSV file to update. Defaults to ModsData.csv.",
    )
    return parser.parse_args()


def fetch_packages(api_key: str) -> list[CompatibilityPackage]:
    response = httpx.get(
        API_URL,
        headers={"USER_ID": "", "API_KEY": api_key},
        timeout=60,
        follow_redirects=True,
    )
    response.raise_for_status()
    return msgspec.json.decode(response.content, type=list[CompatibilityPackage])


def load_packages_from_file(path: Path) -> list[CompatibilityPackage]:
    return msgspec.json.decode(path.read_bytes(), type=list[CompatibilityPackage])


def normalize_name_tag(value: str) -> str | None:
    return NAME_TAGS.get(" ".join(value.strip().upper().split()))


def package_srcs(package: CompatibilityPackage) -> str:
    tags: set[str] = set()

    for match in BRACKET_RE.finditer(package.name or ""):
        tag = normalize_name_tag(match.group(1))
        if tag is not None:
            tags.add(tag)

    if package.stability in BROKEN_STABILITIES:
        tags.add("BROKEN")

    if any(status.type == 5 for status in package.statuses or ()):
        tags.add("BETA")

    return ";".join(tag for tag in TAG_ORDER if tag in tags)


def package_warning(package: CompatibilityPackage) -> bool:
    return (
        package.stability in CAUTION_STABILITIES
        # or package.savegameEffect in CAUTION_SAVEGAME_EFFECTS
        # or any(status.type in CAUTION_STATUS_TYPES for status in package.statuses or ())
        # or any(
        #     interaction.type in CAUTION_INTERACTION_TYPES
        #     for interaction in package.interactions or ()
        # )
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = [name for name in FIELDNAMES if name not in (reader.fieldnames or ())]
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
        return [
            {field: row.get(field, "") or "" for field in FIELDNAMES}
            for row in reader
        ]


def write_csv_rows(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
            lineterminator="\r\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_package_index(
    packages: Iterable[CompatibilityPackage],
) -> dict[str, CompatibilityPackage]:
    return {str(package.id): package for package in packages}


def sync_rows(
    rows: list[dict[str, str]],
    packages: list[CompatibilityPackage],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    by_paradox_id = build_package_index(packages)
    seen_ids = {row["ParadoxId"].strip() for row in rows if row["ParadoxId"].strip()}
    updated_rows = 0
    warning_rows = 0
    skipped_empty_name = 0
    added_rows = 0

    for row in rows:
        paradox_id = row["ParadoxId"].strip()
        package = by_paradox_id.get(paradox_id)
        if package is None:
            continue

        name = (package.name or "").strip()
        if name:
            row["ModName"] = name
        row["Srcs"] = package_srcs(package)
        row["Warning"] = "TRUE" if package_warning(package) else ""
        if row["Warning"]:
            warning_rows += 1
        updated_rows += 1

    for package in packages:
        paradox_id = str(package.id)
        if paradox_id in seen_ids or package.type not in CODE_PACKAGE_TYPES:
            continue

        name = (package.name or "").strip()
        if not name:
            skipped_empty_name += 1
            continue

        rows.append(
            {
                "ModName": name,
                "ModId": "",
                "Beta": "",
                "Warning": "TRUE" if package_warning(package) else "",
                "Badge": "",
                "Srcs": package_srcs(package),
                "BuiltIn": "",
                "Style": "",
                "ParadoxId": paradox_id,
            }
        )
        if rows[-1]["Warning"]:
            warning_rows += 1
        seen_ids.add(paradox_id)
        added_rows += 1

    return rows, {
        "updated": updated_rows,
        "added": added_rows,
        "warning": warning_rows,
        "skipped_empty_name": skipped_empty_name,
    }


def main() -> int:
    args = parse_args()

    packages = (
        load_packages_from_file(args.input_json)
        if args.input_json is not None
        else fetch_packages(args.api_key)
    )
    rows = read_csv_rows(args.csv_path)
    synced_rows, stats = sync_rows(rows, packages)
    write_csv_rows(args.csv_path, synced_rows)

    print(
        f"Synced {args.csv_path}: "
        f"{stats['updated']} updated, "
        f"{stats['added']} added, "
        f"{stats['warning']} warning, "
        f"{stats['skipped_empty_name']} skipped with empty name."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
