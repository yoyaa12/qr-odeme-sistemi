# Implementation Status

Last updated: 2026-08-19 (3) +03:00

## Overall status

### 2026-08-17 - Independent re-verification pass

The 2026-08-14 reset (below) has now been worked through. Every milestone was
re-checked against the current code, the live database and executed tests. The
markers re-ticked in this document are backed by the evidence recorded in the
per-milestone `Status` lines; anything still unchecked was **not** confirmed.

Evidence collected on 2026-08-17:

- `python -m unittest discover -s tests`: **184 tests, OK** (was 125 at the
  start of the day; 59 added, 2 tautological ones removed).
- `node --test "tests/frontend/**/*.test.cjs"`: **34 tests, 34 pass** (was 27).
- Read-only live SQL inspection: 9 tables present, all 8
  `Kullanicilar.sifre_hash` values are `pbkdf2_sha256$...` encoded hashes,
  `CustomerSessions` and `MasaTahsilatlari` exist.
- Route/OpenAPI audit through the real application object: 34 operations,
  22 publish a `StaffBearer` security requirement; the 12 open ones are the
  HTML pages plus `/api/kategoriler`, `/api/urunler`, `/api/auth/login`,
  `/api/garson/verify-pin`, `/api/masalar/{id}/verify-qr`.
- **Mutation testing**: the two new suites were re-run with the guard under
  test deliberately removed, and they failed. `test_milestone9_security_audit`
  stayed green during the same mutation, which is why its scenarios 8 and 15
  are not accepted as evidence (see the Milestone 5 note).

New findings from this pass are recorded under `Security findings` as
`2026-08-17`.

### 2026-08-14 reset notice

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

### Milestone 9 - Security audit and test verification (PARTIAL) and Milestone 10

Milestones 0-8 are verified as of 2026-08-17. Milestone 9's automated scenario
coverage is now genuine; what remains is:

- application-wide stored/DOM XSS regression testing,
- manual direct-HTTP verification against a non-production dataset,
- Milestone 10 documentation review (first deliverable produced:
  `docs/PROJE_MIMARI_SUNUM.md`).

No open defect blocks Milestone 9 sign-off. The findings raised during the
re-verification pass (stock oversell, catalog limits, the tautological tests,
the stale-session hole) were all approved and closed on 2026-08-17; what is
left is test breadth, not known defects. See `Security findings / 2026-08-17`.

---

## Milestones verified on 2026-08-17

### Milestone 0 - Existing system analysis

Status: VERIFIED 2026-08-17 (analysis re-run; the endpoint inventory and
plaintext-credential statements further down this file are a 2026-08-11
snapshot and no longer describe the system - see the dated corrections)

Completion verification:

- [x] Inspect project directory structure
- [x] Identify backend framework
- [x] Identify controller/router structure
- [x] Identify service layer
- [x] Identify repository/data-access layer
- [x] Identify database models and live schema
- [x] Identify schemas/DTOs
- [x] Identify current authentication implementation
- [x] Identify QR/token implementation
- [x] Identify staff login implementation
- [x] Identify order endpoints
- [x] Identify table endpoints
- [x] Identify payment endpoints/behavior
- [x] Identify WebSocket/socket implementation
- [x] Identify current tests and test-runtime state
- [x] Identify known authorization vulnerabilities
- [x] Trace the reported table-ID active-order disclosure end to end
- [x] Compare documentation claims with real code and live schema
- [x] Produce a concrete, incremental implementation plan

No production data was modified. Live SQL verification was read-only.

---

## Independent hardening batches pending re-verification

### Public PIN hints and targeted frontend XSS sinks

Status: VERIFIED 2026-08-17 (Node contract suite covers the encoder, load
order and every targeted sink; 27/27 pass. The scope limit below still
applies: this is not an application-wide XSS claim)

- [x] Removed the public waiter credential list from `templates/garson.html`.
- [x] Replaced the table-verification placeholder that repeated a live staff PIN
  with generic text.
- [x] Added one browser/CommonJS-compatible HTML text encoder and loaded it
  before the customer, waiter, kitchen, and cashier scripts.
- [x] Encoded the confirmed Socket.IO-controlled table-name rendering sinks and
  normalized Socket.IO table IDs to positive integers before using them.
- [x] Encoded customer order names/notes at the targeted cart, tracking, waiter,
  kitchen, and cashier `innerHTML` sinks.
- [x] Replaced note-derived DOM IDs/inline arguments with numeric indexes backed
  by internal key maps.
- [x] Kept client-controlled device IDs out of inline JavaScript by resolving a
  numeric button index in a static click listener.
- [x] Changed the browser-restored waiter identity badge to `textContent`.
- [x] Added and executed 8 Node tests plus syntax checks for all five affected
  JavaScript files.
- [x] Re-executed all 17 Python tests.
- [x] Independently reviewed the targeted diff.

