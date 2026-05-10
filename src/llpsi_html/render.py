from __future__ import annotations

from html import escape
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from .source import normalize

PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")
FRAGMENT_RE = re.compile(r"<!--\s*fragment:([a-z_]+)\s*-->(.*?)<!--\s*/fragment:\1\s*-->", re.S)
WORD_BOUNDARY = r"(?<!\w){surface}(?!\w)"
FORCELLINI_HOST = "lexica.linguax.com"
PENSA = (
    ("Pensum A", "pensa_a"),
    ("Pensum B", "pensa_b"),
    ("Pensum C", "pensa_c"),
    ("Pensum D", "pensa_d"),
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_fragments(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    fragments = {name: body.strip() for name, body in FRAGMENT_RE.findall(text)}
    if not fragments:
        raise ValueError(f"no HTML fragments found in {path}")
    return fragments


def html_text(value: object) -> str:
    return escape(str(value), quote=False)


def html_attr(value: object) -> str:
    return escape(str(value), quote=True)


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


def render_fragment(fragments: dict[str, str], name: str, **values: object) -> str:
    if name not in fragments:
        raise ValueError(f"missing HTML fragment: {name}")
    return render_template(fragments[name], values)


def render_list(fragments: dict[str, str], items: list[str]) -> str:
    return "\n".join(render_fragment(fragments, "list_item", item=html_text(item)) for item in items)


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


def annotate_source_text(text: str, cards: list[dict], paragraph: int, fragments: dict[str, str]) -> str:
    spans = []
    for card in cards:
        if str(card.get("paragraph")) != str(paragraph):
            continue
        match = surface_pattern(str(card["surface"])).search(text)
        if match:
            spans.append((match.start(), match.end(), card))
    spans.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    parts: list[str] = []
    cursor = 0
    for start, end, card in spans:
        if start < cursor:
            continue
        parts.append(html_text(text[cursor:start]))
        gloss = short_gloss(card)
        parts.append(
            render_fragment(
                fragments,
                "new_word",
                lemma=html_attr(card["lemma"]),
                gloss=html_attr(gloss),
                surface=html_text(text[start:end]),
            )
        )
        cursor = end
    parts.append(html_text(text[cursor:]))
    return "".join(parts)


def render_source(paragraphs: list[str], cards: list[dict], fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(
            fragments,
            "source_paragraph",
            index=html_attr(index),
            text=annotate_source_text(text, cards, index, fragments),
        )
        for index, text in enumerate(paragraphs, start=1)
    )


def render_apparatus(lessons: list[dict], fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(
            fragments,
            "apparatus_card",
            index=html_attr(index),
            title=html_text(lesson["title"]),
            praeparatio=render_list(fragments, lesson["praeparatio"]),
            marginalia=render_list(fragments, lesson["marginalia"]),
        )
        for index, lesson in enumerate(lessons, start=1)
    )


def render_pensa(lesson: dict, fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(fragments, "pensum", title=title, items=render_list(fragments, lesson[key]))
        for title, key in PENSA
    )


def render_exercises(lessons: list[dict], fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(
            fragments,
            "lectio",
            index=html_attr(index),
            title=html_text(lesson["title"]),
            pensa=render_pensa(lesson, fragments),
        )
        for index, lesson in enumerate(lessons, start=1)
    )


def render_interrogationes(lessons: list[dict], fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(
            fragments,
            "interrogatio",
            index=html_attr(index),
            title=html_text(lesson["title"]),
            questions=render_list(fragments, lesson["pensa_c"]),
        )
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


def render_forcellini_link(fragments: dict[str, str], card: dict, label: str = "forc2") -> str:
    url = safe_forcellini_url(card["url"])
    if not url:
        return html_text(label)
    return render_fragment(
        fragments,
        "forcellini_link",
        url=html_attr(url),
        lemma=html_attr(card["lemma"]),
        label=html_text(label),
    )


def render_dictionary(cards: list[dict], fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(
            fragments,
            "dictionary_row",
            card_id=html_attr(card["html_id"]),
            lemma=html_text(card["lemma"]),
            surface=html_text(card["surface"]),
            frequency=html_text(card["source_surface_frequency"]),
            paragraph=html_text(card["paragraph"]),
            sense=html_text(card["sense"]),
            forcellini=render_forcellini_link(fragments, card),
        )
        for card in cards
    )


def render_forcellini_cards(cards: list[dict], fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(
            fragments,
            "forcellini_card",
            card_id=html_attr(card["html_id"]),
            surface=html_text(card["surface"]),
            lemma=html_text(card["lemma"]),
            context=html_text(card["context"]),
            definition=html_text(card["definition"]),
            example=html_text(card["example"]),
            sense=html_text(card["sense"]),
            source=render_forcellini_link(fragments, card, f"Forcellini: {card['lemma']}"),
        )
        for card in cards
    )


def render_memory_cards(cards: list[dict], fragments: dict[str, str]) -> str:
    return "\n".join(
        render_fragment(
            fragments,
            "memory_card",
            question=html_text(card["question"]),
            answer=html_text(card["answer"]),
        )
        for card in cards
    )


def render_project(root: Path, paragraphs: list[str]) -> str:
    project = load_json(root / "data/project.json")
    lessons = load_json(root / project["lessons"])["lessons"]
    lock = load_json(root / project["forcellini_lock"])
    memory_cards = load_json(root / project["memory_cards"])["cards"]
    cards = cards_with_frequency(lock["cards"], paragraphs)
    template = (root / project["template"]).read_text(encoding="utf-8")
    fragments = load_fragments(root / project["fragments"])
    css = (root / project["css"]).read_text(encoding="utf-8")
    replacements = {
        "title": html_text(project["title"]),
        "subtitle": html_text(project["subtitle"]),
        "css": css,
        "source": render_source(paragraphs, cards, fragments),
        "apparatus": render_apparatus(lessons, fragments),
        "exercises": render_exercises(lessons, fragments),
        "interrogationes": render_interrogationes(lessons, fragments),
        "dictionary": render_dictionary(cards, fragments),
        "forcellini_cards": render_forcellini_cards(cards, fragments),
        "memory_cards": render_memory_cards(memory_cards, fragments),
    }
    return render_template(template, replacements)
