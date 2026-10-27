# VERIFICATION.md

# FinSight Verification Guide

This document defines the mandatory verification process for every implementation.

No feature is considered complete until every applicable verification step passes.

---

# Verification Philosophy

Implementation is only 50% of the work.

The remaining 50% is verification.

Every new feature must prove that

- it works
- it follows business rules
- it does not break existing functionality
- it preserves architecture

---

# Mandatory Verification Workflow

Every completed implementation must follow this order.

1.

Static Validation

↓

2.

Compilation

↓

3.

Swagger Verification

↓

4.

HTTP Endpoint Testing

↓

5.

Business Rule Validation

↓

6.

Cross Module Validation

↓

7.

Documentation Update

↓

8.

Phase Freeze

---

# Step 1

Static Validation

Verify

- imports
- typing
- schemas
- service wiring
- router registration

No unresolved imports.

No syntax errors.

---

# Step 2

Compilation

Run

python -m compileall app

Expected

No compile errors.

---

# Step 3

Swagger Verification

Open

/docs

Verify

- endpoint appears
- schema appears
- request examples
- response examples
- descriptions
- tags

---

# Step 4

HTTP Verification

Verify

Successful request

Expected

HTTP 200

Verify

Unknown User

Expected

HTTP 404

Verify

Validation Error

Expected

HTTP 422

Unexpected failures

Expected

HTTP 500 only for genuine internal errors.

---

# Step 5

Business Rule Validation

Confirm

Business calculations are correct.

Examples

Exposure

Financial Health

Recommendations

Forecast

Subscription Detection

Trial Detection

Loan Classification

BNPL Detection

AI generated code must never change verified calculations.

---

# Step 6

Cross Module Validation

Ensure

Subscription

↓

EMI

↓

BNPL

↓

Exposure

continue working together.

No module should break another module.

---

# Step 7

Performance Check

Avoid

- duplicate calculations
- repeated dataset loading
- unnecessary dataframe copies
- repeated filtering
- unnecessary loops

Prefer

Reuse

Caching where appropriate

Shared calculations

---

# Step 8

Documentation

Update

PHASE_HISTORY.md

If architecture changes

Update

ARCHITECTURE.md

If calculations change

Update

BUSINESS_RULES.md

If API changes

Update

API_GUIDE.md

---

# Smoke Test Checklist

Minimum verification

Dataset API

PASS

Subscription API

PASS

EMI API

PASS

BNPL API

PASS

Exposure API

PASS

Health API

PASS

Dashboard API (future)

PASS

---

# Required Verification Summary

Every implementation must finish with

## Files Modified

List every modified file.

---

## Business Rules

Explain

- new rules
- changed rules
- preserved rules

---

## Verification

List

Compile

Swagger

HTTP

Smoke Test

Business Validation

---

## Known Limitations

List remaining limitations.

Never hide known issues.

---

## Future Improvements

Optional improvements.

Must not block the current release.

---

# Release Checklist

Before freezing a phase

All APIs return expected responses

Compile succeeds

Swagger works

Business rules validated

Documentation updated

No architecture violations

No duplicated logic

No unfinished TODOs

No debug code

No unused imports

No broken endpoints

---

# Definition of Done

A feature is considered complete only when

Implementation

✓

Compilation

✓

Verification

✓

Documentation

✓

Business Validation

✓

Architecture Preserved

✓

Only then may the phase be marked

COMPLETED

and

FROZEN.