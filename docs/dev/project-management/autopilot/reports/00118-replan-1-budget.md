# PRD 00118 replan budget stall

The committed replan context imposes a hard 75,000-token estimate per task. Plan-tasks step 4.5 counts the full bytes of each touched file, the PRD slice, the task description, and 55,000 overhead tokens. No host adaptation changes that estimator.

The one file-boundary split isolates CHANGELOG.md (102,781 bytes). Its file-plus-overhead lower bound is 80,696 tokens; the complete estimate is 81,132. Splitting its remaining Added/Changed entries by capability cannot reduce the full-file term, so even a zero-byte requirement and plan would exceed the cap. Changing the estimator to count a selected section would require an explicit workflow change; this session neither changes that rule nor raises the cap.

The existing changelog does not yet document failure exit 1 or stable additive JSON v1 behavior. Thus this write cannot be removed from the remaining scope as already completed. No implementation or completion reviewer was dispatched. The canonical oversized_task stall is required.

Prior code and tests remain committed. Original task 3 still lacks Pat review; its complete prompt previously exceeded 50,000 bytes after the permitted trim. Prior tasks, attempts, model metadata and work_start_sha remain in 00118-replan-1-state-before.json and the original raw worker logs. No old attempt was relabeled or marked complete.

Catchup refreshed GitHub state: no issues, PR 267 affects postup dependencies, latest master CI green. Engram is unregistered, memory loading returned no files, task restore returned no_tasks_dir. Branch script emitted the large retained transcript diff; targeted production inspection confirmed the already shipped command, formatter wiring and allocation changes.

PRDs 00119 and 00120 explicitly require successful completion review of 00118 and remain blocked. They must not implement around this stall.
