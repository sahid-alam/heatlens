// HeatLens map: one choropleth of BBMP wards, recoloured per layer.

const LAYERS = {
  risk_score:   { label: "Heat risk",           unit: "score 0–1", digits: 2, colors: ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"] },
  lst_c:        { label: "Surface temperature", unit: "°C",        digits: 1, colors: ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"] },
  ndvi:         { label: "Green cover (NDVI)",  unit: "index",     digits: 2, colors: ["#edf8e9", "#bae4b3", "#74c476", "#31a354", "#006d2c"] },
  pop_density:  { label: "Population density",  unit: "people/km²", digits: 0, colors: ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"] },
  housing_vuln: { label: "Housing vulnerability", unit: "score 0–1", digits: 2, colors: ["#feedde", "#fdbe85", "#fd8d3c", "#e6550d", "#a63603"] },
};
const NO_DATA = "#d0d7de";

// Heat risk can be combined two ways; build_index.py writes both columns.
let combine = "multiply";
const field = (key) => (key === "risk_score" && combine === "add" ? "risk_score_add" : key);

const map = L.map("map").setView([12.97, 77.59], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

let wardsLayer, current, breaks = {};

// 5 quantile classes: each colour covers about the same number of wards.
function quantileBreaks(values) {
  const v = values.filter((x) => x != null).sort((a, b) => a - b);
  if (!v.length) return null;
  return [0.2, 0.4, 0.6, 0.8].map((q) => v[Math.floor(q * (v.length - 1))]);
}

function colorFor(key, value) {
  const b = breaks[field(key)];
  if (value == null || !b) return NO_DATA;
  const i = b.findIndex((x) => value <= x);
  return LAYERS[key].colors[i === -1 ? 4 : i];
}

const fmt = (key, v) => (v == null ? "no data" : Number(v).toLocaleString("en-IN", {
  maximumFractionDigits: LAYERS[key]?.digits ?? 2, minimumFractionDigits: LAYERS[key]?.digits ?? 0,
}));

function restyle() {
  wardsLayer.setStyle((f) => ({
    fillColor: colorFor(current, f.properties[field(current)]),
    fillOpacity: 0.75, color: "#fff", weight: 1,
  }));
  switcher.combineRow.hidden = current !== "risk_score";
  legend.update();
}

// Layer switch (top right). Layers with no data yet are shown but disabled.
const switcher = L.control({ position: "topright" });
switcher.onAdd = () => {
  const div = L.DomUtil.create("div", "panel layers");
  div.innerHTML = "<h2>Show</h2>" + Object.entries(LAYERS).map(([key, l]) => {
    const off = !breaks[key];
    return `<label class="${off ? "off" : ""}" title="${off ? "Not computed yet" : ""}">
      <input type="radio" name="layer" value="${key}" ${off ? "disabled" : ""} ${key === current ? "checked" : ""}>
      ${l.label}</label>`;
  }).join("");

  // Multiply / Add switch, only shown while the heat risk layer is on.
  switcher.combineRow = L.DomUtil.create("fieldset", "combine", div);
  switcher.combineRow.innerHTML = `<legend>Combine ingredients</legend>
    <label title="A ward must be bad on heat, people and fragility to rank high">
      <input type="radio" name="combine" value="multiply" checked> Multiply</label>
    <label title="One very bad ingredient can push a ward up on its own">
      <input type="radio" name="combine" value="add"> Add</label>`;

  div.addEventListener("change", (e) => {
    if (e.target.name === "combine") combine = e.target.value;
    else current = e.target.value;
    restyle();
  });
  L.DomEvent.disableClickPropagation(div);
  return div;
};

// Legend (bottom right): the class ranges for the current layer.
const legend = L.control({ position: "bottomright" });
legend.onAdd = () => (legend.div = L.DomUtil.create("div", "panel legend"));
legend.update = () => {
  const l = LAYERS[current], b = breaks[field(current)];
  const edges = [null, ...b, null];
  const how = current === "risk_score" ? `, ${combine}` : "";
  legend.div.innerHTML = `<h2>${l.label} <small>(${l.unit}${how})</small></h2>` + l.colors.map((c, i) => {
    const lo = edges[i], hi = edges[i + 1];
    const text = lo == null ? `≤ ${fmt(current, hi)}` : hi == null ? `> ${fmt(current, lo)}` : `${fmt(current, lo)} – ${fmt(current, hi)}`;
    return `<div class="row"><i style="background:${c}"></i>${text}</div>`;
  }).join("") + `<div class="row"><i style="background:${NO_DATA}"></i>no data</div>`;
};

// One decimal with a sign; values that round to zero show as "0.0", never "-0.0".
const signed = (v) => {
  const r = Math.round(v * 10) / 10;
  return r === 0 ? "0.0" : `${r > 0 ? "+" : ""}${r.toFixed(1)}`;
};

async function showWard(e, feature) {
  const w = await fetch(`/api/wards/${feature.properties.ward_id}`).then((r) => r.json());
  const rows = [
    ["Surface temp", w.lst_c == null ? "no data" : `${fmt("lst_c", w.lst_c)} °C`],
    ["Risk rank", (combine === "add" ? w.risk_rank_add : w.risk_rank) == null
      ? "no data" : `${combine === "add" ? w.risk_rank_add : w.risk_rank} of 198 (${combine})`],
    ["Green cover", fmt("ndvi", w.ndvi)],
    ["Population", fmt("pop_density", w.population)],
    ["Density", `${fmt("pop_density", w.pop_density)} /km²`],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  const drivers = w.drivers.length
    ? `<ol class="drivers">${w.drivers.slice(0, 3).map((d) =>
        `<li>${d.label}: ${signed(d.effect_c)} °C</li>`).join("")}</ol>`
    : `<p class="muted">Heat drivers appear once the model has run.</p>`;
  L.popup({ maxWidth: 260 })
    .setLatLng(e.latlng)
    .setContent(`<div class="popup"><h3>${w.ward_name} <small>(ward ${w.ward_id})</small></h3><dl>${rows}</dl>${drivers}</div>`)
    .openOn(map);
}

fetch("/api/wards").then((r) => r.json()).then((geojson) => {
  for (const key of [...Object.keys(LAYERS), "risk_score_add"]) {
    breaks[key] = quantileBreaks(geojson.features.map((f) => f.properties[key]));
  }
  current = Object.keys(LAYERS).find((k) => breaks[k]);

  wardsLayer = L.geoJSON(geojson, {
    onEachFeature: (f, layer) => {
      layer.bindTooltip(f.properties.ward_name, { sticky: true });
      layer.on({
        mouseover: () => layer.setStyle({ weight: 3, color: "#1f2328" }),
        mouseout: () => layer.setStyle({ weight: 1, color: "#fff" }),
        click: (e) => showWard(e, f),
      });
    },
  }).addTo(map);
  map.fitBounds(wardsLayer.getBounds());

  switcher.addTo(map);
  legend.addTo(map);
  restyle();
});