Scope limit: this is not an application-wide XSS completion claim. Because the
admin mutation endpoints are still anonymous, raw catalog/category/image/table
values can still be persisted and reach other `innerHTML` or inline-handler
sinks in `static/js/app.js`, `static/js/admin.js`, and `static/js/kasa.js`.
Those residual sinks remain a HIGH open finding for a later focused batch.

### Staff login response schema TTL fix

Status: VERIFIED 2026-08-17 (`app/schemas/auth/response.py` bounds are `le=365*24*3600`
in both `LoginResponse` and `GarsonPinResponse`; covered by
`test_login_and_pin_response_supports_extended_ttl`)

- [x] Fixed `HTTP 500 Internal Server Error` on `/api/auth/login` and `/api/garson/verify-pin`.
- [x] Increased upper bound for `expires_in` in `LoginResponse` and `GarsonPinResponse` (`app/schemas/auth/response.py`) from `le=3600` to `le=31536000` (`365 * 24 * 3600`), allowing configured staff JWT token TTLs (e.g., 30 days = `2592000` seconds).
- [x] Added unit test `test_login_and_pin_response_supports_extended_ttl` in `tests/test_enums_and_schemas.py`.

### Kasa grid salonContainer/bahceContainer ReferenceError fix

Status: VERIFIED 2026-08-17 (`static/js/kasa.js:337-344` resolves both
containers with null guards; the ids match `templates/kasa.html:90,98`)

- [x] Fixed `ReferenceError: salonContainer is not defined` in `renderKasaGrid` (`static/js/kasa.js`).
- [x] Defined `salonContainer` and `bahceContainer` variables using `document.getElementById('kasaGridSalon')` and `document.getElementById('kasaGridBahce')` with null safety checks before rendering innerHTML.

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
- Models, split per domain under `app/schemas/` (2026-08-20). Each domain is a
  package rather than a single module:
    - `auth/`, `catalog/`, `orders/`, `tables/`
    - `entity.py`   - database row shape (`TypedDict`), read by repositories
    - `request.py`  - incoming request bodies
    - `response.py` - outgoing response bodies
    - `orders/dto.py` - service-to-service intermediates that never leave
  `app/schemas/common.py` holds the two generic success responses;
  `app/schemas/schemas.py` is compatibility-only.
- Realtime event bus and Socket.IO adapter: `app/core/events.py` and
  `app/core/socket_manager.py`.
- QR/TOTP implementation: `app/core/totp_service.py`.
- No ORM. Repositories return plain `dict` rows from raw SQL; the `entity.py`
  modules declare those row shapes as `TypedDict`, so the columns a query
  returns are visible from the method signature without reading its SQL. This
  is type-level documentation only - there is no runtime conversion.
- Type coverage as of 2026-08-20: repositories 48/48 and API endpoints 28/28
  declare return types; `tests/test_model_layer_contract.py` keeps both at
  100% and fails if a route ships without a `response_model`.

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
- `Siparisler.customer_session_id -> CustomerSessions.id` (nullable, added
  2026-08-19 by `scripts/add_customer_session_to_orders.py`)
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
- Catalog names/descriptions/image URLs carry database-aligned maximum lengths
  as of 2026-08-17 (`app/schemas/catalog/request.py`).
- Nonnegative client price and total fields remain in the request contract and
  are still trusted by the service; validation alone does not make them
  authoritative-safe.
- `SiparisResponse` exposes `device_id`; that response is currently available
  anonymously and is also broadcast globally over Socket.IO.

---

## Current authentication and authorization mechanisms

> **SUPERSEDED - 2026-08-11 snapshot.** The Staff subsection below describes the
> pre-Milestone-2 system and is factually wrong today. Current behaviour
> (verified 2026-08-17): `POST /api/auth/login` and `POST /api/garson/verify-pin`
> verify a PBKDF2-SHA256 encoded hash (a dummy hash is verified for unknown
> users to equalise timing), are throttled per IP and per account
> (5 failures / 5 minutes -> 429), and return a signed HS256 STAFF access token.
> `get_current_staff` validates signature, `iss`, `aud`, `typ`, `exp`, `iat`,
> token type and re-checks the role against `Kullanicilar` on every request.
> `require_roles(...)` provides the reusable role guard. No endpoint accepts
> `garson_adi` as identity any more - it was removed from both order request
> models. The Customer QR/TOTP subsection below is still accurate.

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

> **SUPERSEDED - 2026-08-11 snapshot.** The three lists below described the
> system before Milestones 3-5. Re-audited on 2026-08-17 through the real
> application object: every route named under "Anonymous sensitive reads" and
> "Anonymous sensitive mutations" now requires authentication, and OpenAPI
> publishes a `StaffBearer` scheme with 22 of 34 operations carrying a security
> requirement. The lists are kept for historical traceability only; the current
> inventory is below them.
>
> **Current inventory (2026-08-17).** Deliberately public: the HTML pages,
> `GET /api/kategoriler`, `GET /api/urunler`, `POST /api/auth/login`,
> `POST /api/garson/verify-pin` (rate limited) and
> `POST /api/masalar/{id}/verify-qr` (rate limited).
> `GET /api/masalar` stays reachable without a token because the customer menu
> reads the table name, but browsing detail (`secim_durumu`) is returned only
> when `get_optional_staff` resolves a staff principal. Everything else requires
> a staff role, a customer session bound to the same table, or both.

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

