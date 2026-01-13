# Document build script

Run (Markdown only):
`python3 Paper/Document/build_document.py`

Optional exports:
`python3 Paper/Document/build_document.py --docx`
`python3 Paper/Document/build_document.py --pdf`
`python3 Paper/Document/build_document.py --docx --pdf`

Venv setup (optional, for consistency):
```bash
python3 -m venv Paper/Document/.venv
source Paper/Document/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r Paper/Document/requirements.txt
```

Outputs land in `Paper/Document/outputs/run_###/` as:
- `merged.md`
- `merged.docx` (when `--docx` is used; requires `pandoc`)
- `merged.pdf` (when `--pdf` is used; requires `pandoc` plus a PDF engine such as `xelatex`)

The script concatenates `Paper/0_Abstract` through `Paper/8_References` in order.
