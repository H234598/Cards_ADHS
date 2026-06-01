from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import genanki
import markdown
import yaml


CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  font-size: 20px;
  line-height: 1.45;
  text-align: left;
  color: #111;
  background: #fafafa;
  padding: 1rem;
}
.card h1, .card h2, .card h3 { line-height: 1.2; }
.card code { font-size: 0.9em; }
.card blockquote {
  border-left: 4px solid #ccc;
  margin-left: 0;
  padding-left: 1rem;
}
.source {
  color: #555;
  font-size: 0.75em;
  margin-top: 1.25rem;
}
.tagline {
  color: #777;
  font-size: 0.72em;
  margin-bottom: 0.75rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
"""

BASIC_MODEL = genanki.Model(
    230601001,
    "Cards_ADHS Basic",
    fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Source"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": '<div class="tagline">ADHS Lernkarte</div>{{Front}}',
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}{{#Source}}<div class="source"><b>Quelle:</b> {{Source}}</div>{{/Source}}',
        }
    ],
    css=CSS,
)

REVERSE_MODEL = genanki.Model(
    230601002,
    "Cards_ADHS Basic + Reverse",
    fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Source"}],
    templates=[
        {
            "name": "Forward",
            "qfmt": '<div class="tagline">ADHS Lernkarte</div>{{Front}}',
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}{{#Source}}<div class="source"><b>Quelle:</b> {{Source}}</div>{{/Source}}',
        },
        {
            "name": "Reverse",
            "qfmt": '<div class="tagline">ADHS Lernkarte · Rückseite</div>{{Back}}',
            "afmt": '{{FrontSide}}<hr id="answer">{{Front}}{{#Source}}<div class="source"><b>Quelle:</b> {{Source}}</div>{{/Source}}',
        },
    ],
    css=CSS,
)

CLOZE_MODEL = genanki.Model(
    230601003,
    "Cards_ADHS Cloze",
    fields=[{"name": "Text"}, {"name": "Extra"}, {"name": "Source"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": '<div class="tagline">ADHS Cloze</div>{{cloze:Text}}',
            "afmt": '{{cloze:Text}}{{#Extra}}<hr id="answer">{{Extra}}{{/Extra}}{{#Source}}<div class="source"><b>Quelle:</b> {{Source}}</div>{{/Source}}',
        }
    ],
    css=CSS,
    model_type=genanki.Model.CLOZE,
)


@dataclass(frozen=True)
class Card:
    deck: str
    card_type: str
    card_id: str
    source_path: Path
    source: str
    tags: tuple[str, ...]
    front: str = ""
    back: str = ""
    text: str = ""
    extra: str = ""


class CardError(ValueError):
    pass


def stable_id(value: str) -> int:
    """Return a deterministic positive integer accepted by Anki/genanki."""
    raw = int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:8], 16)
    return 100_000_000 + (raw % 1_900_000_000)


def slugify(value: str) -> str:
    value = value.replace("::", "_")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._-")
    return value[:96] or "deck"


def md_to_html(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return markdown.markdown(value.strip(), extensions=["extra", "sane_lists"])


def clean_tag(value: str) -> str:
    value = str(value).strip().replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_:\-/]+", "", value)
    return value


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CardError(f"{path}: YAML konnte nicht gelesen werden: {exc}") from exc
    if not isinstance(data, dict):
        raise CardError(f"{path}: Die Datei muss ein YAML-Objekt enthalten.")
    return data


def iter_card_files(cards_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.yml", "*.yaml"):
        files.extend(cards_dir.rglob(pattern))
    return sorted(path for path in files if path.is_file())


def normalize_cards(path: Path, require_source: bool = True) -> list[Card]:
    data = load_yaml(path)
    if "decks" in data:
        decks_raw = data["decks"]
        if not isinstance(decks_raw, list):
            raise CardError(f"{path}: 'decks' muss eine Liste sein.")
    else:
        decks_raw = [data]

    normalized: list[Card] = []
    for deck_index, deck_data in enumerate(decks_raw, start=1):
        if not isinstance(deck_data, dict):
            raise CardError(f"{path}: Deck #{deck_index} ist kein YAML-Objekt.")

        deck_name = deck_data.get("deck") or deck_data.get("name")
        if not deck_name:
            raise CardError(f"{path}: Deck #{deck_index} braucht 'deck:' oder 'name:'.")

        deck_tags = [clean_tag(tag) for tag in as_list(deck_data.get("tags")) if str(tag).strip()]
        deck_source = deck_data.get("source") or data.get("source") or ""
        cards_raw = deck_data.get("cards")
        if not isinstance(cards_raw, list) or not cards_raw:
            raise CardError(f"{path}: Deck '{deck_name}' braucht eine nicht-leere 'cards:'-Liste.")

        for card_index, card_data in enumerate(cards_raw, start=1):
            if not isinstance(card_data, dict):
                raise CardError(f"{path}: Karte #{card_index} in '{deck_name}' ist kein YAML-Objekt.")

            card_type = str(card_data.get("type", "basic")).lower().strip()
            if card_type not in {"basic", "reverse", "cloze"}:
                raise CardError(f"{path}: Karte #{card_index}: type muss basic, reverse oder cloze sein.")

            card_id = str(card_data.get("id") or f"{path.stem}-{deck_index}-{card_index}").strip()
            source = str(card_data.get("source") or deck_source or "").strip()
            if require_source and not source:
                raise CardError(
                    f"{path}: Karte '{card_id}' hat keine Quelle. Ergänze 'source:' oder nutze --allow-unsourced."
                )

            card_tags = [clean_tag(tag) for tag in as_list(card_data.get("tags")) if str(tag).strip()]
            tags = tuple(tag for tag in [*deck_tags, *card_tags, f"source::{slugify(path.stem)}"] if tag)

            if card_type in {"basic", "reverse"}:
                front = card_data.get("front") or card_data.get("question")
                back = card_data.get("back") or card_data.get("answer")
                if not front or not back:
                    raise CardError(f"{path}: Karte '{card_id}' braucht front/back oder question/answer.")
                normalized.append(
                    Card(
                        deck=str(deck_name),
                        card_type=card_type,
                        card_id=card_id,
                        source_path=path,
                        source=source,
                        tags=tags,
                        front=md_to_html(front),
                        back=md_to_html(back),
                    )
                )
            else:
                text = card_data.get("text")
                if not text or "{{c" not in str(text):
                    raise CardError(f"{path}: Cloze-Karte '{card_id}' braucht text mit {{{{c1::...}}}}.")
                normalized.append(
                    Card(
                        deck=str(deck_name),
                        card_type=card_type,
                        card_id=card_id,
                        source_path=path,
                        source=source,
                        tags=tags,
                        text=md_to_html(text),
                        extra=md_to_html(card_data.get("extra")),
                    )
                )
    return normalized


def load_cards(cards_dir: Path, require_source: bool = True) -> list[Card]:
    if not cards_dir.exists():
        raise CardError(f"Kartenordner nicht gefunden: {cards_dir}")

    cards: list[Card] = []
    for path in iter_card_files(cards_dir):
        cards.extend(normalize_cards(path, require_source=require_source))

    if not cards:
        raise CardError(f"Keine .yml/.yaml-Karten in {cards_dir} gefunden.")

    seen: set[tuple[str, str]] = set()
    for card in cards:
        key = (card.deck, card.card_id)
        if key in seen:
            raise CardError(f"Doppelte Karten-ID im Deck '{card.deck}': {card.card_id}")
        seen.add(key)
    return cards


def note_from_card(card: Card) -> genanki.Note:
    guid = genanki.guid_for(card.deck, card.card_id)
    if card.card_type == "basic":
        return genanki.Note(
            model=BASIC_MODEL,
            fields=[card.front, card.back, card.source],
            tags=list(card.tags),
            guid=guid,
        )
    if card.card_type == "reverse":
        return genanki.Note(
            model=REVERSE_MODEL,
            fields=[card.front, card.back, card.source],
            tags=list(card.tags),
            guid=guid,
        )
    return genanki.Note(
        model=CLOZE_MODEL,
        fields=[card.text, card.extra, card.source],
        tags=list(card.tags),
        guid=guid,
    )


def build_decks(cards: Iterable[Card]) -> dict[str, genanki.Deck]:
    decks: dict[str, genanki.Deck] = {}
    for card in cards:
        deck = decks.setdefault(card.deck, genanki.Deck(stable_id(f"deck:{card.deck}"), card.deck))
        deck.add_note(note_from_card(card))
    return decks


def write_packages(decks: dict[str, genanki.Deck], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for deck_name, deck in sorted(decks.items(), key=lambda item: item[0].lower()):
        out_path = out_dir / f"{slugify(deck_name)}.apkg"
        genanki.Package(deck).write_to_file(str(out_path))
        written.append(out_path)

    all_path = out_dir / "Cards_ADHS_all_decks.apkg"
    genanki.Package(list(decks.values())).write_to_file(str(all_path))
    written.append(all_path)
    return written


def cmd_validate(args: argparse.Namespace) -> int:
    cards = load_cards(args.cards_dir, require_source=not args.allow_unsourced)
    decks = build_decks(cards)
    print(f"OK: {len(cards)} Karten in {len(decks)} Deck(s) validiert.")
    for deck_name in sorted(decks):
        count = sum(1 for card in cards if card.deck == deck_name)
        print(f"- {deck_name}: {count} Karte(n)")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    cards = load_cards(args.cards_dir, require_source=not args.allow_unsourced)
    decks = build_decks(cards)
    written = write_packages(decks, args.out_dir)
    print(f"OK: {len(cards)} Karten in {len(decks)} Deck(s) gebaut.")
    for path in written:
        print(path)
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Cards_ADHS Anki .apkg decks from YAML files.")
    subparsers = parser.add_subparsers(dest="command")

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--cards-dir", type=Path, default=Path("cards"), help="Ordner mit .yml/.yaml-Karten")
        subparser.add_argument("--allow-unsourced", action="store_true", help="Quellenprüfung deaktivieren")

    validate_parser = subparsers.add_parser("validate", help="Karten prüfen, ohne .apkg zu schreiben")
    add_common(validate_parser)
    validate_parser.set_defaults(func=cmd_validate)

    build_parser = subparsers.add_parser("build", help=".apkg-Dateien bauen")
    add_common(build_parser)
    build_parser.add_argument("--out-dir", type=Path, default=Path("dist"), help="Ausgabeordner")
    build_parser.set_defaults(func=cmd_build)

    parser.set_defaults(func=cmd_build, cards_dir=Path("cards"), out_dir=Path("dist"), allow_unsourced=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CardError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
