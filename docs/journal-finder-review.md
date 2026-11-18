# Journal Finder review (October 2026)

Scope: improve the existing Journal Finder without changing its data
(`journals_db.json`, `Category_to_keyword.js`) or its matching engine
(`matching_logic.js`). Every change is in the page, its helpers
(`features/journalFinder/journalFinderModel.js`) and its stylesheet.

## Bugs fixed

| Problem | Effect | Fix |
| --- | --- | --- |
| Publisher, quartile, access and minimum H-index were applied only when the search ran. | Changing them after a search did nothing until the user searched again, which also used another search from their allowance. | All filters are now applied in the browser and update the results at once. The engine is still called the same way, with these four left empty. |
| The fee filter compared raw numbers and ignored the currency. | `280000 KRW` (about $200) failed "under 1,000"; `1100 USD; 740 GBP` passed it as 740. | Fees are read in US dollars, with other currencies converted approximately (`apcUsd`). "Lowest publication fee" sorting uses the same value. |
| Diamond journals with no listed fee were left out of "Free only". | 349 diamond journals were missing from that filter. | A diamond journal with no listed fee counts as having no fee. |
| 30 journals have quartile `-`. | The cards showed a "-" chip and a "- journal" reason. | Shown as "Unranked". |
| "Visit" opened a Google search for 75% of journals. | Users expected the journal's website. | The button says "Search online" or "Journal website", depending on the link. |
| "Free" was shown for 4,488 subscription journals. | It read as free to publish open access. | Shown as "No fee (subscription)". |
| The manuscript text was saved but brought back only for signed-in users. | Guests had to retype it on every visit. | The last title, abstract and settings come back for everyone. |
| A hidden table label overflowed on phones. | The page could scroll sideways. | Fixed. |

## UX improvements

- **Layout:** the manuscript and filters are on the left and the wider results on the right. Phones show them in the order you use them.
- **Results header:** shows the total, how many journals the filters hide, and how the list is ordered. Removable filter chips and a sort menu sit above the list.
- **Showing more results:** 30 results first, then "Show 30 more". This replaces the "Results" number box.
- **Result cards:**
  - labelled facts: quartile, H-index, access, fee (multi-currency fees in a tooltip) and review time
  - the ISSN
  - the categories that match your manuscript are highlighted and listed first
  - plain reasons that don't repeat the facts
  - a fit label: Strong, Good or Possible
- **Detected fields:** select one to filter the results to that field. The field filter lists the detected fields first.
- **Optional inputs:** article type, study design and audience are in a section you can open. The abstract shows a word count with a hint about length.
- **Shortlist:** a comparison table with every saved journal, each with a link and a remove button. The shortlist can be exported to CSV.
- **Phones:** after a search the page jumps to the results.
- **Ranking rules:** stated in plain words in "How results are ranked". The hero chips describe what the user gets instead of internal rules.

## Not changed (business rules)

- The publisher priority order (BMC, BMJ, SAGE, Wiley, Elsevier, Oxford, Cambridge, Wolters Kluwer; three each), the case-report boost, and the scoring itself.
- One search uses one Journal Finder allowance. Filtering and sorting don't use any.