### 2026-08-17 - findings from the independent re-verification pass

Status of the 2026-08-11 CRITICAL list: **all six are closed.** 1, 3 and 5 are
closed by the route guards (re-audited today); 2 is closed because both
dynamic-QR endpoints now require `admin`/`kasa`; 4 and 6 are closed by
server-side repricing and by the fact that `odeme_yontemi` only selects the
initial state while every later transition is role- and state-machine-checked.
The 2026-08-11 HIGH list items 1, 2, 3, 5, 8 are likewise closed and now have
tests that fail when the guard is removed.

Open findings raised today:

1. **HIGH - stock oversell on a lost race. REMEDIATED 2026-08-17 (user
   approved).** `execute_update` was added to `app/database.py` to return the
   affected row count (`execute_non_query` loses it by reading
   `SCOPE_IDENTITY()` afterwards), `UrunRepository.update_stock` now returns it,
   and `SiparisService._deduct_stock_or_fail` raises `HTTP 409` on zero rows,
   which rolls back the surrounding `db_transaction()` together with the order
   row. Applied on both the create and the edit path. A driver that cannot
   report a row count returns `-1` and is treated as "unknown", so it degrades
   to the previous behaviour rather than rejecting valid orders; `pyodbc` was
   measured returning 1/0/0 correctly against the live database inside a
   rolled-back transaction. Original finding follows.

   `UrunRepository.update_stock` issued
   `UPDATE Urunler SET stok_miktari = stok_miktari - ? WHERE id = ? AND stok_miktari >= ?`
   but `execute_non_query` returns `SCOPE_IDENTITY()`, never the affected row
   count, and no caller inspects it. Two devices ordering the last unit both
   pass the pre-check (`_assert_stock_available` reads a stale value under READ
   COMMITTED), the first `UPDATE` succeeds and the second matches zero rows.
   The second order is still created and confirmed to the customer while stock
   was never decremented. Negative stock is prevented; overselling is not.
   Fix requires a row-count check plus a decision on the customer-visible
   failure (`409`), which is a business-behaviour change -> user approval.
2. **MEDIUM - catalog request fields have no maximum length.
   REMEDIATED 2026-08-17.** `app/schemas/catalog/request.py` now declares named
   constants taken from the live schema (`urun_adi` 100, `aciklama` 500,
   `gorsel_url` 255, `kategori_adi` 50, money `99999999.99`, stock
   `2147483647`) and applies them to `UrunEkleModel`, `UrunGuncelleModel` and
   `KategoriEkleModel`. Over-long or over-large values now fail as 422 instead
   of reaching SQL Server as a 500. Covered by
   `tests/test_catalog_validation.py` (13 tests, mutation-tested). Closes the
   last open Milestone 1 sub-item.

2b. **LOW - `SiparisItemModel.adet` is unbounded above.** Only `gt=0` is
   declared. A very large quantity on a product with enough stock would
   overflow the `decimal(10,2)` line total and produce a 500. Capping a line
   quantity is a business-rule decision under AGENTS.md §3, so it is recorded
   here rather than applied.
3. **LOW - `masa=99` developer bypass in the client.**
   `static/js/app.js` skips the entire QR verification block for table 99 and
   rewrites table 1 to 99 for one hard-coded LAN host. The backend still demands
   a token, so it is not an exploitable bypass, but it is dead unsafe-looking
   code that must not ship.
4. **LOW - a successful QR verification clears the shared table bucket.**
   `MasaService.verify_dynamic_qr_with_device` calls
   `limiter.record_success(rate_keys)` with both the IP and the `qr-verify-masa`
   key, so one legitimate scan resets the brute-force counter for that table.
   Exploiting it still requires one valid code first.
5. **INFO - documentation drift.** The CHANGELOG entry for Milestone 4 lists
   `app/api/v1/dependencies.py` and a `require_customer_session` dependency;
   neither exists. The equivalent code lives in `app/auth/dependencies.py` as
   `get_current_customer` / `get_current_user_or_customer`.
6. **INFO - a test that cannot fail. REMOVED 2026-08-17.**
   `tests/test_milestone9_security_audit.py` scenarios 8 and 15 raised the
   expected `HTTPException` inside `assertRaises`, so they passed no matter what
   the routers did. Both were deleted and replaced with comments pointing at
   `tests/test_customer_session_authorization.py`, which drives the real ASGI
   application.

