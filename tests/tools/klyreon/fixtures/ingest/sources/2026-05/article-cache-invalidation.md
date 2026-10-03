---
id: article-cache-invalidation
title: Why cache invalidation is hard
created: 2026-05-01T09:00:00+02:00
type: article
tags:
- caching
- distributed-systems
article-author: Jane Doe
article-publication: example.dev
article-url: https://example.dev/cache-invalidation
---

# Why cache invalidation is hard

<!-- stub-marker: article-cache-invalidation -->

A cache serves stale data the moment the source of truth changes and the cache
does not. Invalidation is the act of removing or refreshing an entry so the
next read sees the new truth. The hard part is that the write and the
invalidation are two steps, and anything observing the cache between them sees
the stale value. Time-to-live bounds the staleness without coordination, at the
cost of serving stale data for up to the TTL.
