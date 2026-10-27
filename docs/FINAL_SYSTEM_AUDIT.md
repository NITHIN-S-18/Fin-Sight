# FinSight Final System Audit

## 1. Audit Metadata

- **Audit date:** 2026-09-26
- **Branch:** `integration`
- **Latest commit at audit start:** `e7da5d3 Complete backend security intelligence and API refinement`
- **Scope:** Full repository audit after Tasks 1–6, including backend, frontend,
  database/migrations, configuration, dependencies, tests, documentation,
  model artifacts, data handling, and runtime verification boundaries.
- **Audit method:** Read-only source/configuration inspection, dependency and
  import tracing, targeted probes, existing test execution, compilation, build,
  migration graph inspection, and diff review.
- **Application code changed during audit:** No. Only this audit document was
  created.

The working tree was already dirty before this audit. Existing uncommitted work
includes Tasks 1–6 changes and the Task 6 deletion of confirmed orphaned
frontend pages. Those changes were not reverted or altered.

## 2. Executive Summary

FinSight has a functioning authenticated FastAPI/React financial-intelligence
flow with JWT-scoped user identity, CSV ingestion, append/deduplication,
profile synchronization, deterministic commitment/exposure calculations,
dashboard/history data, What-If simulation, Copilot orchestration, Settings
operations, and two-user isolation regression coverage.

The backend suite passed **68 tests**, Python compilation passed, the frontend
production build passed, and `git diff --check` passed. These results verify
the tested paths only; they do not establish complete browser, external-provider,
production-database, or production-concurrency correctness.

The most important open issues are:

1. **High:** Digital Twin simulator clamps exposure to 100%, contradicting the
   documented business rule and the uncapped Exposure Engine.
2. **High:** Session restoration sets `hasData=true` after `/auth/me` without
   checking imports or transactions, so an empty account can bypass onboarding
   after refresh.
3. **High:** Forgot-password is simulated in the frontend despite no reset
   backend capability.
4. **High:** Settings displays fabricated/stale transaction metadata when its
   requests fail or return no data.
5. **Medium:** Negative CSV amounts are accepted and can affect commitment
   calculations.
6. **Medium:** Existing JWTs remain valid after password change.
7. **Medium:** Financial context is sent to Gemini when enabled; consent,
   provider retention, redaction policy, and regional handling are not
   implemented.
8. **Medium:** The configured `copilot_llm_provider` setting is ignored by the
   provider factory.

No critical tenant-isolation vulnerability was found in the inspected
authenticated financial endpoints. Real browser E2E and real Gemini/Ollama
runtime behavior remain unverified in this environment.

## 3. System Architecture

### Backend

- FastAPI application under `backend/app`.
- Versioned API routes under `/api/v1`.
- Service-layer business logic with endpoints kept comparatively thin.
- SQLAlchemy models and repositories.
- DatasetService as the transaction-data access boundary.
- Deterministic Subscription, EMI, BNPL, Exposure, Dashboard, History,
  Simulator, Copilot, and ML services.
- Centralized middleware and error handling.

### Frontend

- Vite React application under `frontend/src`.
- `frontend/src/main.tsx` mounts `frontend/src/app/App.tsx`.
- `App.tsx` is a local state-machine router rather than React Router.
- Unauthenticated states: landing, login, register, forgot-password.
- Authenticated states: upload/onboarding or the AppShell.
- AppShell pages: Dashboard, Transactions, Commitments, Intelligence, What-If,
  Assistant/Copilot, and Settings.
- Sidebar navigation is defined in `components/AppSidebar.tsx`.

### Database

- SQLAlchemy models for authentication users, financial users, transactions,
  financial profiles, and import history.
- SQLite is the local default in `Settings`; the effective local configuration
  inspected during audit used PostgreSQL settings.
- Alembic migrations form one linear head through revision 009.

### Authentication

```text
register → AuthUser → login → JWT(sub, exp)
         → sessionStorage → /auth/me
         → AuthUser → financial User
         → protected API calls
```

### ML

The ML layer consumes backend-derived features and saved model artifacts when
available. It is additive and does not replace deterministic financial
services. Model training labels include documented rule-derived targets.

### Simulator

```text
JWT user
  → ExposureService baseline
  → DigitalTwinEngine clone
  → ScenarioBuilder
  → ComparisonEngine
  → SimulationResponse
```

Simulations are intended to be in-memory and non-persistent.

### Copilot

```text
JWT user
  → DatasetService empty-account guard
  → ExposureService snapshot
  → IntentDetector / IntentRouter
  → Digital Twin and DecisionEngine when needed
  → ResponseGenerator
  → Gemini → Ollama → deterministic explanation fallback
```

The LLM is intended to explain trusted backend values, not calculate them.

## 4. End-to-End Data Flow

### Authenticated transaction flow

```text
React UploadPage
  → POST /api/v1/transactions/upload
  → JWT-linked AuthUser/User
  → CSV validation and normalization
  → transaction ownership and fingerprint deduplication
  → persisted Transaction rows
  → FinancialProfileSyncService over the complete ledger
  → Dashboard / Commitments / ML / History / Copilot
```

### Financial intelligence flow

```text
persisted authenticated transactions
  → DatasetService
  → SubscriptionService + EmiService + BnplService
  → ExposureService
  → Dashboard, History, What-If, Copilot
```

### Verification status

