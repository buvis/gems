# Discovery review: 00157

Date: 2026-11-15. All five comprehensive-depth lenses applied.
Result: ready for four implementation PRDs; no unresolved blocking findings.
This is the author's five-lens discovery review, not an independent implementation
review. The corrected isolated native lifecycle test passed. No experiment used
the user's live configuration or installed an update.

## Findings

1. **Completeness — resolved:** The native test establishes the observation
   contract. decisions.md settles baseline acceptance, candidate validation,
   application and retention under standing authorization. Four named slices
   preserve every original requirement and distinguish capture from ancestry.
2. **Coherence — resolved:** The bridge route preserves verified-completion and
   restart requirements. Dispatch-only is not treated as an equivalent fallback;
   a missing bridge must report unobservable state rather than claim success.
3. **Integrity — resolved in discovery:** The original idea treats snapshot
   availability as sufficient ancestry. Source inspection shows clone metadata
   records the app version even for personal or edited parents. Discovery now
   distinguishes historical shipped source, observed snapshots, and accepted
   merge bases, preserving unknown ancestry as unresolved.
4. **Feasibility — resolved:** Installing a file alone cannot enable probing.
   The isolated experiment verified loaded delivery, persisted fresh nonces,
   actual quit/relaunch recovery, absent-block failure and layout restoration.
   PRD 00157 explicitly separates installation from loading. Splitting the epic
   into bridge, snapshots, update control and attended ports keeps build/review
   boundaries clear. No upstream cooperation or new agent launcher is required.
5. **Evolvability — resolved in discovery:** A pre-sysup-restart snapshot cannot
   observe every app-owned update, and clone-of-clone data cannot safely collapse
   to a release-version key. The requirements retain content identity, capture
   basis, home identity, raw inputs and protected references without prematurely
   fixing a storage schema. Separate update and porting slices preserve their
   different consent and execution lifecycles.

## Gate disposition

PRDs 00157–00160 cover the intake. The first retains the intake ID; later IDs
were checked across backlog, wip, done, hold, intake and legacy discovery.
Each uses the standard RPG template and passes the grounding gate. Their opus
floors follow concurrency, durable mutation and new shared-contract requirements.
All four specs passed validation; the intake is now under processed.

Final cross-spec review tightened three contracts: null check timestamps cannot
be mistaken for a completed post-dispatch check; the selected configuration's
storage budget reaches both runner and standalone commands; external validation
is explicitly operator-attested rather than falsely described as enforced by
sysup. Runtime operator approvals are simulated in implementation tests.

No blockers are deferred. Actual update installation and arbitrary candidate
correctness are outside the spike; their failure/recovery scenarios are explicit
implementation acceptance work, not claims of completed implementation.

Documentation checks cover local source links and whitespace. Earlier 00156
tests cover existing sysup behavior only and are not evidence for these new
contracts. No implementation tests apply to this discovery-only change.
