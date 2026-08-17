# Implementation Status

Last updated: 2026-08-14 15:45:00 +03:00

## Overall status

**Completion markers in this document were reset on 2026-08-14.**
The 79 checkboxes and 13 `Status` lines here were written by earlier
implementation batches, and the evidence behind them is not recorded in this
file. They were therefore unchecked and relabelled `NEEDS RE-VERIFICATION`, with
the previous values kept in parentheses. This says nothing about whether the work
is correct - only that it has not been re-confirmed since the reset.

Re-tick an item once you have confirmed it against the current code, the live
schema, or a test that demonstrably fails when the behavior is broken. A test
that passes against a mock which cannot detect the defect is not confirmation:
Milestone 7 was marked complete on exactly such a test while its Socket.IO room
isolation did not work at runtime.

Milestones 0 and 1 were previously reported complete. The existing
implementation and live database schema were inspected before
authentication/refactor work, and the first small compatibility-preserving
enum/DTO/test batch was reported verified. An independent frontend batch also
removed public credential hints and closed the two targeted Socket.IO/order-note
XSS rendering paths.

The application currently has no backend authentication or authorization
boundary. Several critical direct-HTTP attack paths are confirmed and remain
open. The frontend fixes do not authenticate Socket.IO or HTTP callers and do
not make the client a security boundary.

The required `docs/` project-memory files were previously ignored by Git. That
ignore rule was removed during Milestone 0 so future status and changelog edits
are visible in normal Git status/diff output.

---

## Current milestone

### Milestone 2 - Staff authentication

Status: NEEDS RE-VERIFICATION (previously: COMPLETED - migration script prepared, requires manual execution)

The next authentication implementation is active. A migration script has been prepared to replace the live six-digit plaintext secrets with salted encoded hashes.
The independent PIN/XSS frontend hardening batch was reported completed and
tested without changing authentication, database schema, payment behavior, or
BOS -> DOLU.

---

## Milestones pending re-verification

### Milestone 0 - Existing system analysis

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

Completion verification:

- [ ] Inspect project directory structure
- [ ] Identify backend framework
- [ ] Identify controller/router structure
- [ ] Identify service layer
- [ ] Identify repository/data-access layer
- [ ] Identify database models and live schema
- [ ] Identify schemas/DTOs
- [ ] Identify current authentication implementation
- [ ] Identify QR/token implementation
- [ ] Identify staff login implementation
- [ ] Identify order endpoints
- [ ] Identify table endpoints
- [ ] Identify payment endpoints/behavior
- [ ] Identify WebSocket/socket implementation
- [ ] Identify current tests and test-runtime state
- [ ] Identify known authorization vulnerabilities
- [ ] Trace the reported table-ID active-order disclosure end to end
- [ ] Compare documentation claims with real code and live schema
- [ ] Produce a concrete, incremental implementation plan

No production data was modified. Live SQL verification was read-only.

---

## Independent hardening batches pending re-verification

### Public PIN hints and targeted frontend XSS sinks

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Removed the public waiter credential list from `templates/garson.html`.
- [ ] Replaced the table-verification placeholder that repeated a live staff PIN
  with generic text.
- [ ] Added one browser/CommonJS-compatible HTML text encoder and loaded it
  before the customer, waiter, kitchen, and cashier scripts.
- [ ] Encoded the confirmed Socket.IO-controlled table-name rendering sinks and
  normalized Socket.IO table IDs to positive integers before using them.
- [ ] Encoded customer order names/notes at the targeted cart, tracking, waiter,
  kitchen, and cashier `innerHTML` sinks.
- [ ] Replaced note-derived DOM IDs/inline arguments with numeric indexes backed
  by internal key maps.
- [ ] Kept client-controlled device IDs out of inline JavaScript by resolving a
  numeric button index in a static click listener.
- [ ] Changed the browser-restored waiter identity badge to `textContent`.
- [ ] Added and executed 8 Node tests plus syntax checks for all five affected
  JavaScript files.