- Authenticated two-user flow: **TESTED** by integration tests.
- Browser registration/upload/navigation flow: **UNVERIFIED**.
- Production database behavior: **PARTIALLY VERIFIED**; migration graph was
  inspected, but a disposable fresh-database migration was not run during this
  read-only audit.

## 5. Authentication & Authorization

### Verified implementation

- Passwords use salted `hashlib.scrypt`.
- Password verification uses constant-time `hmac.compare_digest`.
- JWTs contain `sub` and `exp` and are signed with configured algorithm/secret.
- Expired/invalid/missing bearer credentials produce `401`.
- `/auth/me` resolves the AuthUser from the JWT subject.
- The financial User is linked through `AuthUser.financial_user` or created as
  `AUTH{auth_user.id:08d}`.
- Financial endpoints use `get_current_financial_user`.
- Path IDs are checked by `require_financial_user`.
- Uploads pass both authenticated account and financial-user identity to the
  import service.
- Frontend stores access tokens in `sessionStorage`, not localStorage.
- Frontend logout clears the token and local authentication state.
- Registration performs login and authenticated-user restoration.

### Tenant isolation

The following authenticated surfaces were inspected and/or covered by tests:

- Dataset user and transaction access
- Dashboard
- Dashboard history
- Subscriptions
- EMI
- BNPL
- Exposure
- ML endpoints
- What-If simulator
- Copilot query and suggestions
- Upload and import history
- Profile update
- Password change
- Export

The path-based endpoints reject a foreign user ID with `403`. The simulator
and history derive identity directly from JWT-linked user state. Copilot checks
the optional deprecated body ID and path suggestion ID against the current user.

### Open authentication findings

- Existing JWTs are not revoked after password change.
- No refresh-token or server-side session-revocation model exists.
- No issuer/audience claims were found.
- No login rate limiting was found.
- Session restoration has an empty-account state defect described in Finding
  F-002.

## 6. CSV Ingestion & Deduplication

### Verified behavior

- Multipart UTF-8 CSV upload.
- Required `transaction_date` and `amount` columns.
- Invalid dates, malformed rows, duplicate headers, unsupported schemas, and
  non-finite numeric values are handled.
- Uploads append to the authenticated ledger.
- Fingerprints include authenticated user, normalized date, optional source ID,
  merchant, description, and amount.
- Duplicate rows within and across uploads are covered by tests.
- Import history is persisted per authenticated account.
- Accepted transactions trigger profile synchronization over the complete
  persisted ledger.
- Existing transaction data is not replaced by a later upload.

### Open ingestion concern

Negative amounts are finite and therefore accepted. Subscription, EMI, and BNPL
services use signed values in burden calculations. The intended treatment of
refunds/credits versus invalid negative commitment inputs is not explicitly
enforced at ingestion.

The requested conceptual sequence `Upload A → Upload B → Upload A again` is
covered in substance by the ingestion regression tests; no new audit test was
created.

## 7. Financial Calculations

The following deterministic services remain the financial source of truth:

- SubscriptionService
- EmiService
- BnplService
- ExposureService
- DashboardService
- HistoryService
- DecisionEngine
- ScenarioBuilder/DigitalTwinEngine for simulation

### Observed formulas and semantics

- Exposure Engine uses monthly commitments divided by monthly financial
  capacity times 100.
- Exposure is allowed to exceed 100% in the authoritative Exposure Engine and
  documented business rules.
- Financial health is a separate multi-factor deterministic result.
- Available capacity is derived from financial capacity and commitments.
- History derives monthly income, spending, commitments, exposure, and available
  capacity from successful transaction dates.
- History health is explicitly marked as a transaction-only approximation.
- Missing history months are not fabricated.
- Commitments are classified as subscriptions, EMI, and BNPL; variable spending
  is separate from commitment exposure.

### Cross-module issue

The simulator's Digital Twin recalculation clamps exposure to 100%, unlike the
Exposure Engine. This creates an observable What-If inconsistency for
over-capacity users. See F-001.

## 8. FinancialProfile Synchronization

The Task 1 synchronization path is:

```text
accepted persisted transactions
  → FinancialProfileSyncService
  → complete authenticated ledger aggregation
  → FinancialProfile fields
  → ML feature construction
```

The focused ingestion tests cover profile synchronization, multiple uploads,
duplicates, commitments, exposure, and ML visibility. The implementation
recomputes from all persisted user transactions rather than only the latest
upload.

A semantic limitation remains: profile success-rate handling counts only
explicit success markers, while other services treat some blank/unknown
statuses differently. See F-012.

## 9. ML / Intelligence

### 9.1 Distress

- Features are produced through the backend ML feature pipeline.
- The model artifact and preprocessing path are used when available.
- Distress targets are documented as rule-derived/synthetic rather than
  independently observed outcomes.
- Empty authenticated accounts are rejected before fabricated model output.

**Production feature consistency:** partially verified through synchronization
and regression tests.

**Training/validation quality:** limited; rule-derived labels constrain the
meaning of reported accuracy.

### 9.2 Exposure Forecast

- Uses persisted profile/transaction-derived features and saved preprocessing/
  model metadata.
- The deterministic Exposure Engine remains separate from forecast output.
- Empty-account behavior is guarded.

**Production feature consistency:** partially verified.

**Forecast accuracy/calibration:** not established by this audit.

### 9.3 Behaviour / Persona

- Persona inference is part of the fused intelligence pipeline.
- Inputs come from backend-derived features, not frontend-provided metrics.
- Cluster/persona semantics depend on the saved model and training distribution.