7. **HIGH - stale customer session after an automatic table empty.
   REMEDIATED 2026-08-17 (user approved).** A table reaches `bos` by two routes:
   the cashier clearing it, and automatically once everything is delivered and
   paid. Only the cashier route closed the check. After an automatic empty the
   previous party's sessions stayed valid for the rest of their lifetime, and
   once the next party claimed the table with a fresh code the stale session
   could append orders to their bill without any physical proof - the exact
   troll scenario AGENTS.md §14 exists to prevent. The same gap also returned
   the previous party's delivered orders as active to whoever sat down next.
   Both routes now run `SiparisService._close_masa_session`, which closes the
   orders, closes the collections, revokes every session for the table and
   clears the browsing entry. Covered by `tests/test_table_session_boundary.py`
   and mutation-tested.

8. **MEDIUM - Socket.IO room membership outlives session revocation.**
   Revoking a customer session in the database does not disconnect a socket
   that already joined `table_{id}` during its handshake; room membership is
   in-process and lasts until the client disconnects. A departed guest whose
   session was revoked therefore keeps receiving that table's realtime events
   until their browser closes the connection. They cannot act on them - every
   HTTP mutation re-checks the session - so this is disclosure, not privilege.
   Fixing it requires tracking `sid -> session` and kicking those sockets when
   a check closes.

### CRITICAL

> Historical - 2026-08-11 list. All six are closed as of 2026-08-17; see the
> dated section above.

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
2. **REMEDIATED 2026-08-17.** TOTP accepted the current +/- two 30-second
   windows, wider than documented. The tolerance is now a named constant
   `TOTP_WINDOW_TOLERANCE = 1` in `app/core/totp_service.py`, so a scanned code
   lives 30-59 seconds instead of 60-89. This matters more than it looks: the
   client stores the code from the QR URL and attaches it to the first order
   automatically, so the tolerance *is* the maximum age of the physical-presence
   proof. Covered by a lifetime test that fails if the constant moves.
3. **REMEDIATED 2026-08-17.** Delivered orders were still returned as active
   because the repository excludes only `iptal` and `odendi_kapatildi`. The
   query is unchanged, but a table that empties now closes its orders out to
   `odendi_kapatildi` on both routes, so a delivered-and-paid order no longer
   lingers as active for the next party.
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

Status: VERIFIED 2026-08-17 (enums carry the live lowercase values, DTOs are
split by feature with a complete legacy facade, and the validation rules are
covered by `test_enums_and_schemas`, `test_order_status_mapping` and
`test_repository_enum_queries`. Open sub-item: catalog name/description/
image-URL maximum lengths are still missing - see 2026-08-17 findings)

- [x] Added string enums for verified user roles, table states, payment methods,
  payment states, persisted order states, the legacy cash-collection command,
  and future staff/customer token types.
- [x] Preserved the existing lowercase SQL/API wire values.
- [x] Split the mixed schema file into `auth`, `catalog`, `common`, `orders`, and
  `tables` modules.
- [x] Kept `app.schemas.schemas` as a complete legacy import facade, including
  the previously unused `GarsonResponse` symbol.
- [x] Rewrote application imports to use the responsible feature module.
- [x] Updated Python services/repositories to use enum values rather than
  duplicated role/table/payment/order magic strings.
- [x] Used JSON-mode model dumps at raw Socket.IO/dict boundaries so enums remain
  plain wire strings.
- [x] Added positive-ID/quantity, nonnegative money/stock, nonempty-order, and
  conservative selected length validation without changing BOS -> DOLU
  behavior.
- [x] Limited the legacy status endpoint to known states/commands while
  preserving its previous case normalization.
- [x] Added a tracked standard-library `unittest` suite.
- [x] Executed 17 tests successfully.
- [x] Regenerated OpenAPI successfully after the refactor.
- [x] Executed the changed parameterized repository reads against the live SQL
  Server successfully and without writes.

API validation change: payloads with arbitrary order states, non-positive item
quantities, negative price/total/stock values, empty order item lists, or invalid
IDs now fail Pydantic validation (normally HTTP 422). Client price and total are
still not authoritative-safe merely because negative values are rejected; the
backend still needs DB price recomputation in Milestone 6.

### Milestone 2 - Staff authentication

Status: VERIFIED 2026-08-17 - MIGRATION EXECUTED. Read-only live inspection
confirms all 8 `Kullanicilar.sifre_hash` values are `pbkdf2_sha256$...`
encoded hashes (87 chars); no six-digit plaintext remains. `AUTH_SECRET_KEY`
is present in `.env`. Covered by `test_staff_auth.py`, including real ASGI
route checks for 401/403/200.

- [x] Add secure password verification and short-lived signed STAFF access tokens.
- [x] Add reusable missing/invalid/expired/wrong-token-type handling.
- [x] Remove public credential hints.
- [x] Stop trusting browser-stored identity as authentication.
- [x] Existing six-digit plaintext values must be replaced with encoded hashes in
  `Kullanicilar.sifre_hash`. The column is already wide enough; no schema alter
  is required. (Migration script `scripts/migrate_credentials.py` is ready for execution).
