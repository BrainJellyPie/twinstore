# Check readiness at the selected local-model address

Assistive fallback and model pickers used the built-in local manager's state even
after the llama.cpp provider address was changed to another server. A ready
built-in server made an unreachable replacement appear usable; a starting or
failed built-in server hid an independently working replacement.

Apply the manager's lifecycle state only to its own endpoint, recognizing the
loopback aliases and a trailing slash. Probe a different configured address
regardless of that lifecycle state. Different ports, hosts, schemes, paths and
queries do not inherit readiness. Invalid saved URLs are unavailable instead of
breaking model selection. A known managed server still avoids an extra probe,
and its ongoing startup is not treated as ready.

The regression matrix exercises actual assistive selection and model listing
across seven manager states, three independent endpoints and both health outcomes.
Same-endpoint controls cover IPv4, localhost and IPv6 loopback aliases. Thirty
checks failed before the fix; 27 controls passed. The existing fallback fake now
includes the endpoint that a real ready manager reports.

After: 118 focused endpoint, provider readiness, rejected-key fallback and API
responsiveness checks passed in 3.50 seconds. Two additional malformed-address
controls passed with the new endpoint suite (59 checks). Strict Pyright reported
zero errors in the changed module; `git diff --check` passed. Health responses
were mocked; no model downloads or live inference were used.
