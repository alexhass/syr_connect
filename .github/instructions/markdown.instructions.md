---
description: Markdown conventions (markdownlint) for README and docs files
applyTo: "**/*.md"
---

# Markdown conventions

- Lint rules are defined in `.markdownlint.json`: markdownlint defaults, except MD013 (line length) is off and MD033 only allows `br` and `img` (the scaled logo in the READMEs).
- Tables use the compact style with a spaced separator row: `| ------ | ------ |` (MD060).
- URLs are never bare: use `<https://example.com/>` or `[text](https://example.com/)` (MD034).
- `README.md` (English) and `README.de.md` (German) must always be kept in sync.
- English Markdown uses American English (`codespell`). `README.de.md` follows the German wording rules of `translations.instructions.md`: a product name in a compound stays unchanged and is joined to the noun with a hyphen (`SYR Connect-App`, `SYR Connect-Konto`, `Home Assistant-Entitäten`, `Husty SaoCal-Geräte`), never `SYR-Connect-Konto` or `Home-Assistant-Entitäten`. Quotes around the name only where the German spelling rules require them. cspell and the `german-compounds` hook check it; add new correct technical words to `words` in `cspell.json`.
- Sentences end with a period, also in lists (DIN 5008, Microsoft and Google style guides). If one item of a list is a complete sentence (an English imperative counts), every item of that list ends with a period. Lists of fragments without a verb (device lists, sensor overviews, input fields) have no periods. Numbered steps always end with a period (or a colon before a nested list), in both languages.
- Check the file for markdownlint problems after every edit and fix them before finishing.