- [x] A strong `AUTH_SECRET_KEY` must be supplied through environment configuration. (Added to `.env`)

### Milestone 3 - Role-based authorization

Status: VERIFIED 2026-08-17. Route/OpenAPI audit: every admin, order, table,
QR-display, ban and payment operation requires a staff role. A real ASGI test
drives `POST /api/admin/urunler` and observes 401 (no token), 401 (invalid),
403 (waiter) and 200 (admin). The role matrix is now documented in
`docs/PROJE_MIMARI_SUNUM.md` §6.3 and §7.4.

- [x] Protect admin, waiter, kitchen, cashier, QR-display, table move/clear, ban,
  order list/update, and payment-changing operations using a documented role
  matrix.
- [x] Add service-level transition and object checks (`app/services/order_authorization.py`).

### Milestone 4 - QR customer session authentication

Status: VERIFIED 2026-08-17. `CustomerSessions` is live, tokens are 64-hex
and stored only as SHA-256 digests, `verify-qr` issues them, and the
BOS -> DOLU rule is now covered by `tests/test_first_order_physical_verification.py`
(18 tests, mutation-tested). Naming deviation: the dependency is
`get_current_customer` / `get_current_user_or_customer` in
`app/auth/dependencies.py`, not `require_customer_session`, and
`app/api/v1/dependencies.py` named in the CHANGELOG was never created.

- [x] Design a database-backed `CustomerSessions` table with hashed session tokens,
  expiration, revocation, and table binding. (Schema script created; table
  confirmed live on 2026-08-17 with columns `id, session_token_hash, masa_id,
  device_id, created_at, expires_at, is_active`.)
- [x] Implement backend token generation, hashing, and database storage in AuthRepo/AuthService.
- [x] Update `verify-qr` endpoint to return a secure session token upon success.
- [x] Create a `require_customer_session` dependency to enforce token validation.
- [x] Update `/api/siparisler` POST endpoint to require either a valid `CUSTOMER_SESSION` or a `current_totp_token` (for BOS -> DOLU).
- [x] Update frontend `app.js` to store the received session token and send it in the Authorization header.

### Milestone 5 - Table/order object-level authorization

Status: VERIFIED 2026-08-17 by `tests/test_customer_session_authorization.py`
(6 real ASGI tests). Removing either ownership check makes them fail, while
`test_milestone9_security_audit` scenarios 8 and 15 stay green - those two
raise the expected `HTTPException` themselves and prove nothing.

- [x] Added `get_current_user_or_customer` hybrid auth dependency to allow either staff or authenticated customer sessions.
- [x] Secured `/api/masalar/{masa_id}/aktif-siparis` to prevent IDOR by checking ownership of the session token.
- [x] Secured `/api/siparisler` endpoints to require appropriate authentication.
- [x] Updated frontend `app.js` checkActiveOrder to send the `CUSTOMER_SESSION` token in the Authorization header.

### Milestone 6 - Order and payment business-rule hardening

Status: VERIFIED 2026-08-17. Authoritative pricing, active-product and stock
checks, the idempotency guard and the fail-closed state machine are covered by
real tests. The last open sub-item, atomic stock deduction, was fixed the same
day: the row count of the conditional `UPDATE` is now checked and a lost race
raises `HTTP 409`, rolling the order back. See 2026-08-17 finding 1
(REMEDIATED).

- [x] Authoritative backend price and total recalculation based on database product base prices and option deltas.
- [x] Rejection of underpaid/manipulated unit prices (`HTTP 400`).
- [x] Product active state verification (`aktif_mi == 1`). Rejection of inactive product orders (`HTTP 400`).
- [x] Insufficient stock check (`stok_miktari >= item.adet`). Rejection of insufficient stock (`HTTP 400`).
- [x] Atomic stock deduction (`WHERE id = ? AND stok_miktari >= ?`) **and** a
  check on the affected row count. Zero affected rows now aborts the
  surrounding transaction with `HTTP 409` instead of accepting an order that
  never reduced stock. Closed 2026-08-17; covered by
  `tests/test_stock_oversell_guard.py`.
- [x] Idempotency guard for duplicate order submissions within 5 seconds.
- [x] Centralized state transition validation (`validate_order_state_transition`), preventing invalid backward transitions and modifications to terminal states (`CANCELLED`, `PAID_CLOSED`).
- [x] Added automated unit tests in `tests/test_order_business_rules.py`.

### Milestone 7 - WebSocket authentication/realtime isolation

Status: VERIFIED 2026-08-17. Handshake authenticates staff JWTs and customer
session tokens, anonymous clients cannot enter `table_*`, table moves do not
relocate anonymous sockets, no event is emitted without a room filter, and
`enter_room`/`leave_room` are asserted to be awaited coroutines.

