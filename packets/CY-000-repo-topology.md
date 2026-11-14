---
id: CY-000
track: cyclops
phase: 0
status: todo
rung: 1
depends: []
gate: "test ! -d ~/dev/cyclops && git -C ~/dev/cyclops-wearable remote get-url origin | grep -q github.com && git -C ~/dev/cyclops-wearable status --short | wc -l | awk '{exit ($1>2)?1:0}'"
commit: "branch agent/CY-000; per PROTOCOL §6"
---

# Repo topology: one canonical repo, clones become deploy targets

## Why
The same clone-divergence disease that hit physis: feather has ~/dev/cyclops
(on branch freerouting-omniroute, origin = a LOCAL git mirror under
/media/.../git-mirrors/cyclops.git) AND ~/dev/cyclops-wearable (origin
github, main). pansa has ~/dev/cyclops too. Three trees, two remotes, one
correct one. Work that lands in the wrong clone is work that never merges
back — this has already cost sessions on physis.

## Steps
1. Inventory: for each clone (feather ~/dev/cyclops, ~/dev/cyclops-wearable;
   pansa ~/dev/cyclops): branch, origin, unmerged commits
   (`git log --oneline origin/main..HEAD`). Re-measure; facts above are
   2026-09-02.
2. Any real fix found in a non-canonical clone → port to a branch on the
   canonical repo (cyclops-wearable) via normal review. Record in report.
3. The stray branch freerouting-omniroute: report what it contains and why
   (name suggests it was borrowed for an unrelated project's branch). HUMAN
   decides keep-or-delete; agent does not delete branches.
4. Convert non-canonical clones: rename dir to <name>.retired (never delete).
   If a node needs the built brain/app, that is a deploy target (binaries via
   mesh bin-sync), not a source clone.
5. The /media git-mirror: if the drive is mounted, record its role; if it is
   the ONLY backup of unique history, say so loudly in the report before
   anything is retired (RM-006 backup rules apply).

## Tests you must add
- None (topology). Gate = the checks above plus the report table.

## Never
- Delete a clone or branch. Force-push anything. Retire a clone before porting
  its unique commits.