- [ ] Re-executed all 17 Python tests.
- [ ] Independently reviewed the targeted diff.

Scope limit: this is not an application-wide XSS completion claim. Because the
admin mutation endpoints are still anonymous, raw catalog/category/image/table
values can still be persisted and reach other `innerHTML` or inline-handler
sinks in `static/js/app.js`, `static/js/admin.js`, and `static/js/kasa.js`.
Those residual sinks remain a HIGH open finding for a later focused batch.

### Staff login response schema TTL fix

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Fixed `HTTP 500 Internal Server Error` on `/api/auth/login` and `/api/garson/verify-pin`.
- [ ] Increased upper bound for `expires_in` in `LoginResponse` and `GarsonPinResponse` (`app/schemas/auth.py`) from `le=3600` to `le=31536000` (`365 * 24 * 3600`), allowing configured staff JWT token TTLs (e.g., 30 days = `2592000` seconds).
- [ ] Added unit test `test_login_and_pin_response_supports_extended_ttl` in `tests/test_enums_and_schemas.py`.

### Kasa grid salonContainer/bahceContainer ReferenceError fix

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Fixed `ReferenceError: salonContainer is not defined` in `renderKasaGrid` (`static/js/kasa.js`).
- [ ] Defined `salonContainer` and `bahceContainer` variables using `document.getElementById('kasaGridSalon')` and `document.getElementById('kasaGridBahce')` with null safety checks before rendering innerHTML.

---



## Confirmed architecture

### Runtime and framework

- Backend: FastAPI 0.139.2, served by Uvicorn.
- Realtime: python-socketio 5.16.3 mounted as the outer ASGI application.
- DTO validation: Pydantic 2.13.4.
- Database: Microsoft SQL Server through synchronous `pyodbc`/`pymssql` calls.
- Application entry points: `run.py` and `app/main.py`.
- HTTP API prefix: `/api`; route composition is in `app/api/v1/api.py`.
- CORS exists for FastAPI and wildcard Socket.IO origins are enabled. CORS is
  not treated as authentication.

### Layers actually present

- Page controllers: `app/api/views.py`.
- API routers/controllers: `app/api/v1/endpoints/`.
- Business services: `app/services/`.
- Raw-SQL repositories: `app/repositories/`.
- Connection/transaction abstraction: `app/database.py`.
- Request and response DTOs: `app/schemas/auth.py`, `catalog.py`, `common.py`,
  `orders.py`, and `tables.py`; `app/schemas/schemas.py` is compatibility-only.
- Realtime event bus and Socket.IO adapter: `app/core/events.py` and
  `app/core/socket_manager.py`.
- QR/TOTP implementation: `app/core/totp_service.py`.
- No ORM or separate database/domain model classes exist.

The intended controller -> service -> repository -> database flow is generally
recognizable, but important authorization and business checks are absent from
both controllers and services.

### Live database schema verified read-only

Tables:

- `BannedDevices`
- `Kategoriler`
- `Kullanicilar`
- `Masalar`
- `SiparisDetaylari`
- `Siparisler`
- `Urunler`

Relationships:

- `Siparisler.masa_id -> Masalar.id`
- `SiparisDetaylari.siparis_id -> Siparisler.id`
- `SiparisDetaylari.urun_id -> Urunler.id`
- `Urunler.kategori_id -> Kategoriler.id`

Confirmed schema facts:

- No customer-session, staff-session/token, payment-ledger, token-revocation,
  refresh-token, or idempotency table exists.
- `Kullanicilar.sifre_hash` is `nvarchar(255)`, so a modern encoded password
  hash fits without widening the column.
- The live roles are exactly `admin`, `garson`, `kasa`, and `mutfak`.
- All eight current `sifre_hash` values are six-digit numeric strings; none has
  a bcrypt, PBKDF2, or Argon2 encoded-hash marker.
- `Siparisler` has no `odeme_yontemi` column although the service and DTOs use
  that field. The value is present only in the immediate create response and is
  lost when the order is read back from SQL Server.
