from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path

from .source import digest, normalize, source_body

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
GOLDEN_SCHEMA = "golden-html/v3"
FORBIDDEN_MARKERS = ("Clavis Magistri", "Guida Magistri", "Appendix Probationum")


def attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {key: value or "" for key, value in attrs}


def has_class(attrs: dict[str, str], class_name: str) -> bool:
    return class_name in attrs.get("class", "").split()


class SourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_source = False
        self.in_paragraph = False
        self.depth = 0
        self.current: list[str] = []
        self.paragraphs: list[str] = []
        self.source_ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = attrs_to_dict(attrs)
        if tag == "section" and attrs_dict.get("id") == "textus-auctoris":
            self.in_source = True
            self.depth = 1
            return
        if self.in_source:
            if tag not in VOID_TAGS:
                self.depth += 1
            if tag == "p" and has_class(attrs_dict, "source-text"):
                self.in_paragraph = True
                self.current = []
                self.source_ids.append(attrs_dict.get("id", ""))

    def handle_endtag(self, tag: str) -> None:
        if self.in_source and tag == "p" and self.in_paragraph:
            self.paragraphs.append(normalize("".join(self.current)))
            self.in_paragraph = False
        if self.in_source and tag not in VOID_TAGS:
            self.depth -= 1
            if self.depth <= 0:
                self.in_source = False

    def handle_data(self, data: str) -> None:
        if self.in_source and self.in_paragraph:
            self.current.append(data)


def html_source_paragraphs(html: str) -> list[str]:
    parser = SourceParser()
    parser.feed(html)
    return parser.paragraphs


class SnapshotParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.source = SourceParser()
        self.in_dictionary_row = False
        self.current_cell: str | None = None
        self.current_row: dict[str, str] = {}
        self.dictionary: list[dict[str, str]] = []
        self.detail_kind: str | None = None
        self.detail_depth = 0
        self.detail_parts: list[str] = []
        self.forcellini_cards: list[str] = []
        self.memory_cards: list[str] = []
        self.new_words: list[dict[str, str]] = []
        self.current_new_word: dict[str, str] | None = None
        self.new_word_depth = 0
        self.new_word_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.source.handle_starttag(tag, attrs)
        attrs_dict = attrs_to_dict(attrs)
        if self.current_new_word and tag not in VOID_TAGS:
            self.new_word_depth += 1
        if tag == "span" and has_class(attrs_dict, "new-word"):
            self.current_new_word = {
                "text": "",
                "lemma": attrs_dict.get("data-lemma") or "",
                "gloss": attrs_dict.get("data-gloss") or "",
            }
            self.new_word_depth = 1
            self.new_word_parts = []
        if tag == "tr":
            self.in_dictionary_row = True
            self.current_row = {}
        if self.in_dictionary_row and tag == "td":
            self.current_cell = attrs_dict.get("data-label") or ""
            self.current_row[self.current_cell] = ""
        if tag == "details" and self.detail_kind is None:
            if has_class(attrs_dict, "forcellini-card"):
                self.detail_kind = "forcellini"
                self.detail_depth = 1
                self.detail_parts = []
            elif has_class(attrs_dict, "memory-card"):
                self.detail_kind = "memory"
                self.detail_depth = 1
                self.detail_parts = []
        elif self.detail_kind and tag not in VOID_TAGS:
            self.detail_depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.source.handle_endtag(tag)
        if self.current_new_word and tag not in VOID_TAGS:
            self.new_word_depth -= 1
            if self.new_word_depth <= 0:
                self.current_new_word["text"] = normalize("".join(self.new_word_parts))
                self.new_words.append(dict(self.current_new_word))
                self.current_new_word = None
                self.new_word_parts = []
        if self.current_cell and tag == "td":
            self.current_row[self.current_cell] = normalize(self.current_row[self.current_cell])
            self.current_cell = None
        if self.in_dictionary_row and tag == "tr":
            if self.current_row:
                self.dictionary.append(dict(self.current_row))
            self.in_dictionary_row = False
            self.current_row = {}
        if self.detail_kind and tag not in VOID_TAGS:
            self.detail_depth -= 1
            if self.detail_depth <= 0:
                text = normalize(" ".join(self.detail_parts))
                if self.detail_kind == "forcellini":
                    self.forcellini_cards.append(text)
                else:
                    self.memory_cards.append(text)
                self.detail_kind = None
                self.detail_parts = []

    def handle_data(self, data: str) -> None:
        self.source.handle_data(data)
        if self.current_new_word:
            self.new_word_parts.append(data)
        if self.current_cell:
            self.current_row[self.current_cell] += data
        if self.detail_kind:
            self.detail_parts.append(data)


