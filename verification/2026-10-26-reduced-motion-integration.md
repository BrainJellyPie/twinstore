# Integrate reduced-motion and scroll-focus fixes

Merged `claude/online-shopping-features-ji7y0f` through
`b1f560d39af0641209a83d2d94be4de25b9fda94` onto main `108a1bb8`.
The four incoming commits add scroll padding around sticky/floating report
controls and store-panel tabs, let the template gallery's create bar fit
narrow screens, remove nested main landmarks from online/marketing pages
and respect the system's reduced-motion preference for scripted scrolling.

The shared scroll helper is consulted when the action occurs, so it reads
the current preference. Existing focus transfers are retained. Static
review found no remaining literal `behavior: "smooth"`, `scroll-smooth`
class or CSS `scroll-behavior` declaration under `frontend/src` that would
override these calls. This is not a claim that every animation in the
application has been audited.

The only merge conflict was Unreleased changelog text; both sides were
retained. Released changelog sections remain byte-identical. Previously
published additional-discount, number-input synchronization and coupon-price
changes remain intact; no backend file changes in this merge.

Verification passes 43 frontend tests across seven files in 12.22 seconds:
motion preference, report section focus, online page identity/navigation,
online analyst, dashboard localization, layout deletion and the home route.
TypeScript passes. Lint of all 11 changed TypeScript files has zero errors
and the two existing route-export Fast Refresh warnings. Production build
passes in 20.90 seconds with the existing Babel/chunk-size notices.

These checks use jsdom, static review and compilation. Physical phone
layouts, sticky-element occlusion and browser scrolling were not measured
in a real-browser matrix. Backend verification remains the unchanged
parent's 1,293 focused checks, strict Pyright/boot and four actual CPU VLM
cases. The v0.8.2 release assets are unchanged.

Logs: `/workspace/scratch/reduced-motion-integration-{tests,tsc,eslint,build}.log`.