- No database CHECK constraint enforces role/status values, positive quantity,
  positive price, or positive total.

### DTO/model state

- Request/response DTOs are split into `auth`, `catalog`, `common`, `orders`,
  and `tables` modules. `app/schemas/schemas.py` remains a complete compatibility
  re-export facade.
- Verified role, table, payment, order-state, order-action, and token-type values
  are represented by string enums with unchanged lowercase wire values.
- DTO validation now rejects invalid IDs, non-positive quantity, negative money/
  stock, empty order item lists, arbitrary order states, and overlong values for
  the selected auth/table/order metadata fields that have explicit limits.
- Catalog names/descriptions/image URLs still need database-aligned maximum
  lengths; the general validation-gap finding remains open.
- Nonnegative client price and total fields remain in the request contract and
  are still trusted by the service; validation alone does not make them
  authoritative-safe.
- `SiparisResponse` exposes `device_id`; that response is currently available
  anonymously and is also broadcast globally over Socket.IO.

---

## Current authentication and authorization mechanisms

### Staff

- `POST /api/auth/login` performs direct equality against
  `Kullanicilar.sifre_hash` and returns only a user DTO.
- `POST /api/garson/verify-pin` performs the same direct equality lookup and
  returns only a user DTO.
- Neither endpoint issues a token, cookie, server session, or authenticated
  principal.
- The waiter UI stores editable user data in `localStorage`; privileged API
  calls send a caller-controlled `garson_adi`, not proof of identity.
- The public waiter template no longer embeds staff PIN examples. The live
  values were already disclosed and remain unhashed until approved rotation.
- There is no login rate limit, reusable auth dependency, JWT validation,
  token-type validation, role guard, or object-level authorization.

### Customer QR/TOTP

- Each table has a 32-character random secret in `Masalar.totp_secret`.
- The backend produces a six-digit HMAC-SHA256 time-window token.
- The verifier accepts the current window and +/- two windows, so the effective
  acceptance span is materially wider than the documented 30 seconds.
- Used-token replay tracking exists only in an in-process Python set and is lost
  on restart or split across multiple workers.
- `POST /api/masalar/{id}/verify-qr` returns only a boolean result. It creates no
  authenticated customer session and gives no session/access token.
- A caller-supplied `device_id` can be treated as a returning participant, but
  the identifier is mutable and is exposed by public order responses.

### BOS -> DOLU rule

The required first-order physical-verification check is present in
- `SiparisService.create_siparis` içerisinde stoklar eksiye düşmemesi için sadece `WHERE stok_miktari >= ?` ile kontrol sağlanıyor (Check constraint eksik ama query katmanında koruma var).
- **Masa tahsilatları ve Troll koruması (Milestone 8)**: Kasadan alınan parça ödemelerin sayfayı yenileyince kaybolmaması için `MasaTahsilatlari` tablosu eklendi. Ayrıca garson veya kasa "Masayı Temizle" yaptığında troll'ün (masa başından ayrılmış) aktif oturum token'ı siliniyor (`revoke_all_sessions_for_masa`).
However, the rule currently fails as a physical-presence guarantee because
both dynamic-QR generation endpoints are anonymous. A remote caller can obtain
the current token and submit the first order without being at the table.

Once a table is `dolu`, no QR proof or authenticated table membership is
required at all. Knowing the table ID is sufficient to append orders.

---

## Endpoint security inventory

### Intentionally public candidates (still require output review)

- `GET /api/kategoriler`
- `GET /api/urunler`
- Customer/menu HTML and static assets

### Anonymous sensitive reads

- `GET /api/masalar`
- `GET /api/masalar/{masa_id}/aktif-siparis`
- `GET /api/siparisler`
- `GET /api/siparisler?masa_id=...`
- `GET /api/garsonlar`
- `GET /api/masalar/{masa_id}/dynamic-qr`
- `GET /api/masalar/all-dynamic-qrs`

### Anonymous sensitive mutations

