from __future__ import annotations

import hashlib
import re
import unicodedata
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DOCX_DOCUMENT = "word/document.xml"
DOCX_XML_LIMIT_BYTES = 5_000_000
BLOCKED_XML_MARKERS = ("<!DOCTYPE", "<!ENTITY")
XML_SCAN_ENCODINGS = ("utf-8-sig", "utf-16", "utf-16le", "utf-16be", "utf-32", "utf-32le", "utf-32be")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        document = archive.getinfo(DOCX_DOCUMENT)
        if document.file_size > DOCX_XML_LIMIT_BYTES:
            raise ValueError(f"{DOCX_DOCUMENT} is unexpectedly large")
        xml = archive.read(document)
    reject_dtd_or_entities(xml)
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    # The project contract extracts visible paragraph text from simple DOCX bodies.
    for para in root.findall(".//w:p", DOCX_NS):
        text = normalize("".join(node.text or "" for node in para.findall(".//w:t", DOCX_NS)))
        if text:
            paragraphs.append(text)
    return paragraphs


def reject_dtd_or_entities(xml: bytes) -> None:
    if any(marker.encode("ascii") in xml.upper() for marker in BLOCKED_XML_MARKERS):
        raise ValueError("DOCX XML must not contain DTD or entity declarations")
    for encoding in XML_SCAN_ENCODINGS:
        try:
            text = xml.decode(encoding).upper()
        except UnicodeDecodeError:
            continue
        if any(marker in text for marker in BLOCKED_XML_MARKERS):
            raise ValueError("DOCX XML must not contain DTD or entity declarations")


def source_body(path: Path, start_paragraph: int) -> list[str]:
    if start_paragraph < 1:
        raise ValueError("start_paragraph is 1-based and must be >= 1")
    return extract_docx_paragraphs(path)[start_paragraph - 1 :]


def digest(paragraphs: list[str]) -> str:
    body = "\n".join(normalize(paragraph) for paragraph in paragraphs)
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()