**Production feature consistency:** partially verified.

**Persona stability, drift handling, and external validity:** unverified.

### 9.4 Anomaly Detection

- Isolation Forest output includes decision-score semantics and anomaly
  explanation metadata.
- The score is not a probability.
- Empty accounts are not given fabricated anomaly results.
- Validation metadata records contamination and threshold information.

**Inference path:** tested.

**Calibration and production drift behavior:** unverified.

### ML quality status

- Rule-derived distress/exposure targets: **STILL PRESENT / DOCUMENTED**.
- Preprocessing leakage concern from earlier work: **FIXED** in the inspected
  pipeline, where preprocessing state is fitted after splitting.
- KMeans validation metadata: **FIXED/PARTIALLY VERIFIED**.
- IsolationForest validation metadata: **FIXED/PARTIALLY VERIFIED**.
- Confidence calibration: **NOT VERIFIED** as statistical calibration.
- Feature drift monitoring: **NOT FOUND**.
- Saved artifacts: the expected model directory was present but no model files
  were observed during the audit inventory; bootstrap behavior is therefore a
  deployment concern.

## 10. Dashboard

- Current DashboardPage is active and calls the authenticated dashboard API.
- Cards and recommendations use backend response values.
- Loading, retry, error, and onboarding states exist.
- Upload navigation is connected to authenticated UploadPage.
- Dashboard calls the historical endpoint separately.
- History failure does not erase the primary dashboard response.

The main dashboard defect is the restored-session data-state error in F-002.

## 11. Historical Dashboard

- `GET /api/v1/dashboard/history` is authenticated.
- HistoryService uses transaction dates, not upload timestamps.
- Successful transaction records are aggregated by observed calendar month.
- Months without transactions are not invented.
- Exposure and capacity are calculated only when monthly income is available.
- The response identifies the transaction-only health approximation.
- DashboardPage renders returned history points and has history loading/error/
  empty states.

Multi-month and empty-history behavior is covered by history tests. Browser
rendering is unverified.

## 12. What-If Simulator

### Verified path

```text
WhatIfPage
  → simulatorApi.simulate()
  → POST /api/v1/simulator/simulate
  → JWT-linked current user
  → SimulatorService
  → ExposureService + DigitalTwinEngine + ScenarioBuilder
  → ComparisonEngine
  → backend response rendered by WhatIfPage
```

- No frontend financial formulas are used as the result source.
- Scenario controls map to backend-supported scenario names.
- JWT is sent through the shared API client.
- Loading prevents concurrent submission.
- Errors clear stale results and do not fabricate local values.
- Empty/unavailable backend data is surfaced.
- The simulator does not persist scenario changes.
- The frontend exposes a narrower subset of backend scenarios; this is a
  capability limitation, not an API mismatch.

### Open simulator issue

Over-100% exposure is clamped to 100% inside Digital Twin recalculation,
contradicting the business rule. See F-001.

## 13. Copilot

### 13.1 Deterministic layer

- IntentDetector is keyword/rule based.
- IntentRouter maps to deterministic engines.
- CopilotService builds snapshots through ExposureService.
- DecisionEngine produces recommendations and confidence.
- ResponseGenerator produces deterministic explanations.
- Empty accounts are rejected before Copilot context construction.

### 13.2 Gemini

- Official `google-genai` dependency is declared.
- `GEMINI_API_KEY` is backend configuration.
- Default model is `gemini-3.8-flash`.
- A bounded SDK HTTP timeout is configured.
- Provider exceptions and empty/malformed content produce provider failure.
- Gemini is intended to receive only compact trusted backend-derived context.

### 13.3 Ollama

- Local `/api/chat` adapter exists.
- Base URL, model, and timeout are configurable.
- No Ollama API key is required.
- Provider response parsing is bounded and failure returns `None`.

### 13.4 Fallback behavior

The intended chain is:

```text
Gemini → Ollama → deterministic response
```

Mocked tests cover provider success, Gemini failure to Ollama, and both-provider
failure to deterministic output. No real external Gemini or Ollama call was
made during this audit.

### 13.5 Security

The provider payload inspected contains backend-derived financial snapshot and
decision fields, not passwords, JWTs, database credentials, or reference-user
rows. The API key is not included in response models or prompt context.

Open concerns:

- The effective local environment has LLM enabled and a Gemini key configured.
- No consent, retention, redaction, regional-storage, or provider data policy
  is implemented.
- The configured `copilot_llm_provider` value is ignored by the factory; the
  factory constructs a Gemini-if-keyed then Ollama chain regardless of the
  setting. See F-008.
- Broad provider catches make failures safe for fallback but reduce
  observability and can hide provider-specific diagnostics.
- Real provider runtime, quota behavior, timeout behavior, and data handling
  are unverified.

## 14. Settings

### Verified

- `/auth/me` loads the authenticated profile.
- Display name update uses `PATCH /auth/me`.
- Password change verifies the current password and writes a new scrypt hash.
- Export uses `GET /auth/export` and is scoped to the authenticated user.
- Logout clears local token/session state.
- Avatar is local browser UI state.
- Notification preferences are local browser preferences.

### Open issues

- Settings uses fabricated transaction/import defaults when live metadata cannot
  be loaded. See F-004.
- Settings request failures are swallowed and can leave stale/default values
  visible. See F-005.
- Avatar and notifications are not server-persisted or delivered; the UI
  documents their local nature.
