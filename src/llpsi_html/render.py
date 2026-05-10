from __future__ import annotations

from html import escape
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from .source import normalize

PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")
WORD_BOUNDARY = r"(?<!\w){surface}(?!\w)"
FORCELLINI_HOST = "lexica.linguax.com"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def html_text(value: object) -> str:
    return escape(str(value), quote=False)


def html_attr(value: object) -> str:
    return escape(str(value), quote=True)


def render_list(items: list[str]) -> str:
    return "\n".join(f"<li>{html_text(item)}</li>" for item in items)


def surface_pattern(surface: str) -> re.Pattern[str]:
    if not surface:
        raise ValueError("surface must not be empty")
    return re.compile(WORD_BOUNDARY.format(surface=re.escape(surface)))


def source_surface_frequency(body: str, surface: str) -> int:
    return len(surface_pattern(surface).findall(body))


def slugify(value: object) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "-", normalize(str(value)).lower()).strip("-")
    return slug or "card"


def assign_card_ids(cards: list[dict]) -> list[dict]:
    used: dict[str, int] = {}
    enriched = []
    for card in cards:
        copy = dict(card)
        base = slugify(copy["lemma"])
        used[base] = used.get(base, 0) + 1
        copy["html_id"] = base if used[base] == 1 else f"{base}-{used[base]}"
        enriched.append(copy)
    return enriched


def safe_forcellini_url(value: object) -> str | None:
    url = str(value)
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc == FORCELLINI_HOST and parsed.path.endswith("/forc2.php"):
        return url
    return None


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
        match = surface_pattern(surface).search(text)
        if match:
            spans.append((match.start(), match.end(), card))
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
    body = "\n".join(paragraphs)
    enriched = []
    for card in assign_card_ids(cards):
        copy = dict(card)
        copy["source_surface_frequency"] = source_surface_frequency(body, str(card["surface"]))
        enriched.append(copy)
    return enriched


def render_dictionary(cards: list[dict]) -> str:
    rows = []
    for card in cards:
        url = safe_forcellini_url(card["url"])
        forcellini = (
            f"<a href=\"{html_attr(url)}\" aria-label=\"Forcellini: {html_attr(card['lemma'])}\">forc2</a>"
            if url
            else "forc2"
        )
        rows.append(
            "<tr>"
            f"<td data-label=\"Lemma\"><a href=\"#{html_attr(card['html_id'])}\">{html_text(card['lemma'])}</a></td>"
            f"<td data-label=\"Forma\">{html_text(card['surface'])}</td>"
            f"<td data-label=\"Freq.\">{html_text(card['source_surface_frequency'])}</td>"
            f"<td data-label=\"Par.\">{html_text(card['paragraph'])}</td>"
            f"<td data-label=\"Sensus\">{html_text(card['sense'])}</td>"
            f"<td data-label=\"Forcellini\">{forcellini}</td>"
            f"<td data-label=\"Status\">verified</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_forcellini_cards(cards: list[dict]) -> str:
    blocks = []
    for card in cards:
        url = safe_forcellini_url(card["url"])
        source_link = (
            f'<p><a href="{html_attr(url)}">Forcellini: {html_text(card["lemma"])}</a></p>'
            if url
            else f"<p>Forcellini: {html_text(card['lemma'])}</p>"
        )
        blocks.append(
            f"""
            <details class="forcellini-card" id="{html_attr(card['html_id'])}">
              <summary>{html_text(card['surface'])} · {html_text(card['lemma'])}</summary>
              <p><b>In Nepote.</b> {html_text(card['context'])}</p>
              <p><b>Forcellini.</b> {html_text(card['definition'])}</p>
              <p><b>Exemplum.</b> {html_text(card['example'])}</p>
              <p><b>Sensus huius loci.</b> {html_text(card['sense'])}</p>
              {source_link}
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
        "title": html_text(project["title"]),
        "subtitle": html_text(project["subtitle"]),
        "css": css,
        "source": render_source(paragraphs, cards),
        "apparatus": render_apparatus(lessons),
        "exercises": render_exercises(lessons),
        "interrogationes": render_interrogationes(lessons),
        "dictionary": render_dictionary(cards),
        "forcellini_cards": render_forcellini_cards(cards),
        "memory_cards": render_memory_cards(memory_cards),
    }
    return render_template(template, replacements)


def render_template(template: str, replacements: dict[str, object]) -> str:
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in replacements:
            raise ValueError(f"unknown template placeholder: {key}")
        seen.add(key)
        return str(replacements[key])

    html = PLACEHOLDER_RE.sub(replace, template)
    missing = sorted(set(replacements) - seen)
    if missing:
        raise ValueError(f"unused template replacements: {', '.join(missing)}")
    leftovers = PLACEHOLDER_RE.findall(html)
    if leftovers:
        raise ValueError(f"unresolved template placeholders: {', '.join(sorted(set(leftovers)))}")
    return html
