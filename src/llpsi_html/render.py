from __future__ import annotations

from html import escape
import json
import re
from pathlib import Path

from .source import normalize


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def html_text(value: object) -> str:
    return escape(str(value), quote=False)


def html_attr(value: object) -> str:
    return escape(str(value), quote=True)


def render_list(items: list[str], tag: str = "li") -> str:
    return "\n".join(f"<{tag}>{html_text(item)}</{tag}>" for item in items)


def source_surface_frequency(paragraphs: list[str], surface: str) -> int:
    body = "\n".join(paragraphs)
    count = len(re.findall(rf"(?<!\w){re.escape(surface)}(?!\w)", body))
    return count or body.count(surface)


def short_gloss(card: dict) -> str:
    description = normalize(card.get("definition", ""))
    if len(description) > 170:
        cut = description[:170]
        stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind(","))
        description = cut[: stop + 1] if stop > 70 else cut.rstrip() + "..."
    return f"{card['lemma']}: {description}"


def annotate_source_text(text: str, cards: list[dict], paragraph: int) -> str:
    spans = []
    for card in cards:
        if str(card.get("paragraph")) != str(paragraph):
            continue
        surface = str(card["surface"])
        position = text.find(surface)
        if position != -1:
            spans.append((position, position + len(surface), card))
    spans.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    parts: list[str] = []
    cursor = 0
    for start, end, card in spans:
        if start < cursor:
            continue
        parts.append(html_text(text[cursor:start]))
        surface = text[start:end]
        gloss = short_gloss(card)
        parts.append(
            '<span class="new-word" tabindex="0" '
            f'data-lemma="{html_attr(card["lemma"])}" '
            f'data-gloss="{html_attr(gloss)}" '
            f'aria-label="{html_attr(gloss)}" '
            f'title="{html_attr(gloss)}">{html_text(surface)}</span>'
        )
        cursor = end
    parts.append(html_text(text[cursor:]))
    return "".join(parts)


def render_source(paragraphs: list[str], cards: list[dict]) -> str:
    return "\n".join(
        f'<p class="source-text" id="source-{index}" data-source-paragraph="{index}">'
        f"{annotate_source_text(text, cards, index)}</p>"
        for index, text in enumerate(paragraphs, start=1)
    )


def render_apparatus(lessons: list[dict]) -> str:
    blocks = []
    for index, lesson in enumerate(lessons, start=1):
        blocks.append(
            f"""
            <details class="apparatus-card" data-target="source-{index}" open>
              <summary>{html_text(lesson["title"])}</summary>
              <h3>Praeparatio</h3>
              <ul>{render_list(lesson["praeparatio"])}</ul>
              <h3>Marginalia</h3>
              <ul>{render_list(lesson["marginalia"])}</ul>
            </details>
            """
        )
    return "\n".join(blocks)


def render_exercises(lessons: list[dict]) -> str:
    blocks = []
    for index, lesson in enumerate(lessons, start=1):
        blocks.append(
            f"""
            <section class="lectio" id="lectio-{index}" data-source-paragraph="{index}">
              <h2>{html_text(lesson["title"])}</h2>
              <div class="pensa-grid">
                <section class="pensum"><h3>Pensum A</h3><ol>{render_list(lesson["pensa_a"])}</ol></section>
                <section class="pensum"><h3>Pensum B</h3><ol>{render_list(lesson["pensa_b"])}</ol></section>
                <section class="pensum"><h3>Pensum C</h3><ol>{render_list(lesson["pensa_c"])}</ol></section>
                <section class="pensum"><h3>Pensum D</h3><ol>{render_list(lesson["pensa_d"])}</ol></section>
              </div>
            </section>
            """
        )
    return "\n".join(blocks)


def render_interrogationes(lessons: list[dict]) -> str:
    return "\n".join(
        f"""
        <section class="interrogatio" data-source-paragraph="{index}">
          <h3><a href="#source-{index}">{html_text(lesson["title"])}</a></h3>
          <ol>{render_list(lesson["pensa_c"])}</ol>
        </section>
        """
        for index, lesson in enumerate(lessons, start=1)
    )


def cards_with_frequency(cards: list[dict], paragraphs: list[str]) -> list[dict]:
    enriched = []
    for card in cards:
        copy = dict(card)
        copy["source_surface_frequency"] = source_surface_frequency(paragraphs, str(card["surface"]))
        enriched.append(copy)
    return enriched


def render_dictionary(cards: list[dict]) -> str:
    rows = []
    for card in cards:
        rows.append(
            "<tr>"
            f"<td data-label=\"Lemma\"><a href=\"#card-{html_attr(card['lemma'])}\">{html_text(card['lemma'])}</a></td>"
            f"<td data-label=\"Forma\">{html_text(card['surface'])}</td>"
            f"<td data-label=\"Freq.\">{html_text(card['source_surface_frequency'])}</td>"
            f"<td data-label=\"Par.\">{html_text(card['paragraph'])}</td>"
            f"<td data-label=\"Sensus\">{html_text(card['sense'])}</td>"
            f"<td data-label=\"Forcellini\"><a href=\"{html_attr(card['url'])}\" aria-label=\"Forcellini: {html_attr(card['lemma'])}\">forc2</a></td>"
            f"<td data-label=\"Status\">verified</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_forcellini_cards(cards: list[dict]) -> str:
    blocks = []
    for card in cards:
        blocks.append(
            f"""
            <details class="forcellini-card" id="card-{html_attr(card['lemma'])}">
              <summary>{html_text(card['surface'])} · {html_text(card['lemma'])}</summary>
              <p><b>In Nepote.</b> {html_text(card['context'])}</p>
              <p><b>Forcellini.</b> {html_text(card['definition'])}</p>
              <p><b>Exemplum.</b> {html_text(card['example'])}</p>
              <p><b>Sensus huius loci.</b> {html_text(card['sense'])}</p>
              <p><a href="{html_attr(card['url'])}">Forcellini: {html_text(card['lemma'])}</a></p>
            </details>
            """
        )
    return "\n".join(blocks)


def render_memory_cards(cards: list[dict]) -> str:
    return "\n".join(
        f'<details class="memory-card"><summary>{html_text(card["question"])}</summary>'
        f'<p>{html_text(card["answer"])}</p></details>'
        for card in cards
    )


def render_project(root: Path, paragraphs: list[str]) -> str:
    project = load_json(root / "data/project.json")
    lessons = load_json(root / project["lessons"])["lessons"]
    lock = load_json(root / project["forcellini_lock"])
    memory_cards = load_json(root / "data/memory_cards.json")["cards"]
    cards = cards_with_frequency(lock["cards"], paragraphs)
    template = (root / project["template"]).read_text(encoding="utf-8")
    css = (root / project["css"]).read_text(encoding="utf-8")
    replacements = {
        "title": project["title"],
        "subtitle": project["subtitle"],
        "css": css,
        "source": render_source(paragraphs, cards),
        "apparatus": render_apparatus(lessons),
        "exercises": render_exercises(lessons),
        "interrogationes": render_interrogationes(lessons),
        "dictionary": render_dictionary(cards),
        "forcellini_cards": render_forcellini_cards(cards),
        "memory_cards": render_memory_cards(memory_cards),
    }
    html = template
    for key, value in replacements.items():
        html = html.replace("{{" + key + "}}", str(value))
    return html