def html_snapshot(html: str) -> dict:
    parser = SnapshotParser()
    parser.feed(html)
    source = parser.source.paragraphs
    forbidden_markers = [marker for marker in FORBIDDEN_MARKERS if marker in html]
    return {
        "source_digest": digest(source),
        "source_paragraphs": source,
        "dictionary": parser.dictionary,
        "forcellini_cards": parser.forcellini_cards,
        "memory_cards": parser.memory_cards,
        "new_words": parser.new_words,
        "source_anchor_ids": parser.source.source_ids,
        "forbidden_markers": forbidden_markers,
        "counts": {
            "source_paragraphs": len(source),
            "source_anchor_ids": len(parser.source.source_ids),
            "new_words": len(parser.new_words),
            "dictionary_rows": len(parser.dictionary),
            "forcellini_cards": len(parser.forcellini_cards),
            "memory_cards": len(parser.memory_cards),
        },
    }


def json_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


def data_counts(expected: list[str], cards: list[dict], memory_cards: list[dict]) -> dict[str, int]:
    return {
        "source_paragraphs": len(expected),
        "source_anchor_ids": len(expected),
        "new_words": len(cards),
        "dictionary_rows": len(cards),
        "forcellini_cards": len(cards),
        "memory_cards": len(memory_cards),
    }


def data_hashes(lessons: list[dict], cards: list[dict], memory_cards: list[dict]) -> dict[str, str]:
    return {
        "lessons": json_digest(lessons),
        "forcellini_lock": json_digest(cards),
        "memory_cards": json_digest(memory_cards),
    }


def verify_project(root: Path) -> dict:
    project = json.loads((root / "data/project.json").read_text(encoding="utf-8"))
    expected = source_body(root / project["source_docx"], int(project["docx_start_paragraph"]))
    html_path = root / project["output_html"]
    html = html_path.read_text(encoding="utf-8")
    actual_snapshot = html_snapshot(html)
    actual = actual_snapshot["source_paragraphs"]
    cards = json.loads((root / project["forcellini_lock"]).read_text(encoding="utf-8"))["cards"]
    lessons = json.loads((root / project["lessons"]).read_text(encoding="utf-8"))["lessons"]
    memory_cards = json.loads((root / project["memory_cards"]).read_text(encoding="utf-8"))["cards"]
    counts = actual_snapshot["counts"]
    golden = json.loads((root / project["golden"]).read_text(encoding="utf-8"))
    failures = []
    if actual != expected:
        failures.append({"kind": "source_text_mismatch"})
    expected_ids = [f"source-{index}" for index in range(1, len(expected) + 1)]
    if actual_snapshot["source_anchor_ids"] != expected_ids:
        failures.append(
            {
                "kind": "source_anchor_ids",
                "expected": expected_ids,
                "actual": actual_snapshot["source_anchor_ids"],
            }
        )
    if actual_snapshot["forbidden_markers"]:
        failures.append({"kind": "forbidden_markers", "markers": actual_snapshot["forbidden_markers"]})
    if len(lessons) != len(expected):
        failures.append({"kind": "lesson_count", "expected": len(expected), "actual": len(lessons)})
    for key, expected_value in data_counts(expected, cards, memory_cards).items():
        if counts[key] != expected_value:
            failures.append({"kind": "data_count", "key": key, "expected": expected_value, "actual": counts[key]})
    expected_counts = golden["counts"]
    for key, expected_value in expected_counts.items():
        if counts[key] != expected_value:
            failures.append({"kind": "count", "key": key, "expected": expected_value, "actual": counts[key]})
    if len(cards) != expected_counts["forcellini_cards"]:
        failures.append({"kind": "forcellini_lock_count", "expected": expected_counts["forcellini_cards"], "actual": len(cards)})
    if golden.get("schema_version") != GOLDEN_SCHEMA:
        failures.append({"kind": "golden_schema_version", "expected": GOLDEN_SCHEMA})
    actual_hashes = {
        "dictionary": json_digest(actual_snapshot["dictionary"]),
        "forcellini_cards": json_digest(actual_snapshot["forcellini_cards"]),
        "memory_cards": json_digest(actual_snapshot["memory_cards"]),
        "new_words": json_digest(actual_snapshot["new_words"]),
    }
    actual_data_hashes = data_hashes(lessons, cards, memory_cards)
    if actual_snapshot["source_digest"] != golden["source_digest"]:
        failures.append({"kind": "golden_regression", "key": "source_digest"})
    if counts != golden["counts"]:
        failures.append({"kind": "golden_regression", "key": "counts"})
    for key, actual_hash in actual_hashes.items():
        if actual_hash != golden["hashes"].get(key):
            failures.append({"kind": "golden_regression", "key": key})
    for key, actual_hash in actual_data_hashes.items():
        if actual_hash != golden["data_hashes"].get(key):
            failures.append({"kind": "golden_regression", "key": key})
    report = {
        "schema_version": "slim-html-verify/v1",
        "html": str(html_path),
        "source_digest_expected": digest(expected),
        "source_digest_actual": digest(actual),
        "counts": counts,
        "forbidden_markers": actual_snapshot["forbidden_markers"],
        "data_hashes": actual_data_hashes,
        "golden_checked": True,
        "failures": failures,
    }
    return report
