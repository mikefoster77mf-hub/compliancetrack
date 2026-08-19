# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-08-17

## Product Overview

**One-liner:** Automated vendor compliance and Certificate of Insurance (COI) tracking for General Contractors — daily monitoring, automated reminders, magic upload links, and an audit-ready dashboard.

**What it does:** ComplianceTrack automates the parts of vendor compliance that eat up project management time — monitoring certificates daily, reminding vendors before they expire, collecting COIs via a single link (no portal login), and surfacing compliance status in one live dashboard. You see what's compliant and what isn't without chasing anyone.

**Product category:** Vendor compliance / COI tracking SaaS for construction General Contractors. Sits on the "construction operations / risk management software" shelf — GCs find this when searching for "vendor compliance tracking," "COI management," "certificate of insurance tracker," or "construction compliance software."

**Product type:** B2B SaaS — multi-tenant web app (FastAPI + PostgreSQL + Nginx), per-project pricing.

**Business model:** Per-project / month subscription. Three tiers:
- $49/mo/project — up to 25 vendors, daily monitoring, reminders, magic links, dashboard, email support
- $79/mo/project — unlimited vendors, priority email support, early access & feature input (target "most popular")
- $99/mo/project — multi-project discount, dedicated onboarding call, priority + phone support

Early access members get a founding discount. Pricing shown is target — final may vary.

## Target Audience

**Target companies:** General Contractors (GCs), primarily small-to-mid-sized firms running multiple projects with multiple subcontractors/vendors. Single-project GCs are in scope but the value scales with project count.

**Decision-makers:** Owner / Principal / President (financial buyer + champion at small GCs); Operations Manager / Project Manager (day-to-day user, feels the pain directly); Risk / Safety Manager (compliance owner at larger GCs). At a small GC these are often the same person.

**Primary use case:** A GC is tired of chasing vendor COIs — certificates lapse unnoticed, audits cause last-minute scrambling, compliance tracking lives in an out-of-date spreadsheet, and someone on the team is manually emailing/calling vendors every renewal cycle.

**Jobs to be done:**
- Know at a glance which vendors/projects are compliant and which aren't
- Never miss a renewal or expiration again
- Survive an audit without scrambling to collect 20 certificates
- Stop the manual reminder/follow-up grind
- Get vendors to send COIs without portal friction

**Use cases:**
- Daily compliance monitoring across all active projects
- Automated vendor reminders (60/30/7-day cadence) before COI expiration
- Collecting new/renewed COIs from vendors via magic upload links
- Preparing for month-end or year-end audits with a clean, current compliance list
- Replacing the "compliance spreadsheet that's three versions behind"

## Personas

| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| Owner / Principal (small GC) | Liability, audit risk, not chasing paperwork | Doesn't have time to manually track 20+ vendor COIs per project | "Stop chasing paperwork — see compliance at a glance." Liability protection, time back. |
| Project Manager (doer) | Getting vendors to send COIs without nagging | Sends reminder emails and makes calls every renewal cycle — repetitive grind | "Automated reminders and magic upload links — the system does the follow-up." |
| Operations / Risk Manager (larger GC) | Audit readiness, clean records, compliance across projects | Spreadsheet sprawl — no one is sure which version is correct; audit = panic | "One live dashboard, audit-ready anytime. No spreadsheets." |

## Problems & Pain Points

**Core problem:** Vendor compliance (COI tracking) is a manual, reactive, high-stakes chore. Certificates expire without anyone noticing until it's a liability. Audits surface that reality all at once.

**Why alternatives fall short:**
- **Spreadsheets** — three versions behind reality, nobody sure which is correct, no automated alerting
- **Manual follow-up** — PM/owner sends reminder emails and makes calls every cycle; repetitive, error-prone, easy to miss one
- **General project management tools** — not built for COI-specific tracking; no expiration monitoring, no vendor upload flow, no compliance dashboard
- **"We just wing it"** — works until it doesn't; a missed renewal or failed audit is a liability problem, not a paperwork problem

**What it costs them:** Time (PM hours chasing vendors), liability exposure (lapsed COI = uninsured vendor on a job site), audit risk (scrambling when an auditor asks for current certs), stress (month-end/year-end compliance panic), reputation (auditors and clients notice).

