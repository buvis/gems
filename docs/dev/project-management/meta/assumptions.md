# PRD 00112 assumptions

Task 1: Tess and Ivan reported ASSUMPTIONS: none.

## 2: Emit archive engine progress
Tess quality retry: Clearing PATH represents unavailable system tar; real fallback-message assertion passed. Other test writers and implementors reported none.

## 6: Tail sweep archive progress

Tess: System tar is available. Empty-input coverage uses an empty file. Persistent filesystem failure preserves the observed OSError behavior.

Ivan initial: Fallback retains the system-tar engine string so done_bytes remains None. The assumption that duplicate archiving on early fallback was acceptable was rejected against the existing exact-event test and corrected by the bounded repair. Ivan repair reported none.

## 7: Tail sweep observer documentation

Ivan: Plan suppression means the planning phase emits no progress events. The idle tick interval comes from completed.get(timeout=0.2). Coordinator verified both against Runner.plan/_plan and _collect_completion; paused-yield timing is stated explicitly.
