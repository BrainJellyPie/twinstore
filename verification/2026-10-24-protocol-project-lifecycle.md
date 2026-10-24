# Protocol history and project deletion

Protocol writes held their local update lock but did not coordinate with
project deletion. Late creation/amendment writes could recreate a deleted
project; an idempotent retry could also acknowledge a plan while deletion was
in progress. All ten new overlap and lock-contention cases reproduced the gap.

Creation now acquires the existing project tree guard before making its
directory, then takes the existing protocol-local lock. Amendments use the
same lock ordering. Project existence is checked again inside the guard.
Request IDs, history hashes, revision limits and on-disk formats are unchanged.

Validation: all 48 focused protocol lifecycle, API and domain tests passed in
8.39 seconds. Coverage includes both deletion orders, pauses during revision
construction and file commits, lock contention, idempotent retries, concurrent
amendments, cross-process locking, atomic write failure, corrupted histories,
revision/count limits and bound exports. Strict Pyright passed for the changed
application module. All projects were temporary offline fixtures.
