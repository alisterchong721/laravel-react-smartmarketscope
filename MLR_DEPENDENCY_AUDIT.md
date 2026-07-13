# MLR Dependency Audit

Status: `FULL_STRATEGY_GATE_FAILED`

| Gate | Result | Evidence |
| --- | --- | --- |
| Installed strategy skill | PASS | Repository skill validates; frozen SHA-256 `83d2e96e8435398571814b340fb5c181f42361ec790c239d7337b3668c1eb050` |
| Critical IDOR remediation | PASS | Sanctum ownership/policy checks and negative IDOR tests recorded in `SMART_MARKETSCOPE_SECURITY_REAUDIT_PROGRAM2.md` |
| Critical SSRF remediation | PASS | Unrestricted route/controller removed and route audit passed |
| Immutable PIT macro contract | FAIL | 25 runs / 1,730 observations / 0 eligible observations |
| Broker identity | UNRESOLVED | Eligible history is probable NAS100 CFD, not Pepperstone-confirmed |
| Source timezone | UNRESOLVED | Source timestamps are naive and cannot be mapped to named sessions |
| Spread units | UNRESOLVED | Raw spread is diagnostic only; MT5 symbol metadata is absent |

Decision: fail the macro-gated strategy closed with
`BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`. The unresolved broker, timezone, and spread
contracts independently prohibit broker-specific execution claims and economic
cost results.