- Forgot-password is simulated with a delayed success message and no backend
  reset workflow. See F-003.

## 15. API Contract

The frontend client paths and methods match the inspected backend route
registration for:

- Authentication and profile
- Password change and export
- Upload and import history
- Dashboard and history
- Transactions
- Subscriptions, EMI, BNPL, exposure
- ML intelligence
- Simulator
- Copilot query and suggestions

No confirmed path/method/field mismatch was found in the active client.

Contract limitations:

- Copilot suggestions are defined in the client but not used by AssistantPage.
- The frontend does not expose every simulator scenario supported by the
  backend.
- Forgot-password UI has no corresponding backend contract.
- Registration collects a name but the register request sends only email and
  password. See F-006.

## 16. Error Handling

### Backend

- Explicit `401`, `403`, `404`, `409`, and `422` paths exist.
- Centralized handling sanitizes unexpected/database errors.
- Credentials, tokens, exception text, and database details are not intended
  for client responses.
- Simulator maps supported scenario `ValueError` to `422`.
- Copilot data-source failures propagate rather than becoming fabricated
  metrics.

### Frontend

- Shared API client normalizes structured errors, network failures, `401`, and
  server errors.
- Main feature pages have loading/error/empty states.
- What-If clears stale results on failed submissions.
- Copilot renders query failures as visible assistant error messages.

### Open handling concerns

- Assistant transaction-count loading swallows failures and does not invoke the
  shared unauthorized logout path. See F-009.
- Settings metadata loading swallows failures and shows defaults. See F-005.
- Intelligence retry reloads the entire page rather than retrying the local
  request.
- Provider failures are intentionally converted to fallback, but diagnostics
  are not exposed or structured.

## 17. Database & Migrations

- Migrations 001 through 009 form one linear Alembic head.
- Auth users and financial users are linked.
- Account-owned data cascade behavior was added.
- Transaction ownership and import ownership are represented.
- Deduplication uses a per-user fingerprint.
- Financial profile relationships and cascade behavior are present.

`alembic heads` and migration history inspection showed one current head.
Actual upgrade/downgrade execution against a fresh disposable database was not
performed during this read-only audit, so fresh-install compatibility is
**UNVERIFIED**.

## 18. Configuration & Secrets

- `.env` is ignored by Git.
- `backend/.env` was not tracked; its existence and secret-bearing configuration
  were observed without printing any secret value.
- `.env.example` contains placeholders rather than real keys.
- Gemini and Ollama settings are backend-only.
- Frontend supports `VITE_API_BASE_URL`; no Gemini key is exposed to React.
- Production settings reject the known development JWT secret or short secrets.
- Development defaults still include a known JWT secret and SQLite URL; this is
  acceptable only when `ENVIRONMENT` is not production.

### Configuration issue

Loading `backend/.env.example` directly failed because comma-separated list
values for Pydantic list fields were not valid JSON for the settings parser.
See F-013.

## 19. Performance

### Existing protections

- Request-scoped DatasetService caching exists.
- History avoids fabricating or expanding missing periods.
- What-If is non-persistent.
- Frontend transactions progressively render visible rows.

### Risks

- App.tsx eagerly imports all active pages and dependencies; the production
  JavaScript chunk is approximately 1,027 KB minified.
- Transactions load the full user transaction response before client-side
  filtering.
- Commitments and Intelligence perform several concurrent requests and
  duplicate some transaction/context work.
- MLService can bootstrap/train/persist all models synchronously when artifacts
  are absent. Concurrent first requests may race and cause high latency.
- No production load/concurrency test was run.

## 20. Frontend Quality

### Confirmed active flow

- Landing, login/register, upload, dashboard, transactions, commitments,
  intelligence, What-If, Assistant/Copilot, Settings.
- Current What-If, Dashboard, Settings, Upload, Transactions, Commitments, and
  Intelligence pages are preserved and connected to the backend.
- Task 6 removed confirmed orphaned prototype pages:
  `CalendarPage.tsx`, `GoalsPage.tsx`, `JourneyPage.tsx`, `ReportsPage.tsx`,
  legacy `SimulatorPage.tsx`, and `shared.tsx`.

### Open frontend findings

- Session restoration can skip empty-account onboarding: F-002.
- Forgot-password is simulated: F-003.
- Settings displays fabricated defaults: F-004.
- Settings errors are swallowed: F-005.
- Registration name is discarded: F-006.
- Separate-workspace upload mode is intentionally unavailable: F-007.
- Assistant context fetch does not handle 401: F-009.
- Multiple pages duplicate API loads: F-010.
- Bundle is large due to eager imports: F-011.
- Some clickable containers and icon controls have weak keyboard/ARIA
  semantics: F-014.
- `ImageWithFallback.tsx` is orphaned; the UI-kit directory also includes many
  unused library components. These are cleanup observations, not proven
  application defects.
- Conversation history is in-memory only and disappears on reload.
- Copilot suggestions endpoint is not used by the active Assistant page.

Landing-page marketing metrics are intentionally demo/marketing content. They
are not treated as authenticated financial data. The Settings defaults are
different because they appear in the authenticated account UI and are therefore
reported as a data-integrity finding.

## 21. Testing & Verification

### Executed

- Focused and complete backend tests: **68 passed**.
- `python -m compileall app`: **passed**.
- Frontend `npm run build`: **passed**.
- `git diff --check`: **passed**.
- Migration graph inspection: one head, linear history.
- Targeted simulator over-capacity probe: reproduced exposure clamp.
- `.env.example` parsing probe: reproduced settings parse failure.
- Source/import/routing/dependency inspection: completed.

