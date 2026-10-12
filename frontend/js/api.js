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

// Fetch wrapper for /api/* endpoints
const API_BASE = "/api"

const api = {
    get: async function (path) {
        const res = await fetch(API_BASE + path)
        if (!res.ok) {
            throw new Error("API" + path + "returned" + res.status);
        }
        return res.json();
    },
};