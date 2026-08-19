# Payment Processor Analysis — ComplianceTrack
# Prepared: 2026-08-18 (research done today; action tomorrow evening)

## The question
Per-project subscription billing at $49–$99/mo/project. Need:
- Accept recurring credit card payments
- Payout to a bank account
- Reasonable integration effort on a FastAPI backend
- Keep taxes/compliance from becoming a second job

**Founder context (for decisions below):** US-based, South Carolina. SC state sales tax is 6% + local option taxes (up to 1% additional in some jurisdictions), so buyer location matters for what's owed. A SC-based US bank account works for USD payouts from any of the three options below. For Stripe-direct, SC Department of Revenue + local jurisdictions are the filing responsibility (nexus + returns). For MoR providers (Paddle, Lemon Squeezy), they collect and remit SC state + local tax on your behalf.

---

## The three candidates

### Stripe (direct processor, you are the Merchant of Record)
- **Fees:** ~2.9% + $0.30/transaction base, plus Stripe Billing (0.7% of subscription volume), plus Stripe Tax (0.5%/txn) if you use it, plus international/FX fees, plus dispute fees. Adds up fast when you layer them.
- **Bank payout:** Needs a bank account in a country matching the settlement currency; separate bank per currency. First payouts delayed 7–14 days. USD settlement → US bank account.
- **Entity/KYC:** Verifies legal entity + owner. Accepts sole proprietorships and single-member LLCs, but sole props must provide personal tax ID (SSN/ITIN in US). US accounts need a US-based representative/address for unregistered businesses. Full KYC required.
- **Tax:** Stripe Tax calculates sales tax/VAT/GST in 100+ countries, but filing/remittance is via third-party partners (TaxJar for US, Taxually globally, OSS for EU). YOU remain responsible for filing/remittance unless you use Stripe Managed Payments (which can make Stripe the MoR where supported).
- **Ease:** Most flexible, richest APIs, deepest control. But full B2B billing + tax automation takes longer (days to weeks) because of KYC, tax setup, webhook handling.
- **Statement:** Customer sees YOU as the seller (your business name on their card statement).
- **Best fit:** You want maximum control, lowest per-transaction cost, native multi-currency, custom B2B billing features, and you're willing to handle (or automate) tax filing.