### Not configured

- No frontend unit/integration test script.
- No frontend TypeScript diagnostic script or TypeScript configuration was
  found.
- No frontend lint script was configured.

### Not verified

- Real Gemini runtime request.
- Real Ollama runtime request.
- Gemini-to-Ollama runtime fallback.
- Browser E2E.
- Production HTTP deployment.
- Fresh disposable database migration execution.
- Concurrent ML bootstrap.
- Production load/performance.
- Old-token invalidation after password change.
- Negative-amount ingestion behavior.

Passing tests are evidence for their covered paths, not proof of total system
correctness.

## 22. Known Limitations

- No URL routing/deep linking/browser back-forward page state.
- Forgot-password has no real reset capability.
- Notifications have no backend persistence or delivery.
- Avatar is browser-local.
- Copilot conversation history is not persisted.
- Copilot suggestions are not loaded by the active UI.
- Gemini/Ollama external behavior is not verified in this repository run.
- Model accuracy and confidence calibration are not established.
- Model drift monitoring is not present.
- Fresh migration execution and production deployment are unverified.

## 23. Findings

### F-001

- **ID:** F-001
- **Severity:** 🟠 HIGH
- **Area:** What-If / financial calculation consistency
- **File:** `backend/app/digital_twin/scenario_builder.py`
- **Function/endpoint:** `_recalculate_snapshot_metrics`; `POST /api/v1/simulator/simulate`
- **Description:** Simulator exposure is clamped to 100%.
- **Evidence:** `min(100.0, raw_exposure)` is used in Digital Twin recalculation.
  `docs/BUSINESS_RULES.md` states exposure may exceed 100%, and ExposureService
  leaves it uncapped. A direct over-capacity probe returned `100.0`.
- **Impact:** What-If results can understate overcommitment and disagree with
  the authoritative Exposure Engine.
- **Current behavior:** Simulated exposure cannot exceed 100%.
- **Expected behavior:** Simulator should preserve the same over-100% exposure
  semantics as the authoritative engine.
- **Recommended fix:** Remove or revise the simulator cap and add an
  over-capacity regression test.
- **Verification status:** VERIFIED by direct reproduction and source inspection.

### F-002

- **ID:** F-002
- **Severity:** 🟠 HIGH
- **Area:** Frontend session restoration/onboarding
- **File:** `frontend/src/app/App.tsx`
- **Function/endpoint:** Session restoration effect
- **Description:** Restored JWT sessions unconditionally set `hasData=true`.
- **Evidence:** After `/auth/me`, the effect calls `setHasData(true)` without
  checking `/transactions/imports` or transactions.
- **Impact:** Empty authenticated users can bypass upload onboarding after a
  refresh and enter pages that require financial data.
- **Current behavior:** Any valid restored session opens AppShell.
- **Expected behavior:** Restoration should verify whether the authenticated
  account has persisted transactions and show UploadPage when empty.
- **Recommended fix:** Reuse the authenticated import/transaction check during
  session restoration.
- **Verification status:** VERIFIED by source inspection; browser reproduction
  was unavailable.

### F-003

- **ID:** F-003
- **Severity:** 🟠 HIGH
- **Area:** Authentication UX/API contract
- **File:** `frontend/src/app/AuthPages.tsx`
- **Function/endpoint:** Forgot-password handler
- **Description:** Forgot-password always displays simulated success.
- **Evidence:** The handler waits and shows a reset-link message; backend auth
  routes have no reset request/token endpoint.
- **Impact:** Users are told a recovery action occurred when no email or reset
  operation exists.
- **Current behavior:** Simulated reset success.
- **Expected behavior:** Implement a real reset contract or clearly label the
  feature unavailable.
- **Recommended fix:** Add a secure reset-token flow or remove the simulated
  success state.
- **Verification status:** VERIFIED by source and route inspection.

### F-004

- **ID:** F-004
- **Severity:** 🟠 HIGH
- **Area:** Settings data integrity
- **File:** `frontend/src/app/SettingsPage.tsx`
- **Function/endpoint:** Import metadata/transaction count rendering
- **Description:** Authenticated Settings UI has fabricated fallback metadata.
- **Evidence:** Defaults include values such as 2,841 transactions and a
  historical CSV filename; request failures leave fallback values visible.
- **Impact:** Users can mistake synthetic metadata for their actual account
  history.
- **Current behavior:** Default/stale values can display after empty/error state.
- **Expected behavior:** Show loading, unavailable, or empty state without
  fabricated account facts.
- **Recommended fix:** Remove fabricated defaults and represent unavailable
  metadata explicitly.
- **Verification status:** VERIFIED by source inspection.

### F-005

- **ID:** F-005
- **Severity:** 🟡 MEDIUM
- **Area:** Settings error handling
- **File:** `frontend/src/app/SettingsPage.tsx`
- **Function/endpoint:** Import and transaction metadata effects
- **Description:** Metadata errors are swallowed without a user-visible error.
- **Evidence:** Catch handlers retain/null state rather than exposing a truthful
  failure state.
- **Impact:** Backend failures are indistinguishable from valid zero/default
  metadata.
- **Current behavior:** Silent fallback/stale display.
- **Expected behavior:** Show unavailable/error state and allow retry.
- **Recommended fix:** Add explicit metadata loading/error/empty states.
- **Verification status:** VERIFIED by source inspection.