- `POST /api/siparisler`
- `PATCH /api/siparisler/{siparis_id}/durum`
- `PUT /api/siparisler/{siparis_id}`
- `POST /api/masalar/move`
- `POST /api/masalar/{masa_id}/clear`
- `POST /api/garson/ban-device`
- All create/update/delete routes under `/api/admin/...`

The `/admin`, `/mutfak`, `/garson`, and `/kasa` pages are public. Public page
delivery is not the primary vulnerability; the APIs behind those pages also
have no backend protection.

OpenAPI generation confirms there are no `securitySchemes` and no operation has
a security requirement.

---

## Known table-ID active-order vulnerability - confirmed trace

1. `static/js/app.js` takes `masa` from the URL and stores it in client state.
2. It requests `/api/masalar/${state.masaId}/aktif-siparis`.
3. `app/api/v1/endpoints/masalar.py` forwards that caller-controlled path ID
   without any auth/session dependency.
4. `SiparisService.get_masa_aktif_siparis` uses the ID directly apart from an
   unauthenticated in-memory move redirect.
5. `SiparisRepository.get_all_active_by_masa_id` selects rows with
   `WHERE s.masa_id = ?`.
6. The response returns order items, notes, totals, payment/order state, waiter
   name, and `device_id`.

Changing the path from one table ID to another therefore selects another
table's data. No authenticated customer table exists to compare with the path.
Fixing this one route alone would be insufficient because anonymous
`GET /api/siparisler?masa_id=...` exposes the same data and the unfiltered form
exposes every order.

---

## Payment behavior

There is no payment endpoint, service, repository, or ledger table.

- Client-selected `odeme_yontemi="pos"` immediately marks an order paid; no
  payment-provider proof is verified.
- Special values sent to the generic order-status PATCH can mark orders paid and
  delivered.
- Cash-register partial payments and discounts exist only in the browser's
  JavaScript memory. Refreshing, using another cashier device, or restarting
  loses them. The backend is called only when the UI decides to clear the whole
  table.
- The cash-paid flow immediately stores `teslim_edildi`, while the kitchen UI
  expects a kitchen-pending state. The documented "cash paid -> kitchen" flow
  is therefore not represented correctly.

No payment/business rule was changed during Milestone 0.

---

## WebSocket/realtime behavior

The bullets below are the Milestone 0 baseline observed on 2026-08-11. See the
dated correction after them for the current behavior.

- Socket.IO accepts unauthenticated connections from any origin.
- Clients self-assert `masa_id` in `musteri_oturdu` and
  `musteri_urun_secti` events.
- There are no authenticated rooms, namespaces, table ownership checks, or role
  checks.
- Every order, payment, table, and browsing event is globally broadcast to every
  connected client.
- Multiple socket IDs per claimed table are kept in process memory. Cart state
  remains per browser; the shared browsing snapshot is last-writer-wins.
- Re-registering a socket to another table can leave stale membership in the
  previous table set.
- Presence maps, table-move redirects, replay state, and the event bus are all
  process-local and are not safe across restart or multiple backend instances.

As of 2026-08-14 the first four bullets no longer describe the code. The
handshake authenticates STAFF JWTs and customer session tokens and joins
`role_*`, `staff` and `table_*` rooms, and every event is emitted to a room
rather than broadcast globally. This was verified after fixing a regression in
which the room-join calls were not awaited, so no client joined any room and
room-targeted emits reached nobody. The remaining bullets still apply: clients
still self-assert `masa_id`, and presence maps and the event bus remain
process-local.

For the current single-backend project, RabbitMQ/Kafka is not justified.
WebSocket is the client delivery channel; a broker would not replace
authentication, authorization, or table/role room isolation. Multi-instance
deployment would later need a shared Socket.IO manager/session state, but no
major infrastructure dependency is approved or added now.

---

## Existing tests and runtime verification

- A tracked standard-library Python suite now contains 17 unit tests for enum/
  DTO compatibility, validation, service state mapping, and repository query
  parameters.
- A tracked built-in Node suite now contains 8 helper/source-contract tests for
  the targeted PIN/XSS hardening batch.
