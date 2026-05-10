from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import json
import re
from pathlib import Path

from .source import digest, normalize, source_body


class SourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_source = False
        self.in_paragraph = False
        self.depth = 0
        self.current: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "section" and attrs_dict.get("id") == "textus-auctoris":
            self.in_source = True
            self.depth = 1
            return
        if self.in_source:
            self.depth += 1
            if tag == "p" and "source-text" in (attrs_dict.get("class") or ""):
                self.in_paragraph = True
                self.current = []

    def handle_endtag(self, tag: str) -> None:
        if self.in_source and tag == "p" and self.in_paragraph:
            self.paragraphs.append(normalize("".join(self.current)))
            self.in_paragraph = False
        if self.in_source:
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.source.handle_starttag(tag, attrs)
        attrs_dict = dict(attrs)
        class_attr = attrs_dict.get("class") or ""
        if tag == "span" and "new-word" in class_attr:
            self.new_words.append(
                {
                    "text": "",
                    "lemma": attrs_dict.get("data-lemma") or "",
                    "gloss": attrs_dict.get("data-gloss") or "",
                }
            )
        if tag == "tr":
            self.in_dictionary_row = True
            self.current_row = {}
        if self.in_dictionary_row and tag == "td":
            self.current_cell = attrs_dict.get("data-label") or ""
            self.current_row[self.current_cell] = ""
        if tag == "details" and self.detail_kind is None:
            if "forcellini-card" in class_attr:
                self.detail_kind = "forcellini"
                self.detail_depth = 1
                self.detail_parts = []
            elif "memory-card" in class_attr:
                self.detail_kind = "memory"
                self.detail_depth = 1
                self.detail_parts = []
        elif self.detail_kind:
            self.detail_depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.source.handle_endtag(tag)
        if self.current_cell and tag == "td":
            self.current_row[self.current_cell] = normalize(self.current_row[self.current_cell])
            self.current_cell = None
        if self.in_dictionary_row and tag == "tr":
            if self.current_row:
                self.dictionary.append(dict(self.current_row))
            self.in_dictionary_row = False
            self.current_row = {}
        if self.detail_kind:
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
        if self.new_words and self.new_words[-1]["text"] == "":
            self.new_words[-1]["text"] = normalize(data)
        if self.current_cell:
            self.current_row[self.current_cell] += data
        if self.detail_kind:
            self.detail_parts.append(data)


def html_snapshot(html: str) -> dict:
    parser = SnapshotParser()
    parser.feed(html)
    source = parser.source.paragraphs
    return {
        "source_digest": digest(source),
        "source_paragraphs": source,
        "dictionary": parser.dictionary,
        "forcellini_cards": parser.forcellini_cards,
        "memory_cards": parser.memory_cards,
        "new_words": parser.new_words,
        "counts": {
            "source_paragraphs": len(source),
            "source_anchor_ids": len(re.findall(r'id="source-\d+"', html)),
            "new_words": len(parser.new_words),
            "dictionary_rows": len(parser.dictionary),
            "forcellini_cards": len(parser.forcellini_cards),
            "memory_cards": len(parser.memory_cards),
            "teacher_markers": sum(
                marker in html
                for marker in ["Clavis Magistri", "Guida Magistri", "Appendix Probationum"]
            ),
        },
    }


def json_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


def verify_project(root: Path) -> dict:
    project = json.loads((root / "data/project.json").read_text(encoding="utf-8"))
    expected = source_body(root / project["source_docx"], int(project["docx_start_paragraph"]))
    html_path = root / project["output_html"]
    html = html_path.read_text(encoding="utf-8")
    actual_snapshot = html_snapshot(html)
    actual = actual_snapshot["source_paragraphs"]
    cards = json.loads((root / project["forcellini_lock"]).read_text(encoding="utf-8"))["cards"]
    counts = actual_snapshot["counts"]
    failures = []
    if actual != expected:
        failures.append({"kind": "source_text_mismatch"})
    expected_counts = {
        "source_paragraphs": 10,
        "source_anchor_ids": 10,
        "new_words": 26,
        "dictionary_rows": 26,
        "forcellini_cards": 26,
        "memory_cards": 6,
        "teacher_markers": 0,
    }
    for key, expected_value in expected_counts.items():
        if counts[key] != expected_value:
            failures.append({"kind": "count", "key": key, "expected": expected_value, "actual": counts[key]})
    if len(cards) != 26:
        failures.append({"kind": "forcellini_lock_count", "expected": 26, "actual": len(cards)})
    golden_path = project.get("golden")
    golden = None
    if golden_path:
        golden = json.loads((root / golden_path).read_text(encoding="utf-8"))
        actual_hashes = {
            "dictionary": json_digest(actual_snapshot["dictionary"]),
            "forcellini_cards": json_digest(actual_snapshot["forcellini_cards"]),
            "memory_cards": json_digest(actual_snapshot["memory_cards"]),
            "new_words": json_digest(actual_snapshot["new_words"]),
        }
        if actual_snapshot["source_digest"] != golden["source_digest"]:
            failures.append({"kind": "golden_regression", "key": "source_digest"})
        if counts != golden["counts"]:
            failures.append({"kind": "golden_regression", "key": "counts"})
        for key, actual_hash in actual_hashes.items():
            if actual_hash != golden["hashes"].get(key):
                failures.append({"kind": "golden_regression", "key": key})
    report = {
        "schema_version": "slim-html-verify/v1",
        "html": str(html_path),
        "source_digest_expected": digest(expected),
        "source_digest_actual": digest(actual),
        "counts": counts,
        "golden_checked": bool(golden),
        "failures": failures,
    }
    return report