### F-006

- **ID:** F-006
- **Severity:** 🟡 MEDIUM
- **Area:** Registration/profile contract
- **File:** `frontend/src/app/AuthPages.tsx`, `frontend/src/api/client.ts`
- **Function/endpoint:** `/auth/register`
- **Description:** Registration collects full name but sends only email/password.
- **Impact:** User-entered name is discarded and must be re-entered in Settings.
- **Current behavior:** Name input has no backend effect.
- **Expected behavior:** Either persist the name through registration or do not
  collect it.
- **Recommended fix:** Extend the registration contract or remove the unused
  field.
- **Verification status:** VERIFIED by source and schema inspection.

### F-007

- **ID:** F-007
- **Severity:** 🟡 MEDIUM
- **Area:** Upload UX
- **File:** `frontend/src/app/UploadPage.tsx`
- **Function/endpoint:** “Analyze separately” mode
- **Description:** A selectable upload mode always fails because isolated
  workspaces are unavailable.
- **Impact:** Dead functionality creates an avoidable user path.
- **Current behavior:** Client-side limitation error.
- **Expected behavior:** Hide unavailable mode or implement it.
- **Recommended fix:** Remove the option until supported, or add explicit
  separate-workspace backend behavior.
- **Verification status:** VERIFIED by source inspection.

### F-008

- **ID:** F-008
- **Severity:** 🟡 MEDIUM
- **Area:** Copilot provider configuration
- **File:** `backend/app/core/config.py`, `backend/app/copilot/llm_provider.py`
- **Function/endpoint:** `build_llm_provider`
- **Description:** `copilot_llm_provider` is configured but ignored.
- **Impact:** Operators cannot reliably select deterministic-only, Gemini-only,
  or Ollama-only behavior through the advertised setting.
- **Current behavior:** When enabled, factory constructs Gemini-if-keyed then
  Ollama chain regardless of provider value.
- **Expected behavior:** Provider configuration should determine the intended
  chain.
- **Recommended fix:** Implement and test a provider-selection matrix.
- **Verification status:** VERIFIED by source inspection; matrix untested.

### F-009

- **ID:** F-009
- **Severity:** 🟡 MEDIUM
- **Area:** Copilot session/error handling
- **File:** `frontend/src/app/AssistantPage.tsx`
- **Function/endpoint:** Transaction-count loading effect
- **Description:** A 401 while loading transaction context is swallowed.
- **Impact:** UI can remain apparently authenticated until a later Copilot
  request fails.
- **Current behavior:** Count becomes null without invoking logout.
- **Expected behavior:** Route invalid sessions through the shared unauthorized
  handler.
- **Recommended fix:** Handle `ApiError.status === 401` consistently.
- **Verification status:** VERIFIED by source inspection.

### F-010

- **ID:** F-010
- **Severity:** 🟡 MEDIUM
- **Area:** Frontend performance/data loading
- **File:** `DashboardPage.tsx`, `CommitmentsPage.tsx`,
  `IntelligencePage.tsx`
- **Description:** Several pages duplicate full transaction/context requests.
- **Impact:** Higher browser transfer, memory use, and repeated processing.
- **Current behavior:** Browser-side requests are coordinated with local effects
  but not a shared query/cache layer.
- **Expected behavior:** Reuse already-loaded request data where practical.
- **Recommended fix:** Introduce a bounded page/session cache or request
  coordination without changing backend financial logic.
- **Verification status:** VERIFIED by source inspection; production impact
  unmeasured.

### F-011

- **ID:** F-011
- **Severity:** 🟡 MEDIUM
- **Area:** Frontend performance
- **File:** `frontend/src/app/App.tsx`
- **Description:** All active pages are eagerly imported.
- **Evidence:** Vite reports a roughly 1,027 KB minified JavaScript chunk and
  warns above the configured 500 KB threshold.
- **Impact:** Slower initial download and parse time.
- **Current behavior:** Entire page graph loads at startup.
- **Expected behavior:** Route/page code may be loaded when needed.
- **Recommended fix:** Add route-level lazy loading after preserving state-machine
  behavior.
- **Verification status:** VERIFIED by production build output.

### F-012

- **ID:** F-012
- **Severity:** 🔵 LOW
- **Area:** Profile synchronization semantics
- **File:** `backend/app/services/financial_profile_sync_service.py`
- **Function:** `_success_rate`
- **Description:** Blank/unknown statuses are treated differently by profile
  success-rate sync and commitment classification services.
- **Impact:** Profile-derived ML feature may diverge from other financial
  summaries for incomplete status data.
- **Current behavior:** Only explicit success markers count as successful in the
  profile path.
- **Expected behavior:** Status semantics should be documented and consistent,
  or intentionally separated.
- **Recommended fix:** Define shared status classification and regression tests.
- **Verification status:** PARTIALLY VERIFIED by source inspection.

### F-013

- **ID:** F-013
- **Severity:** 🔵 LOW
- **Area:** Configuration portability
- **File:** `backend/.env.example`
- **Description:** Example list settings are comma-separated, but Pydantic
  Settings expects JSON for list fields.
- **Evidence:** Loading `.env.example` directly raised a settings parse error
  for `cors_allow_origins`.
- **Impact:** New developers cannot reliably validate the example environment.
- **Current behavior:** Effective local `.env` loads, example does not.
- **Expected behavior:** Example values should match the parser format.
- **Recommended fix:** Use valid JSON list syntax or custom parsing consistent
  with the documented example.
