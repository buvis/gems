step: /work Phase 3 (build gate), task-boundary handoff after task 7/9 | PRD 00055-bim-cli-modularization-v1.md
invariants:
- build is ONE session (selection/catchup/design/planning/work) with no mid-build handoff EXCEPT this task-boundary handoff — resume re-enters Phase 3 by artifact (pending tasks remain in state.tasks), not Phase 0-2 re-run logic
- tasks 1-7 completed and committed (HEAD ff290711); tasks 8 (doc_cli.py report_result swap) and 9 (split test_cli.py) remain pending, task 8 blocked_by=[1] (satisfied), task 9 blocked_by=[6,7] (satisfied)
- qwen_preflight cache was invalidated this session (watchdog-judged hang on task 7's dispatch, salvaged successfully) — next qwen-eligible task re-probes before dispatch
- per-task pipeline: claim (task-start) -> Tess/Ivan or qwen per routing table (skipped for pure-move tasks per this PRD's established precedent, tasks 1-5) -> commit -> step 5.5 verify -> step 5.6 self-deslop -> step 5.7 Pat review -> task-done
next: resume Phase 3 in a fresh session, claim task 8, then task 9, then hand off to review (autopilot phase-done --outcome tasks_done) once all 9 tasks complete
