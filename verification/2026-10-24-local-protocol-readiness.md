# Recognize local model protocols during inference preflight

All local inference preflight used a llama.cpp-specific /health check. Ollama and
OpenAI-compatible servers without that route could be shown as listening in
Settings while runs and photo features rejected them as not running. Appending
/health to the whole URL also put it inside a deployment query when one existed.

The check now constructs URLs from parsed path/query components. It first uses
health; only a missing/unsupported route permits fallback to the configured
OpenAI-style models list and the Ollama tags list. A fallback HTTP 200 must contain
the expected JSON list; arbitrary HTML and wrong JSON shapes do not suffice.
Authentication-required endpoints count as reachable and leave credential
validation to the inference request. A health/loading failure such as 503, a
server error, rate limit, timeout or connection failure still stops preflight.
Managed-server startup guards and adoption checks remain separate.

Thirty-six offline cases cover IPv4, localhost, IPv6, trailing slashes, deployment
paths/queries/fragments, health/models/tags/authenticated protocols, loading and
connection failures, malformed listing responses, and named Ollama/custom model
resolution. Before: 22 failures and 14 controls passed. After: 166 focused
protocol, endpoint isolation, assistive readiness and vision-entry checks passed
in 3.15 seconds. Two additional real loopback HTTP-server tests passed through
named model resolution with only a models/tags endpoint and no health route.

Strict Pyright reported zero errors and `git diff --check` passed. No model
weights, live inference or paid provider calls were used; loopback servers served
only deterministic fixture responses. This validates reachability and protocol
handling, not model loading or inference accuracy on a real installation.
