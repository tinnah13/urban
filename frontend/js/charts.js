const BASE_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { y: { beginAtZero: true, grid: { color: "#e2e8f0" } },
            x: { grid: { display: false } } },
};

const PALETTE = ["#0ea5e9", "#f97316", "#22c55e", "#ef4444",
                 "#a855f7", "#eab308", "#14b8a6", "#ec4899"];

function renderLine(id, labels, data, label = "Value", color = "#0ea5e9") {
  const ctx = document.getElementById(id).getContext("2d");
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label, data, borderColor: color,
        backgroundColor: color + "33", fill: true,
        tension: 0.35, pointRadius: 3,
      }],
    },
    options: BASE_OPTS,
  });
}

function renderBar(id, labels, data, color = "#0ea5e9") {
  const ctx = document.getElementById(id).getContext("2d");
  return new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ data, backgroundColor: color, borderRadius: 6 }],
    },
    options: BASE_OPTS,
  });
}

function renderDoughnut(id, labels, data) {
  const ctx = document.getElementById(id).getContext("2d");
  return new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data, backgroundColor: PALETTE, borderWidth: 2,
                   borderColor: "#fff" }],
    },
    options: { responsive: true, maintainAspectRatio: false,
               plugins: { legend: { position: "bottom" } } },
  });
}