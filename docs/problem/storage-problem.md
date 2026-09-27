# The Storage Problem

## The Scenario

Your *Arr stack is working perfectly: Seerr collects requests, Sonarr and Radarr find releases, qBittorrent downloads them. Then one day the disk fills up.

```
Filesystem      Size  Used  Avail  Use%
/mnt/storage    10T   9.2T  800G   92%
```

Three large 4K remux requests arrive concurrently:

| Request | Size | Decision |
|---------|------|----------|
| Request A | 300 GB | ALLOW (800G free) |
| Request B | 300 GB | ALLOW (800G free) |
| Request C | 300 GB | ALLOW (800G free) |

**All three see 800 GB free. All three proceed. Total: 900 GB → disk full.**

## Why This Happens

The *Arr stack checks free space at request time, but:

1. **No persistent memory** — Each check is a snapshot
2. **No coordination** — Requests don't know about each other
3. **No reservation** — Space isn't held for in-progress downloads
4. **No lifecycle tracking** — No distinction between "downloading" and "done"

## Real-World Failure Modes

| Failure Mode | What Happens |
|--------------|--------------|
| **Concurrent 4K requests** | Multiple large downloads start simultaneously |
| **Stalled downloads** | Space consumed by incomplete torrents |
| **Hardlink confusion** | Filesystem space ≠ logical size |
| **External writers** | Other processes consume space silently |
| **Inode exhaustion** | Millions of small files fill inode table |

## What You Need

A system that:

1. **Checks before admitting** — Every request evaluated against current reality
2. **Reserves capacity** — Accepted requests hold their space
3. **Accounts for concurrency** — Outstanding reservations reduce available space
4. **Tracks lifecycle** — Knows when space can be returned
5. **Reconciles reality** — Compares reservations with actual filesystem/qBittorrent state
5. **Fails closed** — When safety can't be verified, deny the request

---

## How Guardarr Fixes This

Guardarr sits between your request layer (Seerr/Sonarr/Radarr) and your downloader (qBittorrent):

```
Seerr/Sonarr/Radarr
       ↓
   Guardarr
       ↓
  ┌─────────────┐
  │ Filesystem  │
  │   Stats     │
  └─────────────┘
       ↓
  ┌─────────────┐
  │ Reservation │
  │   Ledger    │
  └─────────────┘
       ↓
   Admission Decision
       ↓
   qBittorrent
```

The reservation ledger is the single source of truth. Space is accounted for **before** the download starts, not after.

---

## Next: [How Guardarr Helps](how-guardarr-helps.md)
