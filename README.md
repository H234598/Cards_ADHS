# Cards_ADHS

Wissenschaftlich gepflegte Anki-Karten zum Thema ADHS — mit CI-Pipeline, die aus YAML-Dateien automatisch `.apkg`-Decks erzeugt.

Dieses Repo ist bewusst schlicht: Karten rein, Pipeline läuft, APKG-Artefakt raus. Kein Foren-Orakel, keine Diagnose-Magie, keine Dopamin-Märchenmaschine.

## Was die Pipeline macht

Bei jedem Push, Pull Request oder manuellem Start über `workflow_dispatch`:

1. Python installieren
2. Builder installieren
3. Tests ausführen
4. Karten validieren
5. `.apkg`-Decks bauen
6. APKG-Ausgaben auf Existenz und Mindestgröße prüfen
7. APKG-Dateien unter `dist/` ins Repository zurückschreiben
8. Release `cards-adhs-latest` mit den APKG-Dateien erstellen oder aktualisieren
9. fertige Decks als GitHub-Actions-Artefakt hochladen

Erzeugt werden:

- ein `.apkg` pro Deck
- zusätzlich `Cards_ADHS_all_decks.apkg` mit allen Decks zusammen

Die Decks sind danach an zwei sichtbaren Stellen verfügbar:

- im Repository unter `dist/`
- unter `Releases` im Release `cards-adhs-latest`

## Automatisches Kartendesign

Die YAML-Dateien enthalten nur Inhalt. Markdown in `front`, `back`, `text` und `extra`
wird automatisch in HTML umgewandelt und vom Builder mit einem gemeinsamen Anki-Theme
gerendert. Dadurch bekommen neue Karten ohne zusätzliche HTML-Arbeit ein einheitliches
Layout mit Frage-/Antwortflächen, Quellenbereich, Listen-, Code-, Zitat- und Cloze-Styling.

## Ordnerstruktur

```text
Cards_ADHS/
├── .github/workflows/build-anki.yml
├── cards/
│   ├── 01_beginner_onboarding.yml
│   └── 02_neurobio.yml
├── src/cards_adhs_builder/
│   ├── __init__.py
│   └── build_decks.py
├── tests/
│   └── test_build_decks.py
├── pyproject.toml
└── README.md
```

## Kartenformat

Karten liegen als YAML unter `cards/`.

```yaml
deck: "ADHS::01 Beginner::Onboarding"
tags: [adhs, beginner]
source: "NICE Guideline NG87; Faraone et al. 2021."
cards:
  - id: adhs-definition
    type: basic
    front: |
      Was ist ADHS im Kern?
    back: |
      Eine neuroentwicklungsbezogene Störung mit anhaltender Unaufmerksamkeit
      und/oder Hyperaktivität-Impulsivität plus funktioneller Beeinträchtigung.
    tags: [diagnostik]
```

Unterstützte Kartentypen:

| Typ | Zweck | Pflichtfelder |
|---|---|---|
| `basic` | normale Frage/Antwort-Karte | `front`, `back` |
| `reverse` | Frage/Antwort plus Rückwärtskarte | `front`, `back` |
| `cloze` | Lückentextkarte | `text` mit `{{c1::...}}` |

## Wissenschaftliche Hygiene

Der Builder verlangt standardmäßig eine `source:`. Das ist Absicht.

Empfohlene Regeln:

- eine Karte = ein Lernziel
- keine Diagnosen aus Einzelscores ableiten
- keine Monokausal-Erklärungen wie „ADHS ist einfach Dopaminmangel“
- Quellen in jeder Datei oder Karte pflegen
- bei Autismus-/Parkinson-Querbezügen klar trennen: Überlappung, Differentialdiagnose, Komorbidität, Mechanismus

Für schnelle Notizen ohne Quelle gibt es zwar:

```bash
cards-adhs-build build --allow-unsourced
```

Für den Hauptbestand sollte das aber nicht benutzt werden. Wissenschaft ohne Quelle ist nur hübsch gekämmtes Bauchgefühl.

## Lokal bauen

```bash
git clone git@github.com:H234598/Cards_ADHS.git
cd Cards_ADHS
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
cards-adhs-build validate --cards-dir cards
cards-adhs-build build --cards-dir cards --out-dir dist
```

Die fertigen Decks liegen danach in `dist/`.

## GitHub Actions

Nach jedem passenden Push findest du die `.apkg`-Dateien unter:

`Actions` → letzter Workflow-Lauf → `Artifacts` → `Cards_ADHS_apkg`
