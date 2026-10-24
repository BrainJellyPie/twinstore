# Personal purchase evidence in shopper interviews

Post-trip answers and follow-up suggestions used `purpose or intent` for the
shopper's reason for visiting. Generated shoppers normally have both: the
broad purpose label hid the individual purchase intent. Preferred categories
were also absent. These omissions could leave the request and cached answer
unchanged when relevant personal evidence changed.

The scripted HTTP baseline reproduced twelve failures, with four passing
controls where an empty purpose already allowed intent through, in 2.50 seconds.
It covered both answer and follow-up paths, JSON and JSON-schema response modes,
and shoppers with or without a purpose label. The client and disk cache are real;
the transport returns scripted responses without model inference or paid calls.

The trip summary now includes distinct intent alongside an existing purpose
and includes nonempty preferred categories. An intent already used as the visit
reason is not repeated. The 32 new cases also cover clearing either field and
verify cache reuse for unchanged evidence, fresh requests after edits, original
conversation and purchase facts, and removal of out-of-trip citation numbers.
Together with the affected interview API, empty-answer, suggestion-race and
study-identity checks, all 68 tests passed in 20.81 seconds.
Strict backend type checking passed with zero errors; `git diff --check` is clean.
