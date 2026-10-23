# Model responses preserve one complete shopping visit

The impulse stage is asked to return shopping stops, but its response schema can
also represent payment, entry, exit and movement actions. These were merged into
the visit unchanged. A scripted extra payment produced two checkout events for
one shopper; that shopper then abandoned the second checkout because the first
one still occupied the till. Extra exits could end the visit before its purchases.

Conflicting navigation caused a second problem: BUY/PAY actions marked as area
movement or leaving could skip their destination, disappear during merging or
end a visit. Missing exits, or EXIT with ordinary path/area navigation, left the
recorded visit ending at payment's start instead of after checkout and departure.

The engine now normalizes intent purchases/payment to point routes and explicit
exits to leaving before calculating exposure. Impulse responses contribute only
browsing and purchase stops with point routes; an omitted action retains its
existing implicit-browse meaning. Unexpected impulse actions stay in the trace
and are logged as excluded. A missing terminal exit is added after surviving
shopping and payment actions.

Focused verification, all with scripted model responses:

- Initial boundary matrix: **22 failed, 2 passed**, 0.39 seconds, before repair.
- Additional incomplete-exit matrix: **6 failed**, 0.66 seconds, before exit repair.
- Final model, budget, selected-offer, checkout and routing checks:
  **249 passed**, 1.03 seconds, including 30 new cases. Both route orderings cover
  unwanted stage-3 action kinds, conflicting BUY/PAY navigation, actual shelf/till
  positions, a single checkout without self-abandonment, retained implicit
  browsing, and completed exits whose visit duration includes payment.
- Changed engine module strict type check: **zero errors/warnings**.

No model requests or real data were used. Frontend source is unchanged; the full
release suite was not repeated for this engine-only follow-up.