- The only pre-existing test-like file is ignored `scratch/test_security.py`.
- That script has no assertions/failing exit code, expects a nonexistent
  `session_token`/`X-Session-Token` design, and can mutate real order/table data.
  It also contains a hard-coded live staff PIN. It was inspected but
  intentionally not executed or copied into tracked tests; credential rotation
  remains required.
- README references `requirements.txt`, but no such file is tracked and the
  blanket `*.txt` ignore rule would hide it.
- The checked-in `.venv` launcher pointed to a removed base Python installation
  at Milestone 0. As of 2026-08-14 it works and is the interpreter used to run
  the tracked suite.
- A bundled Python 3.12 runtime plus the existing site-packages was used for
  read-only import/OpenAPI/schema verification.
- A bundled Node 24 runtime was used for frontend tests and syntax validation;
  no npm dependency was added.
- `pytest` is not installed. FastAPI's `TestClient` cannot run either, because
  `httpx` is missing (earlier entries in this file called it `httpx2`).

Verification actually executed:

- Application import and OpenAPI generation: PASSED.
- OpenAPI route inventory: PASSED; 29 paths and 31 operations identified.
- OpenAPI security inspection: PASSED; no security schemes/requirements found.
- Live SQL schema/role/status/password-format inspection: PASSED read-only after
  approved local access.
- Python unit suite: PASSED, 17/17.
- Frontend Node suite: PASSED, 8/8.
- JavaScript syntax checks: PASSED for all five affected files.
- `pytest --version`: FAILED because pytest is not installed.
- FastAPI `TestClient` smoke attempt: FAILED before request execution because
  `httpx` is not installed. Endpoint checks on 2026-08-14 were driven directly
  through the ASGI interface instead.
- Direct `.venv` Python execution: FAILED at Milestone 0 because its configured
  base interpreter no longer existed; PASSED on 2026-08-14.

---

## Security findings

### CRITICAL

1. No backend authentication/RBAC protects staff, admin, order, table, or
   payment-changing endpoints.
2. Public dynamic-QR endpoints defeat the BOS -> DOLU physical-presence rule.
3. Anonymous callers can forge order/payment states, including paid/delivered.
4. Client-supplied product prices and order totals are authoritative.
5. Anonymous callers can move/clear tables, replace orders, ban devices, and
   execute all admin CRUD operations.
6. `odeme_yontemi="pos"` is accepted as proof of payment.

### HIGH

1. Confirmed table-ID IDOR exposes another table's active-order information.
2. Anonymous `/api/siparisler` provides broader order/device disclosure.
3. All live staff secrets are unhashed six-digit values and are compared
   directly; there is no brute-force protection.
4. **REMEDIATED IN PUBLIC HTML:** valid staff PIN hints were embedded in public
   HTML. The hints are removed, but the already disclosed live credentials must
   still be rotated and hashed before staff authentication can be trusted. The
   ignored stale scratch script also retains one hard-coded live PIN.
5. DOLU-table order creation has no authenticated membership check.
6. **PARTIALLY REMEDIATED:** DTO validation now rejects non-positive quantity,
   closing the negative-quantity stock-increase input. Insufficient stock is
   still clamped to zero instead of rejecting the order.
7. No idempotency/concurrency guard prevents duplicate orders or repeated stock
   decrements.
8. **REMEDIATED (PENDING RE-VERIFICATION):** Socket.IO was unauthenticated and
   globally broadcast sensitive events. The handshake now validates STAFF JWTs
   and customer session tokens and joins `role_*`, `staff` and `table_*` rooms,
   and every event is emitted to a room. Corrected on 2026-08-14 after a
   regression in which the room-join calls were not awaited, so no client
   joined any room. Clients still self-assert `masa_id` in `musteri_oturdu`
   and `musteri_urun_secti`, which remains open.
9. **REMEDIATED FOR THE CONFIRMED SINKS:** Socket.IO table text is encoded and
   table IDs are normalized before waiter-panel HTML/handler use. Socket.IO
   authentication and broadcast exposure are addressed under finding 8.
