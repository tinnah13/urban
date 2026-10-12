// ========================================================================
// Urban Mobility Explorer
// ========================================================================
// Responsibilities:
//    1. Fetch Kpis, hourly, borough, top-zone and insights data on load.
//    2. Wire the filter bar (borough, payment, fare range, airport toggle).
//    3. Render four chart.js canvases.
//    4. Populated the "sample trips" table with the filtered subset.
//
// Design decision: all data is fetched client-side via /api/* so the
// dasboard can be served from any stastic host without a build step.
// ========================================================================