**Emotional tension:** Stress/fear around liability and audits; frustration with the repetitive nagging; doubt about whether the spreadsheet is actually accurate; "I should be on top of this but I'm not."

## Competitive Landscape

**Direct:** Other vendor compliance / COI tracking SaaS for construction (smaller or niche tools, some vertical-compliance platforms). Falls short because: many are clunky, portal-login-heavy for vendors, or lack daily automated monitoring + magic upload links.

**Secondary:** General project management / document management tools used to track COIs (Procore, Buildertrend, generic PM tools). Falls short because: not purpose-built for COI lifecycle — no automated expiration monitoring, no vendor-facing upload link, compliance status isn't a first-class dashboard.

**Indirect:** Spreadsheets (Excel/Google Sheets), email + phone follow-up, doing nothing / "winging it." Falls short because: manual, reactive, no alerting, no single source of truth, audit = panic.

## Differentiation

**Key differentiators:**
- **Daily automated monitoring** — every certificate checked every day against its expiration; nothing slips because someone forgot to look
- **Magic upload links** — vendor uploads a COI via a single link; no portal login, no account creation, no back-and-forth; lands in the right project automatically
- **Automated reminder cadence** — vendors emailed 60/30/7 days before expiration; GC doesn't send the reminders
- **Live compliance dashboard** — every project, every vendor, green/yellow/red status; audit-ready anytime; one view, no spreadsheets
- **Per-project pricing** (not per-user) — scales with projects, not head count; predictable for GCs

**How we do it differently:** Purpose-built for the COI lifecycle from the ground up — not a PM tool with a compliance module bolted on. Vendor-facing flow (magic link) removes the biggest friction point (getting vendors to actually send the document). Daily automated checks replace the "did anyone look at the spreadsheet today?" question.

**Why that's better:** Less manual work for the GC/PM, fewer missed renewals, audit-ready at any moment, vendor upload is frictionless, compliance status is always current and visible.

**Why customers choose us:** Solves the exact headache GCs feel daily (chasing COIs, audit panic, spreadsheet sprawl) with a focused, lightweight tool rather than a heavy PM platform. Per-project pricing is predictable and scales with their business.

## Objections

| Objection | Response |
|-----------|----------|
| "We already use a PM tool / Procore for this." | ComplianceTrack is purpose-built for the COI lifecycle — daily automated monitoring, vendor magic upload links, and a compliance-specific dashboard. It complements or replaces the spreadsheet/paperwork layer without requiring a full platform migration. |
| "My vendors won't use another portal." | Magic upload links mean vendors don't log into anything — they click a link and upload the COI. No account, no portal friction. |
| "I'm not sure I have enough vendors to justify it." | Even a single project with 5-10 vendors carries real renewal/audit risk. Per-project pricing at $49-99/mo is modest relative to a PM's time and the liability of a missed COI. |
| "We've never had a problem — nothing's lapsed." | That's the goal. Most GCs haven't had a problem *yet* — until an auditor shows up or a vendor's COI lapses on a job site. The tool is insurance against that becoming a real event. |
| "How hard is it to set up?" | Add vendors, enter certificate info (or upload), and the system monitors from there. Magic upload links and reminders are automatic. Dashboard is live immediately. |

**Anti-persona:** GCs who genuinely have 1-2 vendors and no audits, or who have zero compliance concerns and no vendor COI requirement (rare in real construction). Also: GCs who want a full-suite PM platform replacement — ComplianceTrack is a focused compliance tool, not a project management system.

## Switching Dynamics

**Push:** Missed renewals / liability fear; audit panic; spreadsheet sprawl and uncertainty; repetitive manual follow-up grind; "I should be on top of this."

**Pull:** Daily automated monitoring (set it and forget it); automated reminders (the system does the nagging); magic upload links (vendors send COIs without friction); live audit-ready dashboard (one view, green/yellow/red); predictable per-project pricing.

**Habit:** Spreadsheet + email + phone calls; "we've never had a problem"; relying on memory and manual checklists; "it's not that big a deal until it is."

**Anxiety:** "Will my vendors actually use the magic link?"; "Is setup hard?"; "Do I really have a problem if nothing's lapsed yet?"; "Is this another tool my team has to log into?"; "What if it doesn't integrate with my existing workflow?"

