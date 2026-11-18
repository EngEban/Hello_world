# Research Analyzer

Three-step statistics studio: **Upload → Analyse → Report**.

## Structure

- `studio/AnalyzerStudio.jsx` owns the workflow state (dataset, variable types, results, report choices) and keeps it in `sessionStorage`, so reloads never lose results.
- `studio/UploadScreen.jsx` — drop zone and the example datasets in `public/analyzer-example-*.csv`.
- `studio/Workspace.jsx` — variables panel, the question card, result cards and suggested analyses.
- `studio/AskCard.jsx` — question types → sentence builder → recommended method with reasons (`/recommend/`), advanced options, and the input form for methods picked from the library.
- `studio/MethodsLibrary.jsx` — every method from `/methods/`, basic first, advanced behind a switch.
- `studio/ResultCard.jsx` + `studio/resultModel.js` — one display model for every result type (headline, key numbers, tables, checks, chart, bilingual write-up) with Simple / Full views. The report and Word export use the same model.
- `studio/ReportScreen.jsx` — assembled manuscript section, English / Arabic, Word (`/report/docx/`), print and copy.
- `studio/i18n.jsx` — interface text in English and Arabic.
- `services/researchAnalyzerApi.js` — the only API layer; uses the shared ResRef API client.

## Backend

`backend/research_analyzer`: `services/` holds the validated basic tests and data import; `engine/` holds the
method registry, the test-selection rules, the advanced methods and the Word builder (see the package docstring).