- [x] Socket.IO handshake authentication (`connect` event) for STAFF (JWT) and CUSTOMER_SESSION (Hex token).
- [x] Room-based socket isolation (`role_garson`, `role_mutfak`, `role_kasa`, `role_admin`, `staff`, `table_{masa_id}`).
- [x] Stopped global unauthenticated broadcasting of sensitive order and operational events.
- [x] Frontend scripts (`app.js`, `waiter.js`, `kitchen.js`, `kasa.js`) pass
  their token in the Socket.IO handshake (`auth: { token }` plus a `query`
  fallback). Verified in source on 2026-08-17.
- Note: a stray fragment about stock/race-condition work was previously glued
  onto the line above. Stock and race-condition handling belongs to Milestone 6
  and is assessed there; the atomic-deduction sub-item is **not** confirmed.

### Milestone 8 - Multiple-device/session behavior

Status: VERIFIED 2026-08-17 for session behaviour; PARTIAL for partial payments.

Defined and enforced multi-device behaviour:

- Several customer sessions may be live on one table at once. Only the guest
  who claims an empty table types the 6-digit code; everyone joining an already
  occupied table proves presence by scanning the QR, which carries the current
  30-second code and is validated by `verify-qr`.
- The bill is shared per table; the cart stays per browser.
- Every session on a table dies when that table's check closes, by either route
  (`_close_masa_session`). This is what separates one party from the next.
- Session lifetime is a sliding 90-minute window refreshed on use, so a seated
  guest never expires mid-meal while a departed guest's session stops being
  renewed.
- Covered by `tests/test_table_session_boundary.py` (13 tests, mutation-tested)
  and `tests/frontend/customer_session_recovery.test.cjs` (7 tests).

NOT confirmed: `add_tahsilat` / `get_masa_tahsilat_toplami` persistence and
summing across a table close still have no test, although the table is live and
`close_tahsilatlar_for_masa` is asserted on both closing routes.

Residual, accepted: a guest who leaves while the check is still open keeps a
usable session until it closes. See 2026-08-17 finding 8 for the Socket.IO
room-membership side of this.

- [x] Milestone 8 (Multiple-device/session behavior & Kısmi Ödeme): Aynı masada birden fazla cihaz/oturum davranışının yönetilmesi, masa kapatıldığında oturumların iptali (session revocation) ve kasa tarafından alınan kısmi ödemelerin kalıcı hale getirilmesi (partial payment persistence).

### Milestone 9 - Security audit, automated tests and manual HTTP verification

Status: PARTIAL 2026-08-17. The 15 required scenarios from
`SECURITY_AUTH_REFACTOR.md` §19 now all have genuine coverage after scenarios
8/9/15 were re-implemented as real ASGI tests. Still open: application-wide
XSS regression testing and manual direct-HTTP verification.

- [ ] Milestone 9 (Final Review & Cleanup): Fazlalık kodların temizlenmesi, güvenlik testleri ve canlı kullanıma hazırlık. HTTP verification
- [x] Full endpoint security audit after implementation
- [x] Missing-token tests
- [x] Invalid-token tests
- [x] Expired-token tests
- [x] Role authorization tests
- [x] Customer/staff token separation tests
- [x] Table/session ownership tests
- [x] Order object authorization tests
- [x] Price/total manipulation tests
- [x] Order state transition tests
- [x] WebSocket auth/room isolation tests
- [ ] Complete application-wide stored/DOM XSS regression tests
  - 8 Node tests now cover the targeted PIN/order-note/Socket.IO sink batch, but
    they are helper/source-contract tests rather than full browser DOM tests.
- [ ] Manual direct-HTTP verification against a non-production test dataset
- [x] Record remaining findings with severity

### Milestone 10 - Final architecture/documentation review

Status: IN PROGRESS 2026-08-17. First deliverable produced:
`docs/PROJE_MIMARI_SUNUM.md` - architecture, technology rationale, data model,
order state machine, authentication flows, realtime design, scaling analysis
and known limits.

---

## Test status

### 2026-08-17

- `python -m unittest discover -s tests` -> **198 tests, OK** (125 before this
  pass; 149 after the verification suites, 160 after the stock-oversell fix,
  171 after the check-boundary work, 184 after the catalog limits, with 2
  tautological tests removed).
  Executed with the repository `.venv` interpreter.
- `node --test "tests/frontend/**/*.test.cjs"` -> **45 tests** (27 before).
- Added `tests/test_stock_oversell_guard.py` (11 tests): the repository uses the
  conditional query and reports its row count, `db_transaction` rolls back on a
  raised exception and commits otherwise, a lost race returns 409 on both the
  create and the edit path, a rejected attempt is not cached as a duplicate, and
  an unknown row count (-1) does not reject a valid order.
