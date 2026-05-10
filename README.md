# llpsi-html RFC

Status: draft  
Scope: learner HTML only

## 1. Objective

`llpsi-html` generates a source-faithful learner HTML for Latin texts with
LLPSI-style support around the author text. The author text is not rewritten:
the apparatus, vocabulary, questions, and memory cards are added around an
immutable source container.

The current project builds `dist/epaminondas_llpsi.html` from Nepos'
`Epaminondas`. Runtime code uses only the Python standard library.

## 2. Contract

- The source text in `#textus-auctoris` must match the DOCX source paragraphs.
- The build produces only one deliverable: student HTML.
- Forcellini data is read from `data/forcellini.lock.json`; builds do not fetch
  live web data.
- `llpsi-html release` must end with `failures: 0`.
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
llpsi.py               compatibility wrapper for installed checkouts
```

The pipeline is data-driven:

```text
DOCX + project data + template -> HTML -> verification report
```

## 4. Commands

```powershell
py -m pip install -e .
llpsi-html build
llpsi-html verify
llpsi-html release
```

`release` runs build and verify. On Windows, use `py` for Python itself; on a
configured POSIX shell, the equivalent install command is `python -m pip install -e .`.

## 5. Non-Goals

- No PDF export.
- No ZIP delivery.
- No teacher edition.
- No live Forcellini refresh during build.
- No audit bundle beyond `reports/verify.json` and `data/golden.json`.

## 6. Change Rule

Changes to text extraction, rendering, templates, lessons, or Forcellini data
must pass `llpsi-html release`. A change is accepted only if the verifier
reports zero failures, including the golden-regression check.
