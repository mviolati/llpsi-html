from __future__ import annotations

import argparse
import json
from pathlib import Path

from .render import render_project
from .source import source_body
from .verify import verify_project


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def load_project(root: Path) -> dict:
    return json.loads((root / "data/project.json").read_text(encoding="utf-8"))


def build(root: Path) -> Path:
    project = load_project(root)
    paragraphs = source_body(root / project["source_docx"], int(project["docx_start_paragraph"]))
    html = render_project(root, paragraphs)
    output = root / project["output_html"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def verify(root: Path) -> tuple[dict, Path]:
    project = load_project(root)
    report = verify_project(root)
    report_path = root / project["verify_report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llpsi-html")
    parser.add_argument("command", choices=["build", "verify", "release"])
    parser.add_argument("--root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command in {"build", "release"}:
        output = build(root)
        print(json.dumps({"built": str(output)}, indent=2))
    if args.command in {"verify", "release"}:
        report, report_path = verify(root)
        print(json.dumps({"verified": str(report_path), "failures": len(report["failures"])}, indent=2))
        return 1 if report["failures"] else 0
    return 0
