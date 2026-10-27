# BUSINESS_RULES.md

# FinSight Business Rules

## Purpose

This document defines the financial intelligence rules used throughout FinSight.

These rules are considered the project's business logic and should remain consistent across all modules.

Any future implementation must follow these rules unless explicitly instructed otherwise.

---

# Core Philosophy

FinSight is NOT an expense tracker.

FinSight is a Financial Exposure Intelligence System.

The objective is to identify recurring financial commitments that reduce a user's future financial flexibility.

The project focuses on commitments rather than spending.

---

# What is a Financial Commitment?

A financial commitment is any payment that creates an obligation for future payments.

Commitments reduce the user's available financial capacity.

Current commitment types:

- Subscription
- EMI
- Buy Now Pay Later (BNPL)

Future commitment types may be added later.

# Transaction Status and Amount Semantics

Transaction status is classified consistently across profile reliability,
history, and commitment payment summaries:

- `success`, `succeeded`, `successful`, `completed`, `paid`, and `settled`
  are successful.
- `failed`, `declined`, and `rejected` are failed.
- `pending`, `processing`, and `in_progress` are pending.
- Blank, missing, and any other status are unknown; they are not counted as
  successful.

Transaction amounts remain signed so legitimate refunds and credits are not
discarded. Commitment rows are different: negative subscription, EMI, or BNPL
amounts are treated as zero when calculating commitment burden, so malformed
rows cannot reduce exposure or commitment totals.

---

# Why Food, Fuel and Shopping are NOT Commitments

Expenses like

- Food
- Fuel
- Shopping
- Entertainment
- Miscellaneous

are variable expenses.

Although necessary, they are not contractual recurring obligations.

Therefore they are excluded from Exposure Score calculations.

They may appear separately in analytics in future versions.

---

# Essential Expenses

Examples

- Rent
- Electricity
- Water
- Internet
- Insurance

These are recurring living expenses.

They are important for financial planning but are intentionally kept separate from commitment exposure.

Future versions may introduce an Essential Expense Analysis module.

---

# Subscription Rules

Subscriptions are recurring payments.

Examples

- Netflix
- Spotify
- ChatGPT Plus
- Microsoft 365
- Adobe Creative Cloud

Rules

- Detect recurring merchant patterns
- Detect AutoPay
- Detect newly started subscriptions
- Detect possible free trial conversion
- Calculate monthly commitment
- Generate subscription insights

---

# Trial-to-Paid Detection

A subscription may be considered a trial conversion when:

- Initial payment is zero or promotional
- Followed by recurring paid transactions
- Same merchant
- Reasonable confidence threshold

Trial detection should never create false positives.

---

# EMI Rules

EMIs represent mandatory financial commitments.

Examples

- Home Loan
- Car Loan
- Education Loan
- Gold Loan
- Consumer Electronics
- Lifestyle Loan

Rules

- Group EMI payments by merchant
- Infer loan type
- Calculate monthly EMI burden
- Calculate annual burden
- Generate payment analytics
- Detect heavy EMI portfolios

---

# BNPL Rules

BNPL represents installment-based borrowing.

Examples

- Simpl
- LazyPay
- Paytm Postpaid
- Amazon Pay Later

Rules

- Group by provider
- Detect installment count
- Detect active commitments
- Calculate monthly burden
- Detect multiple provider usage
- Detect provider concentration

---

# Exposure Score

Exposure Score represents the percentage of monthly financial capacity already committed.

Formula

Exposure Score =
Monthly Commitments
/
Monthly Financial Capacity

×100

Exposure Score may exceed 100%.

Example

Monthly Capacity

₹50,000

Monthly Commitments

₹60,000

Exposure Score

120%

This indicates the user has overcommitted beyond monthly capacity.

---

# Financial Health

Financial Health is NOT equal to Exposure Score.

Health considers multiple dimensions.

Including

- Exposure
- Payment Success
- AutoPay Coverage
- Commitment Diversity
- Financial Flexibility
- Recommendation Impact

Health Categories

Excellent

Healthy

Moderate

Needs Attention

Critical

---

# Recommendations

Recommendations should always be constructive.

Never simply warn the user.

Recommendations should explain

- Why
- Expected benefit
- Estimated monthly saving
- Estimated annual saving
- Estimated exposure reduction
- Estimated implementation effort

Possible effort levels

- Very Easy
- Easy
- Medium
- High

---

# Forecast

Forecast is separate from current exposure.

Future commitments must NEVER modify the current Exposure Score.

Forecast may include

- Upcoming subscription renewals
- Trial conversion reminders
- Future EMI installments
- Future BNPL installments

Forecast exists only to prepare the user.

---

# Explainability

Every important score should be explainable.

The user should understand

- why a score exists
- which commitments contribute
- what actions can improve it

Black-box calculations should be avoided.

---

# Real-Time Updates

Whenever transaction data changes

- Exposure Score
- Financial Health
- Forecast
- Recommendations

must be recalculated automatically.

Future implementations may use caching for performance.

---

# Dashboard Philosophy

Dashboard should prioritize important information.

Priority

1. Financial Health
2. Exposure Score
3. Active Commitments
4. Critical Recommendations
5. Forecast
6. Detailed Analytics

Do not overwhelm users with unnecessary information.

---

# AI Development Rules

Future AI implementations must

- Preserve these business rules
- Never redesign financial calculations
- Extend existing logic instead of replacing it
- Keep calculations deterministic
- Maintain explainability
- Preserve backward compatibility

Business rules take precedence over implementation convenience.