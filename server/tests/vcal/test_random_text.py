import logging
import random
import os
from pathlib import Path

from vcal.random_text import OptionsSource, TextFileOptionsSource, select_text

def write_file(path: Path, lines):
    os.makedirs(path.parent, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_file(path: Path):
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def test_returns_default_when_above_threshold(tmp_path, monkeypatch):
    text_choices_file_name = "choices.txt"
    previously_chosen = tmp_path / "random_text_selection_history" / "choices_history.txt"

    write_file(tmp_path / text_choices_file_name, ["A", "B", "C"])

    monkeypatch.setattr(random, "random", lambda: 0.6)

    options_source = TextFileOptionsSource(file_name=text_choices_file_name, resources_directory=str(tmp_path))

    result = select_text(
        default_text="DEFAULT",
        threshold=0.3,
        options_source=options_source,
        choice_history_dir=str(tmp_path / "random_text_selection_history"),
    )

    assert result == "DEFAULT"
    assert not previously_chosen.exists()


def test_selects_and_appends_when_below_threshold(tmp_path, monkeypatch):
    text_choices_file_name = "choices.txt"
    previously_chosen = tmp_path / "random_text_selection_history" / "choices_history.txt"

    write_file(tmp_path / text_choices_file_name, ["A", "B", "C"])

    monkeypatch.setattr(random, "random", lambda: 0.1)
    # Always pick the first in the sequence, which should be "A"
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    options_source = TextFileOptionsSource(file_name=text_choices_file_name, resources_directory=str(tmp_path))

    result = select_text(
        default_text="DEFAULT",
        threshold=0.3,
        options_source=options_source,
        choice_history_dir=str(tmp_path / "random_text_selection_history"),
    )

    assert result == "A"
    assert read_file(previously_chosen) == ["A"]


def test_excludes_previously_chosen(tmp_path, monkeypatch):
    text_choices_file_name = "choices.txt"
    previously_chosen = tmp_path / "random_text_selection_history" / "choices_history.txt"

    write_file(tmp_path / text_choices_file_name, ["A", "B", "C"])
    write_file(previously_chosen, ["A"])

    monkeypatch.setattr(random, "random", lambda: 0.2)
    # Always pick the first in the sequence, which should be "B" after "A" is excluded
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    options_source = TextFileOptionsSource(file_name=text_choices_file_name, resources_directory=str(tmp_path))

    result = select_text(
        default_text="DEFAULT",
        threshold=0.3,
        options_source=options_source,
        choice_history_dir=str(tmp_path / "random_text_selection_history")
    )

    assert result == "B"
    assert "A" in read_file(previously_chosen)  # still there
    assert len(read_file(previously_chosen)) == 2


def test_resets_when_all_used(tmp_path, monkeypatch):
    text_choices_file_name = "choices.txt"
    previously_chosen = tmp_path / "random_text_selection_history" / "choices_history.txt"

    write_file(tmp_path / text_choices_file_name, ["A", "B"])
    write_file(previously_chosen, ["A", "B"])

    monkeypatch.setattr(random, "random", lambda: 0.2)
    # Always pick the first in the sequence, which should be "A" after reset
    monkeypatch.setattr(random, "choice", lambda seq: "A")

    options_source = TextFileOptionsSource(file_name=text_choices_file_name, resources_directory=str(tmp_path))

    result = select_text(
        default_text="DEFAULT",
        threshold=0.3,
        options_source=options_source,
        choice_history_dir=str(tmp_path / "random_text_selection_history")
    )

    assert result == "A"
    assert read_file(previously_chosen) == ["A"]  # reset then append


def test_multiset_behavior(tmp_path, monkeypatch):
    text_choices_file_name = "choices.txt"
    previously_chosen = tmp_path / "random_text_selection_history" / "choices_history.txt"

    write_file(tmp_path / text_choices_file_name, ["A", "A", "B"])
    write_file(previously_chosen, ["A"])

    monkeypatch.setattr(random, "random", lambda: 0.2)

    # Capture the sequence passed to random.choice
    captured = {}

    def fake_choice(seq):
        captured["seq"] = list(seq)
        return seq[0]

    monkeypatch.setattr(random, "choice", fake_choice)

    options_source = TextFileOptionsSource(file_name=text_choices_file_name, resources_directory=str(tmp_path))

    select_text(
        default_text="DEFAULT",
        threshold=0.3,
        options_source=options_source,
        choice_history_dir=str(tmp_path / "random_text_selection_history")
    )

    # Remaining should be ["A", "B"] (one A removed)
    assert sorted(captured["seq"]) == ["A", "B"]


def test_missing_previously_chosen_file(tmp_path, monkeypatch):
    text_choices_file_name = "choices.txt"
    previously_chosen = tmp_path / "random_text_selection_history" / "choices_history.txt"

    write_file(tmp_path / text_choices_file_name, ["X"])

    monkeypatch.setattr(random, "random", lambda: 0.2)
    monkeypatch.setattr(random, "choice", lambda seq: "X")

    options_source = TextFileOptionsSource(file_name=text_choices_file_name, resources_directory=str(tmp_path))

    result = select_text(
        default_text="DEFAULT",
        threshold=0.3,
        options_source=options_source,
        choice_history_dir=str(tmp_path / "random_text_selection_history")
    )

    assert result == "X"
    assert read_file(previously_chosen) == ["X"]