### Paddle (Merchant of Record — they sell for you)
- **Fees:** ~5% + $0.50/transaction (no monthly fee). Bundles payment processing + tax/VAT collection + remittance + fraud protection + chargeback handling.
- **Bank payout:** USD, EUR, GBP, AUD, CAD. Bank transfers for EUR/GBP/USD. SWIFT fees if payout currency ≠ bank currency.
- **Entity/KYC:** Business verification for registered businesses; not required for individuals/sole traders. Identity verification for individuals + at least one owner for registered businesses. Can be quick for sole traders.
- **Tax:** As MoR, Paddle registers, collects, files, and remits VAT/sales tax in jurisdictions where it operates — seller of record in 100+ jurisdictions. You don't file; they do.
- **Ease:** Hosted checkout (Paddle.js), SDKs, server APIs, sandbox. Less custom code than a full Stripe Billing build. Hosted checkout needs live-account approval (sandbox available). Supports B2B invoicing, net terms, annual contracts.
- **Statement:** Customer sees PADDLE on their statement (they're the seller of record).
- **Best fit:** Rapid launch, minimal payments ops, global VAT/sales-tax handled for you, willing to pay ~5% + $0.50 for the convenience, OK with Paddle appearing as seller on statements.

### Lemon Squeezy (Merchant of Record — they sell for you)
- **Fees:** ~5% + $0.50/sale (plans vary) + small surcharges for international/PayPal and subscription billing add-ons. Acts as MoR; deducts collected taxes from payouts.
- **Bank payout:** Transactions settle in USD by default (can select payout currency). Payouts twice monthly after 13-day hold, $50 minimum. Bank transfers + PayPal; bank payouts in many countries, PayPal widely supported.
- **Entity/KYC:** KYC/KYB checks before store activation — store must pass verification to confirm business validity and compliance.
- **Tax:** As MoR, collects and remits VAT/sales tax, supports tax-inclusive pricing, OSS automation where applicable. Tax amounts deducted from payouts.
- **Ease:** REST API, JS + Laravel SDKs, hosted checkout + overlay, clear webhooks. Minimal integration: create product/variant, generate checkout URL or overlay, validate webhooks, sync subscriptions. Can be built in hours; custom checkout in a day or two.
- **Statement:** Customer sees LEMON SQUEEZY on their statement.
- **Best fit:** Simplest integration, MoR convenience, bi-monthly payouts with $50 minimum, OK with LS appearing as seller on statements.

---

## Bank account piece (common to all three)

All three ultimately payout to a bank account. The specifics:

- **Stripe:** Bank account in the settlement currency's country. USD → US bank. If you're a US person (sole prop or LLC), a standard US business or personal checking account works. Stripe also supports separate accounts per currency.
- **Paddle:** USD/EUR/GBP/AUD/CAD. SWIFT fees if your bank is in a different currency country.
- **Lemon Squeezy:** USD settlement default. Bank transfers in many countries; PayPal widely supported as fallback.

**What you need on the bank side (most likely path if you're US-based):**
- A US bank account (business checking if you have an LLC; personal checking can work for a sole prop depending on the processor's rules) to receive USD payouts.
- If you're NOT US-based, the research has an evidence gap — the founder's country of residence determines which processors/payout currencies are available and what KYC docs are needed.

**What you need on the entity side:**
- Sole proprietorship: simplest. You can often start as a sole prop with just your SSN. Stripe accepts sole props (with personal tax ID). Paddle is friendly to individuals/sole traders. Lemon Squeezy requires KYC/KYB but individuals can pass.
- Single-member LLC: slightly more formal, gives you a business name and EIN. All three support it.
- If you haven't formalized an entity yet, sole prop is the lowest-friction starting point (assuming US).

---

## My take for ComplianceTrack

Given where you are (first SaaS, solo, per-project SaaS, $49–$99/mo, national GC rollout, "wants live today" energy):

**Option A — Paddle or Lemon Squeezy (MoR path):**
- Fastest to "accepting payments" because tax/VAT/chargebacks are their problem, not yours.
- Hosted checkout means less custom code on your FastAPI backend.
- Trade-off: ~5% + $0.50/transaction (vs Stripe's lower base rate), and the customer sees Paddle/LS on their statement (which can matter for enterprise procurement, but for small/mid GCs probably not a big deal).
- Lemon Squeezy is probably the simplest integration (hosted overlay/checkout + webhooks, hours to a day). Paddle is close behind and has stronger B2B invoicing/net-terms features.
- Payouts: LS is bi-monthly with $50 minimum + 13-day hold; Paddle is more frequent but currency SWIFT fees can bite if your bank isn't in a supported currency.

**Option B — Stripe (direct, you're the MoR):**
- Lower per-transaction cost at scale, most control, customer sees your business name.
- You own tax filing/remittance (Stripe Tax helps calculate, but you still file — unless Managed Payments is available to you).
- More KYC paperwork up front (entity docs, owner tax IDs, US address/representative).
- More dev work to wire up subscriptions, webhooks, dunning, tax.
- Best if you plan to scale hard and want to keep more of each dollar and control the whole flow.

**Rough recommendation (to decide tomorrow):**
- If "fast and simple, let someone else handle tax" wins → **Lemon Squeezy** (simplest integration) or **Paddle** (stronger B2B features, slightly more established MoR).
- If "lowest cost, my brand on the statement, I'll handle tax via automation" wins → **Stripe** (with Stripe Billing + Stripe Tax, and plan for KYC/onboarding time).

---

## Open questions to resolve tomorrow (before picking)

1. **Where are you based (country of residence)?** This drives payout availability, KYC rules, and whether Stripe Managed Payments is an option. The research has an evidence gap here — need your country.
2. **Do you have a business entity yet (sole prop vs LLC), and a bank account ready to receive payouts?** If not, sole prop + a personal/business checking account is the lowest-friction start (assuming US).
3. **How important is your business name appearing on the customer's card statement?** MoR providers (Paddle/LS) put their name there; Stripe puts yours.
4. **Expected monthly volume / how manyprojects signing up?** At low volume, the ~5% + $0.50 MoR fee is a small absolute number and buys you tax simplicity. At higher volume, Stripe's lower rate starts to matter more.
5. **Do you want to accept international GCs (EUR/GBP/etc.) from day one, or US-only for launch?** MoR handles international tax automatically; Stripe requires more setup for multi-currency + tax filing in other jurisdictions.

---

## Research sources (Tavily, 2026-08-18)

- Stripe payouts: https://stripe.com/resources/more/payouts-explained ; https://docs.stripe.com/payouts
- Stripe US account requirements: https://support.stripe.com/questions/requirements-for-having-a-us-stripe-account
- Stripe identity verification: https://docs.stripe.com/connect/identity-verification
- Stripe MoR / Managed Payments: https://stripe.com/resources/more/merchant-of-record ; https://docs.stripe.com/payments/managed-payments
- Stripe Tax pricing: https://stripe.com/tax/pricing
- Stripe fees breakdown: https://freemius.com/blog/stripe-transaction-fees-real-cost
- Paddle API: https://developer.paddle.com/api-reference
- Paddle currencies: https://developer.paddle.com/concepts/sell/supported-currencies
- Paddle business verification: https://www.paddle.com/help/start/account-verification/what-is-business-verification
- Paddle hosted checkout: https://developer.paddle.com/paddle-js/about/hosted-checkout
- Paddle pricing: https://churntools.com/blog/paddle-pricing
- Paddle VAT handling: https://www.paddle.com/help/sell/tax/how-paddle-handles-vat-on-your-behalf
- Paddle chargebacks: https://www.paddle.com/help/manage/risk-prevention/understanding-chargebacks-with-paddle
- Lemon Squeezy API: https://docs.lemonsqueezy.com/api
- Lemon Squeezy getting paid: https://docs.lemonsqueezy.com/help/getting-started/getting-paid
- Lemon Squeezy MoR: https://docs.lemonsqueezy.com/help/payments/merchant-of-record
- Lemon Squeezy sales tax/VAT: https://docs.lemonsqueezy.com/help/payments/sales-tax-vat
- Lemon Squeezy activate store: https://docs.lemonsqueezy.com/help/getting-started/activate-your-store
- Lemon Squeezy getting started guide: https://docs.lemonsqueezy.com/guides/developer-guide/getting-started
- Lemon Squeezy pricing breakdown: https://www.swell.is/content/lemon-squeezy-pricing
- Lemon Squeezy bank payouts expansion: https://www.lemonsqueezy.com/blog/new-bank-payouts
