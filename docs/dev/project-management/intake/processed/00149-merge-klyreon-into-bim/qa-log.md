# Q&A log: 00149 merge klyreon into bim

## 2026-11-15

- **Do hand-written notes ever carry claims and join the contradiction
  check?** No. Only notes in the agent folder carry claims. Private notes
  never reach the LLM.
- **General agent folder or engine folder only?** General. The folder sits
  under `notes/` and is named `tiromex` ("Memex as if I also had Tiro,
  Cicero's secretary"). Any agent may write there; the engine owns a
  subfolder. (Also settles old question 3: under `notes/`.)
- **Command group name?** `bim tx` (`tx` = tiromex).
- **Where do source documents live?** In an archive of mirrored content: a
  general container for articles, book passages, web clippings, screenshots,
  voice recordings and more. The mirror repository directory already exists;
  bim's config has no key for it yet.
- **Mirror archive in or out of this work?** In. Design mirrors here.
- **Mirror layout?** More complex than one path: there can be local mirrors
  in directories not synced through git or iCloud. Details still to elicit.
- **What gates interactive agents outside `notes/tiromex/`?** The bim skill
  text only. No Seatbelt change in this work.
- **Does `bim doc` move onto the shared LLM backend layer?** Yes, one layer.
- **Where is the mirror?** `~/git/src/gitlab.com/buvis/mirror` (a git repo).
  Top-level folders (names only, listed with the owner's leave): `clippings/`,
  `pocket/`, `readwise/` (`articles/`, `books/`, `Full Document Contents/`),
  `readwise-unofficial/` (`Articles/`, `Books/`, `Supplementals/`).
- **How does tx treat a mirror?** Read-only. bim registers named mirror
  roots; tx records each ingested file (root, path, content hash) in bim state
  and re-ingests when the hash changes.
- **Where does `bim create -t article` put originals?** Into the git mirror.
  `path_articles` retires.
- **A note cites a local-only mirror absent on this machine?** Valid; bim
  reports "not on this host", never a dangling link.
- **Existing originals under `path_articles`?** Migrate them into the mirror
  and repoint the `article::` links.
- **plan-port drops** (init and root config, assets group, clock offset,
  `oversized-body` on sources, `is_human_authored`, klyreon `manifest.toml`):
  all six dropped. Port and redesign rows approved as one table.
