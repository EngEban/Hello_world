# ResRef Site Map

## Primary Public Routes

| Route | Page | Purpose |
| --- | --- | --- |
| `/` | Home | Main platform landing page and entry point. |
| `/home` | Home alias | Alternate home route. |
| `/homepage` | Home alias | Alternate home route. |
| `/database` | Research Database | Browse/search research content and resources. |
| `/articles` | Database alias | Article-oriented access to database content. |
| `/advanced-search` | Advanced Search | Advanced resource search tool. |
| `/questionnaires` | Questionnaires Library | Browse scientific scales and questionnaires. |
| `/questionnaires-2` | Questionnaires alias | Legacy/alternate questionnaires route. |
| `/journal-finder` | Journal Finder | Tool for finding journals. |
| `/expert-consultation` | Expert Consultation | Service conversion page and request intake. |
| `/sample-size-calculator` | Sample Size Calculator | Guided calculator workflow for study planning. |
| `/reference-generator` | Reference Generator | Citation and reference generation tool. |
| `/research-opportunities` | Research Opportunities | Program/opportunity page and application intake. |
| `/join-our-team` | Join Our Team | Team application page. |
| `/about-us` | About ResRef | Mission, audience, values, trust narrative. |
| `/contact-us` | Contact Us | Contact channels and contact form. |
| `/contact` | Contact alias | Alternate contact route. |
| `/faq` | FAQ | Common questions. |
| `/terms-of-use` | Terms of Use | Legal terms. |
| `/privacy-policy` | Privacy Policy | Privacy information. |
| `/cookie-policy` | Cookie Policy | Cookie information. |
| `/sign-in` | Account Sign In | User authentication. |
| `/register` | Account Registration | New account creation. |
| `/account` | Account Dashboard | User account and workspace. |
| `/account/reset-password` | Password Reset | Password reset flow. |
| `/page/:slug` | Static Content | CMS-style static page detail. |
| `/:slug` | Dynamic Content | Dynamic post/page fallback. |
| `*` | Not Found | 404 page. |

## Dashboard Routes

| Route | Page | Purpose |
| --- | --- | --- |
| `/dashboard/login` | Dashboard Login | Admin sign-in using Django sessions and CSRF. |
| `/dashboard` | Dashboard Home | Admin overview, metrics, activity, quick actions. |
| `/dashboard/users` | Users | User management. |
| `/dashboard/posts` | Posts | Content management. |
| `/dashboard/media` | Media | Media library management. |
| `/dashboard/categories` | Categories | Content taxonomy management. |
| `/dashboard/tags` | Tags | Content tag management. |
| `/dashboard/authors` | Authors | Author profile and byline management. |
| `/dashboard/contacts` | Contacts | Contact inbox management. |
| `/dashboard/applications` | Applications | Team and opportunity application review. |
| `/dashboard/opportunities` | Opportunities | Research opportunity management. |
| `/dashboard/services` | Services | Service definition and request management. |
| `/dashboard/forms` | Forms | Forms overview and intake records. |
| `/dashboard/team` | Team | Team member management. |
| `/dashboard/newsletter` | Newsletter | Subscriber management. |
| `/dashboard/reports` | Reports | Operational analytics and export access. |
| `/dashboard/settings` | Settings | Site settings, roles, API docs. |
| `/dashboard/guide` | Guide | Admin guidance page. |

## Primary Navigation Structure

Topbar:

- WhatsApp: `+971 559977405`
- Email: `info@resref.com`
- Social links: Facebook, X, YouTube, Instagram, LinkedIn, Telegram, WhatsApp.

Header:

- Home
- Database
- Services
  - Expert Consultation
  - Sample Size Calculator
  - Reference Generator
  - Research Opportunities
- Join Our Team
- About Us
- Contact Us
- FAQ
- Search icon routes to Advanced Search
- Account icon routes to Account or Sign In

Footer:

- Newsletter subscription
- Brand summary
- Email and WhatsApp contact cards
- Social links
- Resources: Research Database, Advanced Search, Questionnaires, Articles
- Tools: Reference Generator, Sample Size Calculator, Journal Finder, Expert Consultation
- Community: Research Opportunities, Join Our Team, About ResRef, FAQ
- Legal: Terms of Use, Cookie Policy, Privacy Policy

## Key User Flows

### Student or Researcher Finds a Resource

1. Home or Database.
2. Search or browse categories.
3. Open resource/article detail.
4. Continue to related tools such as reference generator, sample size calculator, or expert consultation.

### User Uses a Research Tool

1. Enters tool from Services menu or homepage.
2. Inputs research details.
3. Receives result, citation, journal match, or calculation.
4. Optional sign-in to save workspace or continue later.

### User Requests Expert Support

1. Opens Expert Consultation.
2. Reviews service value and trust content.
3. Completes RequestForm.
4. Submission is stored in Django dashboard service/contact workflows.
5. Internal team reviews and follows up.

### User Applies for Opportunity or Team

1. Opens Research Opportunities or Join Our Team.
2. Reviews program/team details.
3. Completes structured application.
4. Admin reviews in Dashboard Applications/Team.

### Public User Creates Account

1. Opens Sign In or Register.
2. Authenticates with email/password or Google.
3. Uses Account page to manage profile and tool workspace state.

### Admin Manages Platform

1. Opens Dashboard Login.
2. Authenticates through Django session.
3. Uses dashboard sidebar for content, media, forms, contacts, services, settings, and reports.
4. Performs CRUD and review actions through dashboard API modules.

## Navigation Observations

- The current navigation is understandable and close to the original ResRef information model.
- Services are grouped in one dropdown, but Database subcategories are not deeply exposed in the primary nav.
- Advanced Search is treated as a search icon, which matches the requested direction.
- Dashboard has a separate admin IA, which is appropriate.
- Dynamic content fallback can make route ownership harder for designers and developers to reason about.

