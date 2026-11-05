---
description: Markdown conventions (markdownlint) for README and docs files
applyTo: "**/*.md"
---

# Markdown conventions

- Lint rules are defined in `.markdownlint.json`: markdownlint defaults, except MD013 (line length) is off and MD033 only allows `br` and `img` (the scaled logo in the READMEs).
- Tables use the compact style with a spaced separator row: `| ------ | ------ |` (MD060).
- URLs are never bare: use `<https://example.com/>` or `[text](https://example.com/)` (MD034).
- `README.md` (English) and `README.de.md` (German) must always be kept in sync.
- English Markdown uses American English (`codespell`). `README.de.md` follows the German wording rules of `translations.instructions.md`: a name in a compound is joined with hyphens (`SYR-Connect-Konto`, `Home-Assistant-Entitäten`). cspell and the `german-compounds` hook check it; add new correct technical words to `words` in `cspell.json`.
- Check the file for markdownlint problems after every edit and fix them before finishing.
