# Reference Manager review (October 2026)

Scope: improve the existing Reference Generator (`/tools/reference-generator`) without changing its data model or architecture.

- No database migration was needed. References still live in the same `UserToolWorkspace` JSON (key `reference-generator`) and in the same browser storage key.
- Existing lists load unchanged.
- New fields (`pmid`, `isbn`, `accessed`) are optional. Older data simply has them empty.

## Bugs fixed

| Problem | Effect | Fix |
| --- | --- | --- |
| "Source type" defaulted to Journal Article, and the server forced that type on every result. | Books and chapters found by DOI were saved as journal articles, with their required fields missing. | The default is now "Any source type". A chosen type only sorts matching results first and sets the type for plain links. |
| Crossref and OpenAlex chapters put the book title in the journal field. Reports had no organisation and preprints had no site. | These entries always showed as incomplete. | Each type's container fields are filled correctly. More Crossref types are mapped, such as monographs, proceedings papers and theses. |
| Changing the source type in the editor erased everything except title and authors. | Typed details were lost. | All fields are kept. |
| Empty fields broke the formatted output. | You got text like `vol. , no.` and `Journal, (4)`, and APA lists were numbered. | The formatter builds each part only when its data exists and handles end punctuation. Author-date styles are sorted by author and not numbered. |
| Nature was an exact copy of Vancouver; Harvard, ACS and Chicago author formats were wrong. | Wrong references for those journals. | Each style now follows its own rules for authors, italics, editions, chapters, reports and websites. |
| Duplicate check used `doi \|\| title \|\| url` as written. | `https://doi.org/10.x` and `10.x` counted as different works, and so did the same title with different capitals. | DOIs, titles, links, PMIDs and ISBNs are normalised before comparing. |
| The BibTeX reader failed on nested braces, such as `{The {COVID}-19 pandemic}`. | Titles were cut off or lost on import. | It now reads braces properly, converts LaTeX accents, handles organisation authors and supports more entry types. |
| Account sync could hit the 600 KB limit at a few hundred references. | Sync paused with a technical message. | Empty fields are left out of the saved copy. A large library now takes about half the space. |
| Book authors from Open Library sometimes included "M.D." or "Dr". | Names like "M.D. TB" appeared. | Titles and degrees are removed. |

## New and improved

- **Identifiers:** PubMed ID (via NCBI), ISBN (via Open Library, with check-digit validation), and DOIs Crossref doesn't hold (arXiv, Zenodo, DataCite) through doi.org. A single identifier is added straight away, with no result list to click through.
- **Search results:** an Add button on each result, results already in the list are marked, an "Add all" option, and the window stays open.
- **Fill missing details:** looks the reference up by DOI, PMID, ISBN or exact title and fills only the empty fields. Existing details are never overwritten, and by title it only uses a result with the same title.
- **Checks:** "Needs attention" counts and filters incomplete references. Plain-language warnings flag a bad year, an incomplete DOI, a link without https, an all-capitals title, "et al." typed into the author list, and a journal article with no volume, pages or DOI.
- **Duplicates:** "Find duplicates" groups copies by DOI, PMID, ISBN, link, or title and year. "Merge" keeps the most complete copy and fills its gaps, and nothing merges unless you choose to. The detail panel warns when the selected reference has a twin.
- **Bulk actions:** checkboxes and "select all shown", then Copy, Export RIS, Move or copy to another list (skipping duplicates), or Delete.
- **Undo:** deleting references, deleting a list and merging can all be undone for 12 seconds.
- **Import formats:** BibTeX, RIS (more tags), PubMed `.nbib` and CSL JSON. Duplicates inside a file are skipped and reported.
- **Export formats:** RIS, BibTeX, CSL JSON, plain text, and an HTML bibliography that opens in Word with italics and hanging indents.
- **Copying:** citations are copied with italics (rich text) for Word and Google Docs.
- **Editor:** shows how the authors were read, recognises organisations, accepts "Smith JA, Doe B" lists, shows a live preview and warnings, and offers a date picker for "Date accessed".
- **Lists:** create and rename them inline instead of in browser pop-ups.
- **Search filter:** now also matches authors, year, publisher and PMID.
- **Speed:** checks and formatted citations are computed once per change instead of on every render.

## Not changed

- The citation search still uses one Reference Generator allowance per successful lookup, including "Fill missing details".
- URLs are still not fetched by the server, which protects against SSRF.
- Tags were not added. Lists already work as folders, and tags would add complexity for a small gain.