10. **REMEDIATED FOR THE CONFIRMED NOTE SINKS:** customer order notes/names are
    encoded at the targeted customer, kitchen, waiter, and cashier render paths;
    raw note-derived DOM IDs and inline device-ID JavaScript were removed.
11. Browser-only partial-payment accounting can be lost or double-collected.
12. Caller-controlled `device_id` can bypass bans/membership checks and is
    publicly disclosed.
13. Anonymous admin CRUD can persist catalog/category/image/table values that
    still reach additional unescaped `innerHTML`, URL-attribute, or inline-
    handler sinks in customer/admin/cashier pages. A broader stored-XSS sink
    audit remains open.

### MEDIUM

1. TOTP replay protection and table/socket state are process-local.
2. TOTP accepts current +/- two 30-second windows, wider than documented.
3. Delivered orders are still returned as active because the repository excludes
   only `iptal` and `odendi_kapatildi`.
4. Cash-payment state handling contradicts the documented kitchen flow.
5. **PARTIALLY REMEDIATED:** enum/numeric and selected length validation was
   added, but catalog length limits and multiple business-state validations are
   still missing.
6. CORS cannot protect these APIs from direct HTTP clients.
7. **PARTIALLY REMEDIATED:** project-memory documents and the old script were
   ignored by Git. The `docs/` ignore was removed and tracked replacement tests
   were added; the stale scratch script remains ignored and unsafe.

No confirmed SQL-injection path was found in the inspected runtime repositories;
request values are generally parameterized. The one dynamic update-column name
is selected from a fixed service-owned key set.

---

## Architectural decisions

1. Preserve FastAPI + service/repository + SQL Server; do not perform a
   repository-wide rewrite.
2. Preserve the BOS -> DOLU current-TOTP requirement. The fix must protect token
   issuance and bind later requests to authenticated sessions, not remove the
   rule.
3. Keep public menu/category/product reads separate from protected operational
   data.
4. Use the live lowercase values for enums: roles `admin`, `garson`, `kasa`,
   `mutfak`; existing table/order/payment strings must remain API/DB compatible.
5. Add central reusable authentication and role dependencies; do not copy token
   validation into each controller.
6. Enforce resource ownership and state transitions again in services even when
   route-level role checks exist.
7. Prefer database-backed customer sessions for restart/multi-device safety.
   This needs a user-approved schema change before implementation.
8. Do not add Redis, RabbitMQ, or Kafka. The current single backend can use its
   database plus authenticated Socket.IO rooms.
9. Use the new non-destructive Python/Node suites for incremental security
   mutations. The stale live-data script is not a valid test suite.

---

## Incremental implementation plan

### Milestone 1 - Enum and model/schema cleanup

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Added string enums for verified user roles, table states, payment methods,
  payment states, persisted order states, the legacy cash-collection command,
  and future staff/customer token types.
- [ ] Preserved the existing lowercase SQL/API wire values.
- [ ] Split the mixed schema file into `auth`, `catalog`, `common`, `orders`, and
  `tables` modules.
- [ ] Kept `app.schemas.schemas` as a complete legacy import facade, including
  the previously unused `GarsonResponse` symbol.
- [ ] Rewrote application imports to use the responsible feature module.
- [ ] Updated Python services/repositories to use enum values rather than
  duplicated role/table/payment/order magic strings.
- [ ] Used JSON-mode model dumps at raw Socket.IO/dict boundaries so enums remain
  plain wire strings.
- [ ] Added positive-ID/quantity, nonnegative money/stock, nonempty-order, and
  conservative selected length validation without changing BOS -> DOLU
  behavior.
- [ ] Limited the legacy status endpoint to known states/commands while
  preserving its previous case normalization.
- [ ] Added a tracked standard-library `unittest` suite.
- [ ] Executed 17 tests successfully.
- [ ] Regenerated OpenAPI successfully after the refactor.
- [ ] Executed the changed parameterized repository reads against the live SQL
  Server successfully and without writes.

