# Role 5 Historical Macro Data Collector Report

Status: `PASS`  
Decision: `H41_FULL_POINT_IN_TIME_CHAIN_VALIDATED`

## Current status

`[FACT]` H.6 and H.4.1 acquisition are complete. H.4.1 reconciles all 1,228 frozen release identities and produces 3,684 immutable point-in-time observations across total assets, reserve balances, and TGA. The traversal used 1,232 requests including the pilot, with 0 retries and 28 requests of ceiling headroom.

`[FACT]` Exact source exceptions are preserved rather than hidden: 2005-03-05 aliases 2005-03-03; the 2008-07-02 reserve balance is legitimately -6,962 and reconciles to supplying minus absorbing factors; 2016-11-18 aliases 2016-11-17; 2019-11-28 shifts to 2019-11-29; and 2020-05-14 aliases 2020-05-15.

## What failed

`[FACT]` The failed-first H.4.1 pilot sampled one out-of-scope 1996 body before its missing lower bound was corrected. The full traversal preserved 6 stopped parser/source-identity attempts. They exposed one archive alias, one valid signed legacy balance, and three exact directory/body date divergences. No failed record was deleted, retried as if normal, or used without a frozen reconciliation.

## Why later steps did not run earlier

Roles after collection were gated, not skipped. Scoring before complete H.6 revision lineage and H.4.1 source/date validation would have embedded incomplete liquidity history and incorrect availability dates. Role 5 now passes; Role 6 may begin sequentially. Technical alignment, comparison, and independent audit remain closed until their own predecessors pass.

## Exact next permitted action

Start Role 6 deterministic category taxonomy and scoring from the frozen eligible observation set. Do not join technical setups or inspect PnL yet.