- `node --test "tests/frontend/**/*.test.cjs"` -> **27 tests, 27 pass**.
- Added `tests/test_first_order_physical_verification.py` (18 tests). It is the
  first coverage of `SiparisService.create_siparis` and of
  `app/core/totp_service.py`: window tolerance (+/-2 accepted, +/-3 rejected),
  replay consumption, per-table token isolation, the BOS -> DOLU code
  requirement, the DOLU "friend joins" path, banned devices, the idempotency
  window and server-side repricing on create.
- Added `tests/test_customer_session_authorization.py` (6 tests) driving the
  real ASGI app for `GET /api/masalar/{id}/aktif-siparis` and
  `POST /api/siparisler`: no token -> 401, unknown token -> 401, own table ->
  200, another table -> 403, and the service is asserted never to run for a
  rejected request.
- Mutation testing was used to prove both new suites bite: with the ownership
  check removed the active-order test failed `200 != 403`; with the BOS -> DOLU
  block disabled four tests failed. All source files were restored afterwards
  (`git diff` empty).
- Coverage gaps that remain: no test for two concurrent sessions on one table,
  none for `MasaTahsilatlari` persistence/summing, and no browser-level DOM XSS
  regression suite.
- `pytest` and `httpx` are still not installed; HTTP-level tests are driven
  directly through the ASGI interface.

### Earlier

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

1. **Staff credential migration approval:** RESOLVED and EXECUTED. Verified
   read-only on 2026-08-17: all 8 `Kullanicilar.sifre_hash` values are
   `pbkdf2_sha256$...` encoded hashes.

2. **Customer-session schema approval:** RESOLVED and APPLIED. `CustomerSessions`
   exists live with `session_token_hash, masa_id, device_id, created_at,
   expires_at, is_active`. `MasaTahsilatlari` (Milestone 8) is also live.

3. **Payment/option data-model decision:** STILL OPEN. Option pricing is derived
   from Turkish substrings in `urun_notu`
   (`"Orta Boy" in note` -> +40 TL, and so on) inside
   `SiparisService._calculate_item_authoritative_price`. Moving it into the
   catalogue is a schema change and needs approval. `Siparisler` also still has
   no `odeme_yontemi` column, so the payment method is lost on read-back.

4. **Stock oversell fix:** RESOLVED. The user approved the behaviour change on
   2026-08-17 and it is implemented: a lost stock race now returns `HTTP 409`
   instead of confirming an order that never reduced stock.

5. **NEW - process-local state persistence:** `TABLE_MOVES_MAP`,
   `totp_service._used_tokens` and `BROWSING_TABLES` are lost on restart and
   unshared across workers. Persisting them requires new tables.

6. **Stock lifecycle decision:** RESOLVED 2026-08-19 by the user, and
   implemented. The rule is now explicit and has one name in the code:

   > Stock is **reserved** when the order is created and **consumed** when the
   > order reaches `teslim_edildi`.

   Reservation at creation time is deliberate and stays: a neighbouring table
   must not see quantities that another table has already claimed. What was
   missing was the release. `clear_active_orders_for_masa` marks open orders
   `odendi_kapatildi`, not `iptal`, and only the `iptal` path restored stock -
   so a customer who left before the food arrived, or a table force-closed at
   the till, permanently destroyed inventory that was never served.
   `_close_masa_session` now restores every still-undelivered line first, on
   both routes that empty a table.

   Not decided, and deliberately left open: reservations have no expiry. An
   order on a table that is never closed and never delivered holds its stock
   forever. Harmless in the current flow because tables do get closed, but a
   timeout would need its own decision.

7. **Per-device order visibility:** RESOLVED 2026-08-19 by the user, and
   implemented. `Siparisler.customer_session_id` (nullable) now records which
   verified `CustomerSessions` row placed the order. The controller reads it
   from `get_current_user_or_customer`, never from the request body, so the
   answer to "who ordered this" cannot be forged the way `device_id` could.

   The read path returns `is_mine` per order plus `benim_toplamim`, both
   computed server-side. The customer client only filters. The bill total is
   deliberately still the whole table in both views: showing a personal total
   as *the* total would surprise the guest when the bill arrives and would not
   match the till.

   Limits that remain, and are NOT solved by this column:
   - a session is not a person. Two tabs, cleared storage, or a shared phone
     all break the mapping, and there is no login to repair it.
   - orders created before this change have `NULL` and therefore never appear
     under "Benim Siparişlerim". No data was invented for them.
   - this must not become a payment boundary. Per-person payment needs a real
     check/person entity; `MasaTahsilatlari` is per table.

   The original open question is kept below for the record:

   **Was OPEN, user decision required.**
   Today every phone at a table sees the whole table's orders. The data to
   split that view already exists: `Siparisler.device_id` is written on
   creation and returned by `/api/masalar/{id}/aktif-siparis`, and the customer
   client already knows its own `qr_device_id`. So a "Benim Siparişlerim /
   Masanın Tümü" toggle is a client-side filter, not a schema change.

   What it does NOT give: `device_id` is a browser-profile identifier, not a
   person. A phone that clears storage, orders from a second tab, or hands the
   menu to a friend breaks the mapping, and there is no login to repair it. So
   the filter can be an aid to reading the bill, never an authorisation
   boundary or the basis of a split payment.

   Recommendation on record: default the customer view to the whole table
   (it is the truth of what will be charged) and offer the personal filter as
   an explicitly labelled toggle. Do not hide other people's orders by default
   and do not let the filter drive any payment amount.