## Customer Language

**How they describe the problem:**
- "Chasing certificates"
- "COIs expiring and nobody tells me"
- "Audit panic — scrambling to collect 20 certs"
- "Spreadsheet that's three versions behind"
- "I'm emailing and calling vendors every renewal cycle"
- "Vendor's insurance lapsed and we didn't know"

**How they describe us:**
- "Automated COI tracking"
- "Vendor compliance made easy"
- "Never chase a missing certificate again"
- "Audit-ready dashboard"
- "Magic link for vendors to send their COI"

**Words to use:** compliance, certificate of insurance, COI, vendor, General Contractor, GC, audit, expiration, renewal, dashboard, automated, reminders, magic link, per-project, risk, liability.

**Words to avoid:** jargon-heavy SaaS buzzwords ("streamline," "optimize," "innovative," "AI-powered" unless true); over-promising ("never miss" is fine as a value promise, but avoid fabricated stats); anything that sounds like a generic PM platform ("project management suite," "all-in-one").

**Glossary:**

| Term | Meaning |
|------|---------|
| COI | Certificate of Insurance — the document a vendor/subcontractor provides proving they carry required insurance coverage |
| GC | General Contractor — the firm running the project, responsible for vendor compliance |
| Vendor | Subcontractor or supplier doing work on a GC's project; required to carry insurance and provide a COI |
| Magic link | A single shareable URL a vendor clicks to upload their COI — no login, no portal account |
| Compliance dashboard | Live view of every project/vendor's compliance status (green/yellow/red) |
| Per-project pricing | Subscription priced per active project per month, not per user/seat |

## Brand Voice

**Tone:** Professional but approachable; clear, concrete, no fluff. GC-friendly — this is for people who run job sites, not SaaS nerds. Confident but not hype-y.

**Style:** Direct and conversational; short sentences; benefit-led; specific over vague. Speak to the pain (missed renewals, audit panic, chasing paperwork) and the outcome (audit-ready, set-it-and-forget-it, no chasing).

**Personality:** Reliable, practical, competent, straight-shooting. Think: a tool built by someone who understands construction operations, not a generic SaaS marketing department. "Vendor compliance, automated" — simple and honest.

## Proof Points

**Metrics:** (to be filled from real data post-launch — early access/waitlist signups, vendors tracked, reminders sent, etc.)

**Customers:** (initial: internal/boss validation — 20+ year GC said "that might go." Early access waitlist members.)

**Testimonials:** (to be collected — boss quote is a strong early signal: "that might go")

**Value themes:**
| Theme | Proof |
|-------|-------|
| Stop chasing paperwork | Daily automated monitoring + automated reminders replace manual follow-up |
| Audit-ready anytime | Live compliance dashboard — green/yellow/red, one view, no spreadsheets |
| Vendor upload without friction | Magic upload links — no portal login, no account creation |
| Predictable cost | Per-project pricing ($49-99/mo/project), not per-user; scales with the business |
| Set it and forget it | System monitors and reminds; GC sees status, not a to-do list |

## Goals

**Business goal:** National rollout to GCs — get ComplianceTrack in front of enough General Contractors across the country to build a real waitlist and launch customer base. Validate pricing and conversion from the landing page. Establish boss's endorsement as an early proof point.

**Conversion action:** Join the waitlist (name, email, optional company + project count). Secondary: learn more by scrolling the page (problem → solution → how it works → pricing).

**Current metrics:** Landing page live at https://localhost (mkcert HTTPS, Podman Compose stack). Waitlist API endpoint active (`/api/waitlist`). Pricing tiers defined ($49/$79/$99 per project/month). Boss validation obtained ("that might go"). Viewing on Android phone confirmed page looks good. Desktop app workaround in place (RDNA3 GPU crash → `--disable-gpu`).

## Changelog

- v1 (2026-08-17) — Initial context. Auto-drafted from codebase: landing page (index.html), pricing tiers, tech stack (FastAPI + PostgreSQL + Nginx, Podman Compose), features (daily monitoring, reminders, magic links, dashboard), SendGrid email reminders, waitlist flow. Incorporated boss validation and national rollout intent. Pending: real customer proof points, testimonials, conversion metrics, competitor names to fill in.