- **Verification status:** VERIFIED by direct probe.

### F-014

- **ID:** F-014
- **Severity:** 🔵 LOW
- **Area:** Frontend accessibility
- **File:** `frontend/src/app/components/AppSidebar.tsx`,
  `frontend/src/app/UploadPage.tsx`
- **Description:** Some clickable containers and icon-only controls lack strong
  keyboard semantics or explicit ARIA labels.
- **Impact:** Keyboard and assistive-technology usability is inconsistent.
- **Current behavior:** Some controls rely on visual click behavior/title text.
- **Expected behavior:** Interactive controls should use semantic buttons/links
  and explicit labels.
- **Recommended fix:** Audit and add semantic roles/labels without redesigning.
- **Verification status:** VERIFIED by source inspection; no automated
  accessibility test configured.

### F-015

- **ID:** F-015
- **Severity:** ⚪ INFORMATIONAL
- **Area:** Authentication security lifecycle
- **File:** `backend/app/core/security.py`
- **Description:** JWTs are stateless and contain only subject/expiration; there
  is no refresh-token, revocation, issuer/audience, or login-rate-limit system.
- **Impact:** Limits session lifecycle controls in a production threat model.
- **Current behavior:** Existing tokens remain valid until expiration.
- **Expected behavior:** Depends on deployment security requirements.
- **Recommended fix:** Evaluate token lifecycle/revocation and abuse controls
  before production exposure.
- **Verification status:** VERIFIED by source inspection.

### F-016

- **ID:** F-016
- **Severity:** 🟡 MEDIUM
- **Area:** Copilot privacy/provider governance
- **File:** `backend/app/copilot/llm_provider.py`,
  `backend/.env`
- **Description:** Enabled Gemini receives authenticated-user financial context,
  but no provider consent, retention, redaction, or regional-data policy exists.
- **Impact:** Financial information may leave the application boundary under
  provider terms not represented in the product.
- **Current behavior:** Provider chain is enabled when configured and sends
  compact backend-derived context.
- **Expected behavior:** Product/deployment policy should explicitly govern
  external financial-data processing.
- **Recommended fix:** Add consent/configuration policy, redaction and logging
  controls, and provider data-handling documentation.
- **Verification status:** PARTIALLY VERIFIED by code/config inspection; no real
  request was made.

### F-017

- **ID:** F-017
- **Severity:** 🟡 MEDIUM
- **Area:** ML deployment/performance
- **File:** `backend/app/services/ml_service.py`,
  `backend/app/ml/saved_models`
- **Description:** Missing model artifacts can trigger synchronous bootstrap/
  training during request handling.
- **Impact:** First-request latency, concurrent bootstrap races, and deployment
  instability are possible.
- **Current behavior:** Service can initialize/bootstrap models on demand.
- **Expected behavior:** Deployment should provision/version artifacts or
  serialize bootstrap explicitly.
- **Recommended fix:** Move artifact preparation to controlled startup/deployment
  and add concurrent initialization tests.
- **Verification status:** PARTIALLY VERIFIED by source and filesystem
  inspection; no load test was run.

### F-018

- **ID:** F-018
- **Severity:** 🟡 MEDIUM
- **Area:** CSV financial input validation
- **File:** `backend/app/services/transaction_import_service.py`,
  `subscription_service.py`, `emi_service.py`, `bnpl_service.py`
- **Function/endpoint:** `POST /api/v1/transactions/upload`
- **Description:** Negative amounts are accepted as finite numeric values and
  can flow into commitment burden calculations.
- **Evidence:** Import validation checks finiteness but does not reject negative
  amounts; commitment services multiply signed amounts directly.
- **Impact:** A malformed or semantically unsupported negative commitment row
  could reduce calculated commitments/exposure or create negative burdens.
- **Current behavior:** Negative values can be persisted and classified.
- **Expected behavior:** The system should explicitly distinguish valid refunds/
  credits from invalid negative commitment inputs.
- **Recommended fix:** Define signed-amount business semantics, validate them at
  ingestion, and add regression tests for refunds and negative commitments.
- **Verification status:** STATIC finding; endpoint behavior was not modified or
  exercised during this read-only audit.

### F-019

- **ID:** F-019
- **Severity:** 🟡 MEDIUM
- **Area:** Authentication session lifecycle
- **File:** `backend/app/core/security.py`,
  `backend/app/services/auth_service.py`
- **Function/endpoint:** `POST /api/v1/auth/change-password`
- **Description:** Password changes do not invalidate JWTs already issued before
  the password change.
- **Evidence:** JWTs contain only `sub` and `exp`; password change updates the
  stored hash but no token version, revocation list, or session invalidation is
  checked by authentication.
- **Impact:** A stolen prior token remains usable until expiration after the
  user changes the password.
- **Current behavior:** Existing tokens remain accepted until expiry.
- **Expected behavior:** Security policy should determine whether password
  changes revoke prior sessions; sensitive deployments commonly revoke them.
- **Recommended fix:** Add a token-version/revocation strategy and test old-token
  rejection after password change.
- **Verification status:** VERIFIED by source inspection; old-token behavior was
  not exercised by the existing tests.

## 24. Open Issues

### Critical

None identified from the inspected code and tested authenticated flows.

### High