8. **NEW - partial item transfer granularity:** the 2026-08-19 (2) batch moves
   whole `SiparisDetaylari` rows between tables. Splitting a row by quantity
   ("move 1 of the 3 soups") is not supported and would need its own decision:
   it changes line pricing and produces a second kitchen ticket.

---

## Exact next action

1. ~~Stock oversell row-count check~~ - DONE 2026-08-17.
2. ~~Delete the tautological scenarios 8 and 15~~ - DONE 2026-08-17.
3. ~~Close the check on both table-emptying routes; sliding session expiry~~ -
   DONE 2026-08-17.
4. ~~Add `max_length` to the catalog request models~~ - DONE 2026-08-17.
5. Add a `MasaTahsilatlari` persistence/summing test across a table close.
5b. ~~Decide when stock is deducted (option C from the 2026-08-17 discussion)~~ -
   DECIDED and DONE 2026-08-19: reserve on create, consume on delivery, release
   the undelivered remainder when the check closes. See blocker 6 above and the
   2026-08-19 changelog entry.
5c. ~~Live stock in the customer menu; quantity cannot exceed stock; waiter
   panel shows the receipt to carry, not the table total; cashier item
   selection charges only unpaid quantities~~ - DONE 2026-08-19.
6. Then finish Milestone 9: application-wide XSS regression and manual
   direct-HTTP verification against a non-production dataset.
7. Manual round for the 2026-08-19 batch, on a test dataset: send one
   waiter-approved soup from table 1, watch the "Son X Adet" badge drop live on
   a second table's menu, force-close table 1 at the till and confirm with SQL
   that `Urunler.stok_miktari` went back up by exactly the undelivered
   quantity. Then repeat with the order marked `teslim_edildi` first - stock
   must NOT come back.
8. ~~Cashier "move selected items" moved the whole table regardless of the
   selection~~ - DONE 2026-08-19 (2). `POST /api/masalar/move-items`.
9. ~~Cashier ticket columns clipped four-digit amounts; the details button
   drifted with the product name~~ - DONE 2026-08-19 (2).
10. ~~Receipt lumped order-time payments and till collections into one
   "Önceden Ödenen" line~~ - DONE 2026-08-19 (2); now an itemised
   "ÖDEME BİLGİLERİ" section.
11. Manual round for the transfer: two receipts on one table, move a single
   line to another table, verify both totals against their lines in SQL and
   that `SiparisDetaylari.siparis_id` points at the new header.
12. ~~Blocker 7 (per-device order visibility) needs the user's decision~~ -
   DECIDED and DONE 2026-08-19 (3). `Siparisler.customer_session_id` +
   "Benim Siparişlerim" tab.
13. Manual round for ownership, on a test dataset: open the same table's QR in a
   normal window and in an incognito window, order from each, and confirm that
   each device's "Benim Siparişlerim" shows only its own order while
   "Masanın Tümü" and the bill total show both. Then check with SQL that both
   `Siparisler` rows carry different `customer_session_id` values.
14. Still open, unchanged: `Siparisler` has no `odeme_yontemi` column, so the
   payment method chosen at order time is lost on read-back. Adding it is a
   separate decision (see the 2026-08-19 discussion: the column in
   `MasaTahsilatlari` measures a different thing and must stay where it is).

Future work, not scheduled: introduce a real `MasaOturumlari` (check) entity
with `Siparisler.oturum_id` and `CustomerSessions.oturum_id`. The check boundary
is currently implicit - the table's `bos` transition - which works and is now
enforced identically everywhere, but an explicit entity would make it a database
guarantee and enable per-check reporting and split tables. Requires a schema
change and user approval.

Suggested manual check for the check boundary, on a test dataset: order and pay
by card at table 5, have the waiter mark it delivered, confirm the table shows
`bos` and `CustomerSessions.is_active = 0` for that table, then try to order
again from the same phone - it must ask for the 6-digit code, and after entering
it the order must go through on a clean bill with no items from the previous
party.

Suggested manual check for the stock fix, on a test dataset: set a product's
`stok_miktari` to 1, then fire two `POST /api/siparisler` requests for that
product at the same time. Exactly one must return 200; the other must return
409 with the "stoğu az önce tükendi" message, and `stok_miktari` must end at 0
(never -1, and never 1).
