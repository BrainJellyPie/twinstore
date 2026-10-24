# Preserve independently configured local vision servers

Simulation readiness and automatic vision-model selection still treated
loopback hosts on one port as the managed endpoint. The startup guard also
ignored the API path, while vision selection ignored the deployment query. An
independently responding server could therefore be blocked by the built-in
server's download or replaced by a cloud model because a key was configured.

Match the concrete API endpoint when applying managed lifecycle or routing
policy: scheme, host, port, path (ignoring a trailing slash), query and userinfo.
Readiness probes still test independent loopback endpoints. The known managed
endpoint retains its startup guard and the existing optional cloud fallback;
an explicitly requested model remains authoritative.

Thirty independent-endpoint cases cross six manager states with different
localhost/IPv6 hosts, paths, queries and ports. They assert that the configured
server is health-checked and neither vision selector changes its model. Two
managed-endpoint controls preserve startup blocking and fallback. Before:
21 failures and 11 passing controls. Existing managed-address tests now identify
the manager's actual endpoint instead of assuming loopback aliases are identical.

After: 189 focused vision routing, readiness, assistive scope, key fallback and
provider API responsiveness checks passed. Strict Pyright reported zero errors
in the changed module; `git diff --check` passed. All health responses and keys
were offline fixtures; no provider inference or downloads were used.