API validation change: payloads with arbitrary order states, non-positive item
quantities, negative price/total/stock values, empty order item lists, or invalid
IDs now fail Pydantic validation (normally HTTP 422). Client price and total are
still not authoritative-safe merely because negative values are rejected; the
backend still needs DB price recomputation in Milestone 6.

### Milestone 2 - Staff authentication

Status: NEEDS RE-VERIFICATION (previously: COMPLETED - migration script prepared, requires manual execution)

- [ ] Add secure password verification and short-lived signed STAFF access tokens.
- [ ] Add reusable missing/invalid/expired/wrong-token-type handling.
- [ ] Remove public credential hints.
- [ ] Stop trusting browser-stored identity as authentication.
- [ ] Existing six-digit plaintext values must be replaced with encoded hashes in
  `Kullanicilar.sifre_hash`. The column is already wide enough; no schema alter
  is required. (Migration script `scripts/migrate_credentials.py` is ready for execution).
- [ ] A strong `AUTH_SECRET_KEY` must be supplied through environment configuration. (Added to `.env`)

### Milestone 3 - Role-based authorization

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Protect admin, waiter, kitchen, cashier, QR-display, table move/clear, ban,
  order list/update, and payment-changing operations using a documented role
  matrix.
- [ ] Add service-level transition and object checks (`app/services/order_authorization.py`).

### Milestone 4 - QR customer session authentication

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Design a database-backed `CustomerSessions` table with hashed session tokens,
  expiration, revocation, and table binding. (Schema script created)
- [ ] Implement backend token generation, hashing, and database storage in AuthRepo/AuthService.
- [ ] Update `verify-qr` endpoint to return a secure session token upon success.
- [ ] Create a `require_customer_session` dependency to enforce token validation.
- [ ] Update `/api/siparisler` POST endpoint to require either a valid `CUSTOMER_SESSION` or a `current_totp_token` (for BOS -> DOLU).
- [ ] Update frontend `app.js` to store the received session token and send it in the Authorization header.

### Milestone 5 - Table/order object-level authorization

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Added `get_current_user_or_customer` hybrid auth dependency to allow either staff or authenticated customer sessions.
- [ ] Secured `/api/masalar/{masa_id}/aktif-siparis` to prevent IDOR by checking ownership of the session token.
- [ ] Secured `/api/siparisler` endpoints to require appropriate authentication.
- [ ] Updated frontend `app.js` checkActiveOrder to send the `CUSTOMER_SESSION` token in the Authorization header.

### Milestone 6 - Order and payment business-rule hardening

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Authoritative backend price and total recalculation based on database product base prices and option deltas.
- [ ] Rejection of underpaid/manipulated unit prices (`HTTP 400`).
- [ ] Product active state verification (`aktif_mi == 1`). Rejection of inactive product orders (`HTTP 400`).
- [ ] Insufficient stock check (`stok_miktari >= item.adet`). Rejection of insufficient stock (`HTTP 400`).
- [ ] Atomic stock deduction (`WHERE id = ? AND stok_miktari >= ?`).
- [ ] Idempotency guard for duplicate order submissions within 5 seconds.
- [ ] Centralized state transition validation (`validate_order_state_transition`), preventing invalid backward transitions and modifications to terminal states (`CANCELLED`, `PAID_CLOSED`).
- [ ] Added automated unit tests in `tests/test_order_business_rules.py`.

### Milestone 7 - WebSocket authentication/realtime isolation

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Socket.IO handshake authentication (`connect` event) for STAFF (JWT) and CUSTOMER_SESSION (Hex token).
- [ ] Room-based socket isolation (`role_garson`, `role_mutfak`, `role_kasa`, `role_admin`, `staff`, `table_{masa_id}`).
- [ ] Stopped global unauthenticated broadcasting of sensitive order and operational events.
- [ ] Frontend scripts (`app.js`, `waiter.js`, `kitchen.js`, `kasa.js`)- [x] Milestone 7 (Stok Sistemi Güvenliği ve Race Condition Önleme): Sipariş anında stok düşme ve birden fazla cihazla aynı anda (race condition) sipariş verildiğinde stok aşımını önleme.

