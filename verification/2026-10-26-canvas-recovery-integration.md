# Keep WebGL recovery events attached to their active canvas

Integrate `fed7e532` and `eed8ef5a`: shopper-search Enter/ArrowDown navigation
and a localized recovery notice for the 3D store after WebGL context loss.

The initial recovery implementation registered anonymous listeners in
`onCreated` and never removed them. The installed React Three Fiber renderer
calls `forceContextLoss` while disposing an unmounted canvas after 500 ms.
After restart, the old canvas could therefore display the loss overlay again
or stop a newly started Photo session. Its restoration event could also clear
a loss message belonging to the replacement canvas.

The component now owns the canvas element in state and attaches/removes its
listeners in an effect. Restart clears the old canvas before replacing it;
leaving the screen removes the listeners as well. The new canvas still stops
Photo mode on loss and clears its notice on restoration.

The new DOM-event regressions initially had two failures and one pass: a late
old-canvas loss redisplayed the overlay, and loss after unmount stopped a new
Photo session. All **13 tests across four related files** now pass in 4.83 s,
including active restoration, replacement/unmount isolation, Strict Mode,
shopper navigation, layout currency and photo-scene checks. These tests use
a minimal Canvas stand-in and real DOM events; they do not emulate a GPU or
claim a physical driver reset was tested. The disposal timing was checked in
the installed renderer source.

ESLint on all five changed TypeScript files reported zero errors/warnings;
TypeScript checking and the production build passed (20.16 s, existing
chunk/plugin warnings). Diff checking passed. Backend code is unchanged from
verified main `d3bf577e`; no backend suite was repeated for this UI change.
Changelog conflicts were reconciled under Unreleased. All released content
from v0.8.2 onward remains unchanged.
