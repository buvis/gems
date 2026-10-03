---
id: transcript-arch-review-2026-05-01
title: Architecture review call 2026-05-01
created: 2026-05-01T09:15:00+02:00
type: transcript
tags:
- architecture
transcript-event: call
transcript-participants:
- Alice
- Bob
transcript-recorded: 2026-05-01T08:30:00+02:00
---

# Architecture review call 2026-05-01

<!-- stub-marker: transcript-arch-review-2026-05-01 -->

Alice: The queue backs up whenever the downstream slows, and retries make it
worse. Bob: Right, so bounded retries plus a dead-letter queue. Alice: And a
concurrency cap on the consumer, otherwise we just move the pileup upstream.
Bob: Agreed. The cap is the real fix; retries only buy time.
