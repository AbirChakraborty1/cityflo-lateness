# Verdict table — 07:45 IST, 2026-06-17

| route | verdict | note |
|---|---|---|
| Borivali → BKC (route 11) | CALL_DRIVER | GPS shows no movement from the origin stop for 59 min -- not congestion, may not have left |
| Ghatkopar → BKC (route 21) | PUSH_LATE 19 min | projected to reach the next unserved stop 19 min after the promised time |
| Mulund → Andheri E (route 12) | PUSH_LATE 14 min | projected to reach the next unserved stop 14 min after the promised time |
| Vashi → Worli (route 17) | NO_VERDICT | last position is 17 min old -- can't trust a number this stale |
| Thane → Powai (route 9) | HOLD | trip already complete -- informational only, nothing to push now |
| Kandivali → Lower Parel (route 14) | HOLD | running close to its typical pace |

## Worry order (chase in this order if you can only do one)

1. **Route 11 (Borivali → BKC)** — CALL_DRIVER — GPS shows no movement from the origin stop for 59 min -- not congestion, may not have left
2. **Route 21 (Ghatkopar → BKC)** — PUSH_LATE, 19 min — projected to reach the next unserved stop 19 min after the promised time
3. **Route 12 (Mulund → Andheri E)** — PUSH_LATE, 14 min — projected to reach the next unserved stop 14 min after the promised time
4. **Route 17 (Vashi → Worli)** — NO_VERDICT — last position is 17 min old -- can't trust a number this stale
5. **Route 9 (Thane → Powai)** — HOLD — trip already complete -- informational only, nothing to push now
6. **Route 14 (Kandivali → Lower Parel)** — HOLD — running close to its typical pace

## Excluded from this table (rev. C rule 1 — operator 7 vehicles)

- **TRIP_019**, route 21 (Ghatkopar → BKC): internally reads **HOLD** (within 5 min of what riders were promised) — excluded from the rider-facing table per the onboarding SOP, not because the data says it's fine. See DECISION_RECORD.md call #2.
