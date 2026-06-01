from __future__ import annotations

from pathlib import Path

from cards_adhs_builder.build_decks import (
    BASIC_MODEL,
    CLOZE_MODEL,
    REVERSE_MODEL,
    CardError,
    build_decks,
    load_cards,
    main,
    slugify,
)


def write_sample(path: Path) -> None:
    path.write_text(
        """
deck: "ADHS::Test"
source: "Testquelle"
cards:
  - id: one
    type: basic
    front: "Was ist ein Test?"
    back: "Eine prüfbare Probe."
  - id: two
    type: cloze
    text: "ADHS ist {{c1::nicht}} durch eine Einzelursache erklärt."
    extra: "Cloze-Test."
""".strip(),
        encoding="utf-8",
    )


def test_slugify_keeps_safe_filename() -> None:
    assert slugify("ADHS::01 Beginner::Onboarding") == "ADHS_01_Beginner_Onboarding"


def test_load_cards_and_build_decks(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    write_sample(cards_dir / "sample.yml")

    cards = load_cards(cards_dir)
    decks = build_decks(cards)

    assert len(cards) == 2
    assert list(decks) == ["ADHS::Test"]


def test_models_apply_pretty_theme_automatically() -> None:
    for model in (BASIC_MODEL, REVERSE_MODEL, CLOZE_MODEL):
        assert ".adhs-card" in model.css
        assert ".prompt" in model.css
        assert ".response" in model.css

    assert 'class="prompt"' in BASIC_MODEL.templates[0]["qfmt"]
    assert 'class="response"' in BASIC_MODEL.templates[0]["afmt"]
    assert 'class="cloze-extra"' in CLOZE_MODEL.templates[0]["afmt"]


def test_missing_source_fails(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    (cards_dir / "bad.yml").write_text(
        """
deck: "ADHS::Test"
cards:
  - id: no-source
    type: basic
    front: "Frage"
    back: "Antwort"
""".strip(),
        encoding="utf-8",
    )

    try:
        load_cards(cards_dir)
    except CardError as exc:
        assert "keine Quelle" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Missing source should fail")


def test_cli_build_writes_apkg(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    out_dir = tmp_path / "dist"
    cards_dir.mkdir()
    write_sample(cards_dir / "sample.yml")

    exit_code = main(["build", "--cards-dir", str(cards_dir), "--out-dir", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "ADHS_Test.apkg").exists()
    assert (out_dir / "Cards_ADHS_all_decks.apkg").exists()
