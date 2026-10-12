// Dashboard controller

let chartHourly, chartBorough, chartZones, chartAirport;

// ---------- KPIs ----------
async function loadSummary() {
  const s = await api.get("/summary");
  const items = [
    ["Total Trips",   Number(s.total_trips).toLocaleString()],
    ["Avg Distance",  s.avg_distance + " mi"],
    ["Avg Duration",  s.avg_duration + " min"],
    ["Avg Fare",      "$" + s.avg_fare],
    ["Avg Speed",     s.avg_speed + " mph"],
    ["Avg Tip",       s.avg_tip_pct + "%"],
    ["Total Revenue", "$" + Number(s.total_revenue).toLocaleString()],
  ];
  document.getElementById("kpis").innerHTML = items.map(
    ([label, value]) =>
      `<div class="kpi"><div class="v">${value}</div>
       <div class="l">${label}</div></div>`
  ).join("");
}

// ---------- Charts ----------
async function loadCharts() {
  const hourly = await api.get("/hourly");
  if (chartHourly) chartHourly.destroy();
  chartHourly = renderLine(
    "c-hourly",
    hourly.map(h => h.hour + ":00"),
    hourly.map(h => h.trips)
  );

  const boro = await api.get("/boroughs");
  if (chartBorough) chartBorough.destroy();
  chartBorough = renderBar(
    "c-borough",
    boro.map(b => b.borough),
    boro.map(b => b.trips),
    "#f97316"
  );

  const zones = await api.get("/top-zones?k=10");
  if (chartZones) chartZones.destroy();
  chartZones = renderBar(
    "c-zones",
    zones.map(z => z.zone),
    zones.map(z => z.trips),
    "#22c55e"
  );

  const insights = await api.get("/insights");
  if (chartAirport) chartAirport.destroy();
  chartAirport = renderDoughnut(
    "c-airport",
    insights.airport.map(a => a.is_airport_trip ? "Airport" : "Non-airport"),
    insights.airport.map(a => a.avg_fare)
  );
}

// ---------- Insights ----------
async function loadInsights() {
  const i = await api.get("/insights");
  const peak = i.peak_hour || {};
  const ap = i.airport.find(a => a.is_airport_trip) || {};
  const non = i.airport.find(a => a.is_airport_trip === 0) || {};
  const cb = i.cross_borough.find(c => c.is_cross_borough) || {};
  const intra = i.cross_borough.find(c => c.is_cross_borough === 0) || {};

  document.getElementById("insights").innerHTML = `
    <div class="insight">
      <b>Peak demand:</b> The busiest hour is <b>${peak.hour}:00</b> with
      <b>${Number(peak.c).toLocaleString()}</b> trips. Fleet managers should
      plan driver shifts accordingly.
    </div>
    <div class="insight">
      <b>Airport premium:</b> Airport trips average
      <b>$${ap.avg_fare}</b> vs <b>$${non.avg_fare}</b> for non-airport trips
      — a ${(ap.avg_fare / non.avg_fare).toFixed(1)}× multiplier.
    </div>
    <div class="insight">
      <b>Cross-borough tipping:</b> Riders crossing borough lines tip
      <b>${cb.avg_tip}%</b> on average vs <b>${intra.avg_tip}%</b> for
      intra-borough trips — an economic signal for driver incentives.
    </div>
  `;
}

// ---------- Filters ----------
async function loadFilters() {
  const f = await api.get("/filters");
  const bSel = document.getElementById("f-borough");
  f.boroughs.forEach(b => bSel.add(new Option(b, b)));
  const pSel = document.getElementById("f-payment");
  f.payments.forEach(p =>
    pSel.add(new Option(p.payment_description, p.payment_type_id))
  );
}

// ---------- Trips table ----------
async function loadTrips() {
  const params = new URLSearchParams({ limit: 100 });
  const b  = document.getElementById("f-borough").value;
  const p  = document.getElementById("f-payment").value;
  const mn = document.getElementById("f-min").value;
  const mx = document.getElementById("f-max").value;
  const ap = document.getElementById("f-airport").value;
  if (b)  params.set("borough", b);
  if (p)  params.set("payment", p);
  if (mn) params.set("min_fare", mn);
  if (mx) params.set("max_fare", mx);
  if (ap) params.set("airport", ap);

  const rows = await api.get("/trips?" + params.toString());
  document.querySelector("#trips-table tbody").innerHTML = rows.map(r => `
    <tr>
      <td>${new Date(r.pickup_time).toLocaleString()}</td>
      <td>${r.pickup_zone}</td>
      <td>${r.pickup_borough}</td>
      <td>${(+r.trip_distance).toFixed(2)} mi</td>
      <td>${(+r.trip_duration_minutes).toFixed(1)} min</td>
      <td>$${(+r.total_amount).toFixed(2)}</td>
      <td>${(+r.tip_percentage).toFixed(1)}%</td>
      <td>${(+r.speed_mph).toFixed(1)} mph</td>
    </tr>
  `).join("");
}

// ---------- Init ----------
document.getElementById("apply").addEventListener("click", loadTrips);

(async function init() {
  try {
    await loadFilters();
    await loadSummary();
    await loadCharts();
    await loadInsights();
    await loadTrips();
    console.log("Dashboard loaded");
  } catch (err) {
    console.error("Init error:", err);
    alert("Failed to load dashboard: " + err.message);
  }
})();