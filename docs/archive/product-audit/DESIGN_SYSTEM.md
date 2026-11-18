# ResRef Design System Audit

## Current Brand Colors

User-provided brand colors:

- Navy: `#062B80`
- Blue: `#126AC6`
- Sky: `#4FB9FC`
- Beige: `#F6F5DA` - requested not to use as a dominant UI color

Common colors found in the current codebase:

- Deep navy: `#071f52`, `#061c4a`, `#041636`, `#05205b`, `#102b5d`
- Primary blue: `#126ac6`, `#1f6ff2`, `#0967bd`
- Sky/accent blue: `#4fb9fc`, `#62bdff`, `#8ccfff`
- Ink/text: `#10233f`, `#243752`, `#284768`, `#2f4767`
- Muted text: `#52647c`, `#62718a`, `#718096`
- Lines: `#dce7f3`, `#e0e7ef`, `#dbe4ee`, `#e3edf7`
- Soft backgrounds: `#f5f8fc`, `#f8fbff`, `#eef5fc`, `#eff7ff`
- Success: `#087f5b`, `#eaf8f2`
- Warning: `#936a00`, `#fff6dc`
- Error: `#c92a2a`, `#fff0f0`

## Color System Recommendation

The redesign should reduce drift by formalizing semantic tokens:

- `brand.navy`: Primary authority, header, footer, hero dark areas.
- `brand.blue`: Primary action, links, active states.
- `brand.sky`: Accent, highlights, data emphasis, selected states.
- `surface.base`: Page background.
- `surface.panel`: Cards and forms.
- `surface.subtle`: Soft section bands.
- `text.strong`: Main headings.
- `text.body`: Body copy.
- `text.muted`: Secondary copy.
- `border.default`: Low contrast dividers.
- `status.success`, `status.warning`, `status.error`, `status.info`.

Beige should be avoided as a dominant background. If it is used at all, it should be limited to very small warm highlights or editorial callouts after brand approval.

## Typography

Observed fonts:

- Heading/logo areas reference `Comfortaa`.
- Body and fallback text use `Arial, sans-serif`.
- Code/editor areas use `Consolas, monospace`.

Current issues:

- Font usage is not fully documented as a system.
- Heading scale varies by page family.
- Some compact dashboard headings and large marketing headings need clearer rules.
- Arabic text requires dedicated font and line-height decisions.

Recommended typography roles:

- Display: Major hero headings only.
- Page title: Public and dashboard page titles.
- Section title: Section-level hierarchy.
- Card title: Compact card headings.
- Body: Main text.
- Small/meta: Labels, badges, bylines, helper text.
- Form label: Consistent weight and size.
- Data/table text: Dense but readable dashboard typography.

## Spacing

Observed patterns:

- Public sections commonly use `.section` with large vertical padding.
- Containers use `.site-container`.
- Dashboard uses `admin-content`, cards, grids, and toolbars.
- Tool pages have custom spacing systems in their own CSS files.

Current issues:

- Section spacing varies across public, tool, account, and dashboard areas.
- Some cards have generous padding while others are dense.
- Mobile spacing is sometimes a direct compression of desktop rather than a designed rhythm.

Recommended spacing scale:

- `4px`: Micro gaps, icon/text alignment.
- `8px`: Compact controls.
- `12px`: Form/control internal spacing.
- `16px`: Card internal rhythm.
- `24px`: Card padding and grid gaps.
- `32px`: Section subgroups.
- `48px`: Major section spacing.
- `72px`: Desktop vertical section rhythm.
- `96px`: Hero/major campaign sections only.

## Layout Patterns

Current layout patterns:

- Public header/topbar and footer.
- Full-width section bands with constrained `site-container`.
- Hero sections with split copy/visual layouts.
- Card grids for services, benefits, audiences, and values.
- Tool workflow layouts with side panels and result panels.
- Forms inside cards or split sections.
- Dashboard shell with fixed sidebar and topbar.
- Dashboard content grids, tables, review layouts, editors, and media grids.

Recommended layout system:

- Public pages should use a limited set of templates:
  - Landing page template.
  - Service conversion page template.
  - Tool application page template.
  - Content listing page template.
  - Institutional/trust page template.
  - Contact/support page template.
  - Legal/static content template.
- Dashboard pages should use:
  - Overview page.
  - Table/list management page.
  - Split list/detail page.
  - Editor page.
  - Settings page.
  - Reports page.

## Component Standards Needed

- Buttons: Primary, secondary, ghost, danger, icon-only, text link.
- Cards: Service, resource, metric, benefit, trust, dashboard, media, application.
- Forms: Labels, helper text, validation, error summary, success state.
- Tables: Header style, empty state, action cells, responsive behavior.
- Filters: Search, select, status filter, reset action.
- Badges: Status, category, membership, role.
- Alerts: Info, success, warning, error.
- Navigation: Desktop dropdown, mobile drawer/menu, dashboard sidebar.
- Tool panels: Input, output, saved history, sync state, citation notes.
- Legal/content renderer: Safe rich content with consistent typography.

## Motion and Interaction

Current app has some hover and transition behavior but no clearly documented motion system.

Recommended interaction rules:

- Use subtle transitions for hover, focus, dropdown open, accordion open, and card affordances.
- Avoid decorative motion that distracts from research tasks.
- Prefer responsive micro-interactions that clarify state.
- Respect `prefers-reduced-motion`.

## Accessibility Standards For Redesign

- Minimum WCAG AA contrast for text and controls.
- Visible focus states for every interactive element.
- Accessible names for icon-only buttons and social links.
- Semantic headings in correct order.
- Keyboard navigation through menus, forms, dashboard sidebar, and tool workflows.
- Error messages tied to form fields.
- Reduced-motion support.
- RTL/Arabic typographic QA where Arabic text appears.

