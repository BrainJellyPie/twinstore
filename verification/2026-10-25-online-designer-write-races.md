# Online designer writes — 2026-10-25

Saving, copying a variant, or making a version without ads left other edit and
delete controls active. Slow requests could overlap a deletion, and edits made
while a save/refetch was pending could disappear when the refreshed timestamp
remounted the form. Four focused regressions failed before the fix in 3.04s:
three sent a real mocked delete request during another write, and the fourth
found the form editable before its saved snapshot arrived.

The complete editor is now disabled during writes. Refresh promises keep the
save pending until the new snapshot arrives. Exact query invalidation avoids
refetching the same detail twice through the list's query prefix. Failed writes
unlock the original draft, including unfinished monetary edits, for retry.

Verification: 45 frontend cases passed in 7.23s across SiteDesigner,
OnlinePageIdentity, and RunLauncherExperiments. New cases cover the three write
paths, the save/refetch interval, failure and retry, and saving/copying during a
pending deletion. TypeScript and changed-file ESLint passed. Production build
passed in 18.41s with existing chunk-size and plugin-timing warnings. Backend
code was unchanged; no backend checks or live model calls were needed.
