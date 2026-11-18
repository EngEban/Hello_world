# ResRef UX Audit

## Executive UX Summary

ResRef has a strong product foundation: the information architecture is clearer than the earlier generic version, the platform has real tools and admin workflows, and the backend/frontend architecture supports future growth. The biggest design challenge is consistency. Some pages now feel premium and purpose-driven, while others still behave like independent feature builds with different spacing, card language, form density, visual weight, and interaction patterns.

The next design phase should not add more features. It should unify hierarchy, content strategy, responsive behavior, accessibility, and conversion paths into one coherent research platform experience.

## Strengths

- Clear core navigation: Home, Database, Services, Team, About, Contact, FAQ.
- Strong practical feature set for research users.
- Dedicated pages for major tools instead of hiding them as small widgets.
- Account and dashboard architecture support future platform growth.
- Dashboard has useful operational groupings and domain-based structure.
- Brand colors are distinctive and appropriate for healthcare/research.
- Existing React components provide a reusable base for redesign.

## UI and Visual Issues

- Page quality is uneven across the app. Tool pages, marketing pages, and dashboard pages do not always feel like one design system.
- Some sections rely heavily on white cards over pale backgrounds, which can reduce the premium feel.
- Shadows, borders, radius, and card spacing vary across files and page families.
- The dashboard and public website use related colors but different visual languages.
- Several pages have dense text blocks that need editorial hierarchy and clearer scanning patterns.
- Some mobile layouts compress complex cards/forms without enough hierarchy.
- Icon treatments are inconsistent: some icons are outline buttons, some are text-like social placeholders, and some are embedded in cards.
- The public header is functionally clear but should be assessed for mobile nav depth, dropdown behavior, tap targets, and scroll behavior.
- Some legacy CSS remains in `resref.css` while newer styles are in `platform-redesign.css`, `upgrades.css`, and tool-specific files, increasing design drift risk.

## UX and Information Architecture Issues

- Database categories from the original site are not fully exposed in top-level navigation, which may weaken discoverability.
- Advanced Search exists as an icon route, but users may not understand the difference between Database, Advanced Search, and Journal Finder.
- Tool pages are valuable, but the product should better explain which tool to use for which research job.
- Expert Consultation should more clearly connect user problems to service outcomes and trust proof.
- Account value is not yet fully clear before sign-in. Users need to know why saving/syncing matters.
- Dashboard route ownership is clear for admins, but public users should not feel exposed to admin concepts.
- Legal pages exist, but they should eventually be reviewed by a legal professional and written in a more polished trust-oriented style.

## Mobile Issues

- Large tool workflows, especially Sample Size Calculator and Reference Generator, are complex on narrow screens.
- Some multi-column dashboard layouts collapse but may still be heavy for mobile admin use.
- Dropdown navigation and service discovery need careful mobile testing.
- Tables often rely on horizontal overflow, which is functional but not ideal for repeated mobile use.
- Long cards and forms can create scroll fatigue.
- Button groups may wrap unpredictably on small widths.
- Mobile screenshots should be reviewed for first-viewport clarity: users should immediately understand page purpose and primary action.

## Accessibility Issues

- Some icon-only controls need verified accessible labels and visible focus states.
- Color contrast should be audited systematically, especially muted text on blue backgrounds and pale card text.
- Form error states should be consistent and announced clearly.
- Social links should use real accessible names rather than visual placeholder letters.
- Keyboard navigation should be tested for dropdown menus, dashboard sidebar, forms, and tool workflows.
- Dashboard tables need clear header relationships and accessible action labels.
- Motion and micro-interactions should respect reduced-motion preferences.
- Dynamic content rendered from CMS/API should preserve semantic headings, lists, and link labels.

## Conversion Issues

- Expert Consultation should be the primary service conversion journey, but the value proposition can be sharper.
- Request forms are present, but trust proof, expected response time, and next steps should be clearer near submission.
- Newsletter subscription needs stronger reason-to-subscribe copy and visible validation states.
- Database/tool users need contextual nudges to sign in when saving/syncing has a clear benefit.
- Research Opportunities and Join Our Team should better separate applicants, collaborators, and research participants.
- Calls to action should use consistent priority: primary action, secondary action, text link.

## Content Issues

- Wording is sometimes inconsistent: "ResRef", "ResRef.com", "Research Reference", "Medical Research Platform", and "Research Reference Platform" appear in different contexts.
- Some headings are long and should be edited for clarity and rhythm.
- Tool pages need concise "who this is for" and "what output you get" summaries.
- Arabic content support exists through `ArabicTextEnhancer`, but mixed-language pages need direct QA for readability, direction, and typographic scale.

## Technical UX Risks

- Multiple style files can cause conflicting visual rules.
- Legacy public pages under `frontend/src/pages/public` remain in the codebase and may confuse future designers.
- Dynamic fallback route `/:slug` can hide routing mistakes by rendering unexpected content paths.
- Browser screenshots revealed long/complex pages can be heavy to capture as full-page images.
- Dashboard UI is powerful but may become hard to maintain without a documented component standard.

## Recommended Redesign Priorities

1. Define a single ResRef product narrative and page hierarchy.
2. Create a unified design system across public pages, tools, account, and dashboard.
3. Redesign the main public journeys: Home to Database, Home to Tool, Tool to Account, Consultation to Request.
4. Simplify mobile navigation and tool workflows.
5. Standardize forms, cards, buttons, tables, filters, badges, and empty states.
6. Add accessibility QA to every core journey.
7. Produce page templates before redesigning every page individually.

