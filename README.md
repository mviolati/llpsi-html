# llpsi-html

Generate one source-faithful LLPSI-style learner HTML.

Run:

```powershell
py .\llpsi.py
```

Expected result: `dist/epaminondas_llpsi.html` is rebuilt and
`reports/verify.json` ends with `"failures": []`.

## Commands

```powershell
py .\llpsi.py build
py .\llpsi.py verify
py .\llpsi.py release
```

With no command, `llpsi.py` runs `release`.

Optional installable CLI:

```powershell
py -m pip install -e .
llpsi-html release
```

## Contract

- The author text in `#textus-auctoris` must match the DOCX source paragraphs.
- The build produces only student HTML.
- Forcellini data comes from `data/forcellini.lock.json`; the build never fetches live web data.
- Golden verification is mandatory and covers source text, vocabulary, memory cards, lesson data, and locked Forcellini data.
- Teacher-only markers are forbidden in the student HTML.

## Shape

```text
input/                 source DOCX
data/                  project data and golden hashes
templates/             page HTML, repeated HTML fragments, CSS
src/llpsi_html/        source extraction, rendering, verification
dist/                  generated HTML
reports/               generated verification report
llpsi.py               direct CLI
```

Runtime code uses only the Python standard library.
