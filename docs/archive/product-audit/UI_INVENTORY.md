# ResRef UI Inventory

## Layout Components

- `ResRefPublicLayout`: Public shell with header, footer, scroll-to-top, settings context.
- `DashboardLayout`: Protected admin shell with sidebar, topbar, search, quick actions, user chip, responsive mobile menu.
- `PublicLayout`: Legacy/simple public layout still present.

## Public Navigation Components

- `SiteHeader`: Topbar, brand, nav links, dropdown services menu, mobile menu toggle, search icon, account icon.
- `SiteFooter`: Newsletter band, brand panel, contact cards, social links, footer navigation, legal links.
- `SocialLinks`: Reusable social icon row.
- `ScrollToTop`: Route-change scroll behavior.

## Public Content Components

- `PageHero`: Reusable page hero.
- `SectionHeading`: Eyebrow, title, supporting text.
- `ResourceCard`: Reusable resource/service card.
- `PostCard`: Simple article card.
- `NewsletterSection`: Email subscription form.
- `ContactForm`: Contact intake form.
- `RequestForm`: Service/opportunity/team request form.
- `FaqList`: FAQ accordion/list.
- `ArabicTextEnhancer`: Runtime Arabic text detection/styling enhancement.
- `LoadingState`: Generic loading state.
- `ErrorMessage`: Generic error message.

## Account Components

- `AccountAuthPage`: Login/register card, pitch section, account form, Google sign-in option.
- `AccountPage`: Account profile, membership, workspace/access information.
- `AccountResetPasswordPage`: Password reset flow.
- `GoogleSignInButton`: Google Identity Services button mount.

## Public Page-Specific UI

### Home

- Hero section with brand message and primary calls to action.
- Service/tool cards.
- Audience/benefit sections.
- Partner/logo area.
- Trust and CTA sections.

### Database

- Search input and database actions.
- Resource/content grid.
- Article/resource cards.
- Category and content browsing patterns.

### Advanced Search

- Advanced search card.
- Keyword input.
- Type/category controls.
- Search results/messages.

### Questionnaires

- Page hero.
- Questionnaire/resource cards.
- Browse-oriented content sections.

### Journal Finder

- Journal finder card.
- Filter grid.
- Journal cards with badges and side actions.

### Expert Consultation

- Conversion-focused hero.
- Service benefits.
- Consultation request form.
- Trust and process sections.

### Sample Size Calculator

- Guided process cover.
- Workflow stepper.
- Research type cards.
- Assumption form fields.
- Live result preview.
- Sensitivity rows.
- Formula/method panels.
- Saved calculation history.
- Manuscript wording copy action.
- Account sync/sign-in prompt.

### Reference Generator

- Reference input workflow.
- Citation style controls.
- Generated output panels.
- Copy/download style actions.
- Account workspace integration.

### Research Opportunities

- Opportunity cards.
- Benefit cards.
- Application/request form.

### Join Our Team

- Team option cards.
- Application/request form.

### About Us

- Identity split layout.
- Metrics.
- Image panel and floating card.
- Mission card.
- Principle cards.
- Value cards.
- Audience cards.
- Trust CTA.

### Contact Us

- Contact channels.
- Contact form.
- Support/response information.

### FAQ

- FAQ list/accordion.
- Support CTA.

### Legal Pages

- Static legal content layout for terms, privacy, and cookies.

## Dashboard UI Components

- `AdminPageHeader`: Dashboard page heading and actions.
- `AdminNotice`: Success, error, info notices.
- `AdminPagination`: Table/list pagination controls.
- `DashboardPrimitives`: Dashboard cards, metrics, reusable admin primitives.
- `EmptyPanel`: Empty state panels.
- `StatusBadge`: Status labeling across forms, applications, posts, and users.
- `VisualContentEditor`: Rich/html editor surface with tabs and toolbar.

## Dashboard Page UI

### Dashboard Home

- Metrics grid.
- Dashboard cards.
- Quick links.
- Activity and guide areas.

### Users

- User table/list.
- Role/status controls.
- User edit form.
- Permission-oriented interface.

### Posts

- Content manager layout.
- List panel and editor panel.
- Filter/search bar.
- Taxonomy selectors.
- Visual/HTML editor.
- Featured image preview.
- Sticky save actions.

### Categories and Tags

- Taxonomy table.
- Taxonomy editor form.
- Delete/edit actions.

### Authors

- Author editor.
- Avatar preview.
- Author table.
- Profile link fields.

### Media

- Upload card.
- Search input.
- Media grid.
- Media cards with thumbnails and metadata.

### Contacts and Forms

- Inbox list.
- Status selects.
- Contact detail cards.
- Forms overview.

### Applications and Team

- Review list.
- Two-column review layout.
- Application detail form.
- Status and private notes.

### Opportunities and Services

- Service/opportunity CRUD forms.
- Status badges.
- Tables/lists.
- Request management.

### Reports

- Metric grid.
- Report cards.
- Export controls.

### Settings

- Settings sections.
- Form grids.
- Role and API documentation surfaces.

## Forms Inventory

- Contact form.
- Newsletter form.
- Request form used by consultation, opportunities, and team flows.
- Account login/register forms.
- Password reset forms.
- Dashboard login form.
- Dashboard content editor forms.
- Dashboard taxonomy forms.
- Dashboard author profile form.
- Dashboard media upload form.
- Dashboard application review form.
- Dashboard service/opportunity forms.
- Dashboard settings forms.

## Table and List Inventory

- Dashboard user tables.
- Posts/content list.
- Categories/tags tables.
- Authors table.
- Media grid.
- Inbox/contact list.
- Application review list.
- Service/opportunity tables/lists.
- Newsletter subscriber list.
- Report/export panels.

## Modal Inventory

No obvious reusable modal component was found in the current React source. Most flows use inline cards, forms, accordions, dropdowns, and page-level panels.

## Filter and Search Inventory

- Header search icon to Advanced Search.
- Database search.
- Advanced search fields.
- Journal finder filters.
- Dashboard global search.
- Dashboard content filter bars.
- Dashboard media search.
- Status filters for applications/contacts.

