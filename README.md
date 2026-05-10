# llpsi-html RFC

Status: draft  
Scope: learner HTML only

## 1. Objective

`llpsi-html` generates a source-faithful learner HTML for Latin texts with
LLPSI-style support around the author text. The author text is not rewritten:
the apparatus, vocabulary, questions, and memory cards are added around an
immutable source container.

The current project builds `dist/epaminondas_llpsi.html` from Nepos'
`Epaminondas`.

## 2. Contract

- The source text in `#textus-auctoris` must match the DOCX source paragraphs.
- The build produces only one deliverable: student HTML.
- Forcellini data is read from `data/forcellini.lock.json`; builds do not fetch
  live web data.
- `python .\llpsi.py release` must end with `failures: 0`.
- The verifier checks source integrity, expected structural counts, no teacher
  markers, and compact golden-regression hashes.

## 3. Architecture

```text
input/                 source DOCX
data/                  project data, lessons, Forcellini lock, golden hashes
templates/             HTML and CSS
src/llpsi_html/        source extraction, rendering, verification
dist/                  generated HTML
reports/               generated verification report
llpsi.py               CLI: build, verify, release
```

The pipeline is data-driven:

```text
DOCX + project data + template -> HTML -> verification report
```

## 4. Commands

```powershell
python .\llpsi.py build
python .\llpsi.py verify
python .\llpsi.py release
```

`release` runs build and verify.

## 5. Non-Goals

- No PDF export.
- No ZIP delivery.
- No teacher edition.
- No live Forcellini refresh during build.
- No audit bundle beyond `reports/verify.json` and `data/golden.json`.

## 6. Change Rule

Changes to text extraction, rendering, templates, lessons, or Forcellini data
must pass `python .\llpsi.py release`. A change is accepted only if the verifier
reports zero failures, including the golden-regression check.

