# Include product landings in per-product reports

Search/social arrivals recorded the initial product in the session's viewed list
and funnel, but product reports counted only open-product clicks. A landing-only
visit could therefore have no product row, while later browsing undercounted one
view. Aggregate the recorded view list instead of deriving it from click actions.
Click-action counts and add/purchase metrics retain their existing meanings.

Seven tests cover direct/search/social arrivals, immediate exits, opening another
product and repeated recorded exposures. Before repair: five failed, two passed
in 0.68 seconds. After repair: 78 focused arrival, session, advertising and API
tests passed in 23.58 seconds. Full-source Pyright reported zero errors and warnings;
backend boot passed. No frontend runtime or previously stored reports changed.
