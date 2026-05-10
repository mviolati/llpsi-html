from __future__ import annotations

import hashlib
import re
import unicodedata
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", DOCX_NS):
        text = normalize("".join(node.text or "" for node in para.findall(".//w:t", DOCX_NS)))
        if text:
            paragraphs.append(text)
    return paragraphs


def source_body(path: Path, start_paragraph: int) -> list[str]:
    if start_paragraph < 1:
        raise ValueError("start_paragraph is 1-based and must be >= 1")
    return extract_docx_paragraphs(path)[start_paragraph - 1 :]


def digest(paragraphs: list[str]) -> str:
    body = "\n".join(normalize(paragraph) for paragraph in paragraphs)
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()