### Milestone 8 - Multiple-device/session behavior

Status: NEEDS RE-VERIFICATION (previously: COMPLETED)

- [ ] Milestone 8 (Multiple-device/session behavior & Kısmi Ödeme): Aynı masada birden fazla cihaz/oturum davranışının yönetilmesi, masa kapatıldığında oturumların iptali (session revocation) ve kasa tarafından alınan kısmi ödemelerin kalıcı hale getirilmesi (partial payment persistence).

### Milestone 9 - Security audit, automated tests and manual HTTP verification

Status: NOT STARTED

- [ ] Milestone 9 (Final Review & Cleanup): Fazlalık kodların temizlenmesi, güvenlik testleri ve canlı kullanıma hazırlık. HTTP verification
- [ ] Full endpoint security audit after implementation
- [ ] Missing-token tests
- [ ] Invalid-token tests
- [ ] Expired-token tests
- [ ] Role authorization tests
- [ ] Customer/staff token separation tests
- [ ] Table/session ownership tests
- [ ] Order object authorization tests
- [ ] Price/total manipulation tests
- [ ] Order state transition tests
- [ ] WebSocket auth/room isolation tests
- [ ] Complete application-wide stored/DOM XSS regression tests
  - 8 Node tests now cover the targeted PIN/order-note/Socket.IO sink batch, but
    they are helper/source-contract tests rather than full browser DOM tests.
- [ ] Manual direct-HTTP verification against a non-production test dataset
- [ ] Record remaining findings with severity

### Milestone 10 - Final architecture/documentation review

Status: NOT STARTED

---

## Test status

- Tracked standard-library suite: 17 tests at the time of this section; 82 tests
  as of 2026-08-14, all PASSED.
- Covered enum wire compatibility, live role values, legacy import compatibility,
  valid frontend order payloads, invalid order states, status normalization,
  quantity/money/order-list validation, initial payment/order state mapping, and
  repository SQL parameter/value preservation.
- Post-change application import and OpenAPI generation: PASSED.
- Post-change live read-only repository query smoke verification: PASSED.
- Frontend Node suite: 15 tests, all PASSED. It covers the HTML encoder in
  CommonJS and browser-like VM contexts, template load order/PIN-literal
  contracts, targeted note/name sinks, numeric key mapping, device-ID handler
  separation, Socket.IO table text/ID contracts, and staff authentication
  race condition contracts.
- JavaScript syntax checks: PASSED for `security.js`, `app.js`, `waiter.js`,
  `kitchen.js`, `kasa.js`, and `staff_auth.js`.
- `git diff --check`: PASSED; only Windows LF/CRLF conversion warnings remain.
- `pytest` is unavailable.
- FastAPI `TestClient` cannot run because `httpx` is not installed. Endpoint
  checks were instead driven directly through the ASGI interface.
- The repository `.venv` interpreter works; it was used on 2026-08-14 to run the
  tracked suite (82 tests, all PASSED) and read-only live SQL inspection.
- The ignored `scratch/test_security.py` is stale and unsafe to run against the
  current database.

---

## Blockers / required manual decisions

1. **Staff credential migration approval:** RESOLVED. User approved the credential data migration. Migration script `scripts/migrate_credentials.py` generated and awaits execution.

2. **Customer-session schema approval:** required before Milestone 4. Exact DDL
   will be prepared after the Milestone 1/2 auth primitives and ownership
   contract are finalized; no schema change has been applied.

3. **Payment/option data-model decision:** authoritative option/extras pricing
   and durable partial payments cannot be safely inferred from the current
   schema. Any proposed DDL will be presented separately for approval.

---

## Exact next action

Proceed to Milestone 8 (Multiple-device/session behavior) and Milestone 9 (Security Audit & Test Verification). Run tests for WebSocket authentication and endpoint security matrix.