- F-001: Simulator exposure clamp contradicts financial business rules.
- F-002: Session restoration can bypass empty-account onboarding.
- F-003: Forgot-password reports simulated success without a backend reset.
- F-004: Settings displays fabricated/stale account metadata.

### Medium

- F-005: Settings metadata errors are swallowed.
- F-006: Registration name is discarded.
- F-007: Unsupported separate-upload mode remains selectable.
- F-008: Copilot provider setting is ignored.
- F-009: Assistant transaction-context 401 is swallowed.
- F-010: Duplicate frontend data loading.
- F-011: Large eager frontend bundle.
- F-016: External provider privacy/governance gap.
- F-017: Synchronous ML bootstrap/performance risk.
- F-018: Negative CSV amounts are accepted and can affect financial burdens.
- F-019: Password changes do not revoke existing JWTs.

### Low

- F-012: Profile status semantics can diverge.
- F-013: `.env.example` list parsing failure.
- F-014: Accessibility semantics.
- Orphaned `ImageWithFallback.tsx` and unused UI-kit surface.

### Informational

- F-015: No refresh/revocation/issuer/audience/rate-limit lifecycle features.
- Copilot conversation history is in-memory only.
- Copilot suggestions endpoint is not used by the active UI.
- Notifications and avatar remain local/UI-only.
- Browser E2E, live provider behavior, fresh migration application, and
  production concurrency remain unverified.

## 25. Verification Matrix

| Feature | Automated | Manual | Browser E2E | Status |
|---|---|---|---|---|
| Registration/login/JWT | Tested | Partially inspected | Unverified | PARTIALLY VERIFIED |
| Tenant isolation | Tested with multi-user tests | Source inspected | Unverified | VERIFIED for covered API paths |
| CSV ingestion/deduplication | Tested | Source inspected | Unverified | VERIFIED for covered cases |
| Profile synchronization | Tested | Source inspected | Unverified | VERIFIED for covered cases |
| Financial calculations | Tested in service/integration tests | Source/formulas inspected | Unverified | PARTIALLY VERIFIED |
| ML feature sync/inference | Tested for covered paths | Source/artifacts inspected | Unverified | PARTIALLY VERIFIED |
| ML quality/calibration | Some quality tests | Source inspected | Unverified | LIMITED |
| Dashboard | Backend/integration tested | Frontend source inspected | Unverified | PARTIALLY VERIFIED |
| Historical dashboard | History tests | Frontend source inspected | Unverified | PARTIALLY VERIFIED |
| What-If | Simulator tests | Frontend/backend source inspected | Unverified | PARTIALLY VERIFIED; F-001 open |
| Deterministic Copilot | Tested | Source inspected | Unverified | VERIFIED for covered paths |
| Gemini | Mocked provider tests | Configuration inspected | Unverified | UNVERIFIED runtime |
| Ollama | Mocked chain coverage | Adapter inspected | Unverified | UNVERIFIED runtime |
| Provider fallback | Mocked tests | Source inspected | Unverified | PARTIALLY VERIFIED |
| Settings/profile/password/export | Backend tests | Frontend source inspected | Unverified | PARTIALLY VERIFIED; F-004 open |
| Migrations | Graph inspected | Not applied in audit | Unverified | PARTIALLY VERIFIED |
| Frontend build | Passed | N/A | N/A | VERIFIED build only |
| Frontend type/lint/tests | Not configured | N/A | N/A | UNVERIFIED |
| Full browser flow | None | Tooling unavailable | Unverified | UNVERIFIED |

## 26. Final Repository Structure

```text
.
├── backend
│   ├── alembic
│   │   └── versions
│   ├── app
│   │   ├── api/v1/endpoints
│   │   ├── copilot
│   │   ├── database
│   │   ├── decision
│   │   ├── digital_twin
│   │   ├── dna
│   │   ├── experience
│   │   ├── ml
│   │   ├── repositories
│   │   ├── schemas
│   │   └── services
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend
│   ├── src/app
│   │   ├── active authenticated pages
│   │   ├── auth/landing/upload pages
│   │   └── components
│   ├── src/api
│   ├── package.json
│   └── vite.config.ts
├── tests
├── docs
├── scripts
├── finsight.db
└── README.md
```

Task 6 removed the confirmed orphaned prototype page files from
`frontend/src/app`. No reference/training dataset or model source was modified
by this audit.

## 27. Recommended Next Actions

1. Correct F-001 and add an over-100% simulator regression test because it
   changes a user-visible financial result.
2. Correct F-002 so session restoration verifies the authenticated account's
   actual transaction/import state.
3. Remove simulated forgot-password success or implement a secure reset
   workflow.
4. Remove fabricated Settings defaults and expose truthful metadata error/
   empty states.
5. Define negative-amount semantics and reject or classify unsupported signed
   commitment inputs.
6. Decide and implement password-session revocation requirements.
7. Make Copilot provider configuration explicit and test Gemini/Ollama/
   deterministic selection matrices.
8. Establish external-provider privacy/consent/retention/redaction policy
   before enabling Gemini for production financial data.
9. Validate fresh Alembic upgrades and controlled ML artifact provisioning in a
   disposable/deployment environment.
10. Add browser E2E coverage for register, upload, refresh, all active pages,
    What-If, Copilot, Settings, export, logout, and re-login.
11. Add frontend type-check/lint/test tooling or document an intentional
    alternative verification strategy.
12. Address duplicate frontend data loading, bundle splitting, and accessibility
    findings after correctness and security items.
