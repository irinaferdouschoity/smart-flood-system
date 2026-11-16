
"use strict";

const $ = (id) => document.getElementById(id);

let map = null;
let rainChart = null;
let tempChart = null;
let humChart = null;

// ---------- API helper ----------

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.headers || {}),
            ...(options.body ? { "Content-Type": "application/json" } : {})
        }
    });

    const text = await response.text();
    let data;

    try {
        data = text ? JSON.parse(text) : null;
    } catch {
        throw new Error(`Invalid server response (${response.status}).`);
    }

    if (!response.ok) {
        throw new Error(
            data?.detail || `Request failed: ${response.status}`
        );
    }

    return data;
}

function status(message) {
    const element = $("status");

    if (element) {
        element.textContent = message;
        if (element.dataset) {
            element.dataset.state = String(message).startsWith("Error") ? "error" : "";
        }
    }
}

function showError(message) {
    console.error(message);
    status(`Error: ${message}`);
}

function numeric(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const result = Number(value);
    return Number.isFinite(result) ? result : null;
}

function displayNumber(value, suffix = "") {
    const result = numeric(value);
    return result === null ? "--" : `${result.toFixed(2)}${suffix}`;
}

// ---------- Base map: OpenStreetMap, with a second provider and a visible warning if both fail ----------

const TILE_SOURCES = [
    {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        options: { maxZoom: 19, attribution: "© OpenStreetMap contributors" }
    },
    {
        url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        options: { subdomains: "abcd", maxZoom: 19, attribution: "© OpenStreetMap contributors © CARTO" }
    }
];

function showMapWarning() {
    const box = $("map-warning");

    if (!box) return;

    box.hidden = false;
    box.textContent =
        "The map pictures could not be loaded. Check your internet connection or firewall " +
        "(the map needs tile.openstreetmap.org). The location markers still work.";
}

function addBaseMap(index = 0) {
    const source = TILE_SOURCES[index];
    const layer = L.tileLayer(source.url, source.options).addTo(map);

    if (!layer || typeof layer.on !== "function") return;

    let loaded = 0;
    let failed = 0;
    let handled = false;

    layer.on("tileload", () => { loaded += 1; });

    layer.on("tileerror", () => {
        failed += 1;

        if (loaded === 0 && failed >= 4 && !handled) {
            handled = true;
            map.removeLayer(layer);

            if (index + 1 < TILE_SOURCES.length) {
                addBaseMap(index + 1);
            } else {
                showMapWarning();
            }
        }
    });
}

// ---------- Look: place heading and the risk gauge ----------

function showPlace() {
    const select = $("locations");
    const place = $("place");
    const option = select?.options?.[select.selectedIndex];

    if (!place) return;

    if (option?.dataset?.name) {
        place.textContent = `${option.dataset.name}, ${option.dataset.division} Division`;
    } else {
        place.textContent = option ? option.textContent : "Choose a location";
    }
}

// 0 = no reading, 1 = low ... 4 = very high
function riskLevelOf(text) {
    const value = String(text || "").trim().toUpperCase();

    if (!value || value === "--") return 0;
    if (/VERY|SEVERE|EXTREME|CRITICAL/.test(value)) return 4;
    if (/HIGH/.test(value)) return 3;
    if (/MODERATE|MEDIUM/.test(value)) return 2;
    if (/LOW|NONE|MINIMAL/.test(value)) return 1;

    return 0;
}

function applyRiskVisual() {
    const level = riskLevelOf($("risk")?.textContent);
    const reading = $("reading");
    const gauge = $("gauge");

    if (reading?.dataset) reading.dataset.level = String(level);
    if (gauge?.style?.setProperty) gauge.style.setProperty("--level", String(level));
}

function watchRisk() {
    const element = $("risk");

    if (!element || typeof MutationObserver === "undefined") return;

    new MutationObserver(applyRiskVisual).observe(
        element,
        { childList: true, characterData: true, subtree: true }
    );

    applyRiskVisual();
}

function selectedCityId() {
    return Number($("locations")?.value || 0) || 0;
}

// A database city in Bangladesh (e.g. Dhaka) is also one of the 64 districts: use the district model for it.
function bangladeshCityDistrictId() {
    const select = $("locations");
    const option = select?.options?.[select.selectedIndex];

    if (!option || option.dataset?.country !== "Bangladesh") return 0;

    const id = Number(select.value) || 0;
    return BD_IDS.has(id) ? id : 0;
}

// Bangladesh districts use option values like "bd:105".
function selectedDistrictId() {
    const value = $("locations")?.value || "";
    return value.startsWith("bd:") ? Number(value.slice(3)) : 0;
}

// ---------- Graphs ----------

// Chart colours come from the page's CSS variables so light and dark mode both work.
function cssVar(name, fallback) {
    try {
        const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return value || fallback;
    } catch (error) {
        return fallback;
    }
}

const CHART_STYLE = {
    rain: { type: "bar", variable: "--teal", fallback: "#0e7c86" },
    temp: { type: "line", variable: "--amber", fallback: "#d98a1f" },
    humidity: { type: "line", variable: "--slate", fallback: "#5b7c99" }
};

function drawChart(previous, canvasId, labels, values, title) {
    const canvas = $(canvasId);

    if (!canvas || typeof Chart === "undefined") {
        throw new Error(
            `Chart.js or canvas "${canvasId}" is unavailable.`
        );
    }

    if (previous) previous.destroy();

    const style = CHART_STYLE[canvasId] || CHART_STYLE.temp;
    const color = cssVar(style.variable, style.fallback);
    const grid = cssVar("--rule-soft", "#e0e8e4");
    const muted = cssVar("--muted", "#5a707b");
    const isBar = style.type === "bar";

    return new Chart(canvas, {
        type: style.type,
        data: {
            labels: labels,
            datasets: [{
                label: title,
                data: values,
                borderColor: color,
                backgroundColor: color,
                borderWidth: isBar ? 0 : 2,
                borderRadius: isBar ? 2 : 0,
                maxBarThickness: 12,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.25,
                spanGaps: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 1.7,
            interaction: {
                intersect: false,
                mode: "index"
            },
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: muted, maxTicksLimit: 6, maxRotation: 0, autoSkip: true }
                },
                y: {
                    beginAtZero: isBar,
                    grid: { color: grid },
                    ticks: { color: muted, maxTicksLimit: 5 }
                }
            }
        }
    });
}

// ---------- Weather ----------

async function weather(id) {
    const records = await api(`/weather/${id}?limit=90`);

    if (!Array.isArray(records)) {
        throw new Error("Weather data is not in the expected format.");
    }

    // The API returns the observations oldest to newest.
    renderWeather(records);
}

// ---------- Flood history ----------

async function history(id) {
    renderHistory(await api(`/flood-history/${id}`));
}

function renderHistory(records) {
    const container = $("history");

    if (!container) return;

    container.replaceChildren();

    if (!Array.isArray(records) || records.length === 0) {
        container.textContent = "No documented floods for this location.";
        container.classList.add("empty");
        return;
    }

    container.classList.remove("empty");

    const list = document.createElement("ul");
    list.className = "timeline";

    records.forEach(record => {
        const item = document.createElement("li");

        const when = document.createElement("time");
        when.textContent = String(record.event_date ?? "--");
        item.appendChild(when);

        const severity = document.createElement("span");
        severity.className = "conf";
        severity.textContent = String(record.severity ?? "");
        item.appendChild(severity);

        const text = document.createElement("p");
        text.textContent = String(record.description ?? record.details ?? "");
        item.appendChild(text);

        list.appendChild(item);
    });

    container.appendChild(list);
}

// ---------- Weather: charts, latest day, month average and the day-to-day table ----------

let lastWeather = null;

function toWeatherRows(records) {
    return records.map(row => ({
        date: String(row.observation_date ?? row.date ?? ""),
        rain: numeric(row.precipitation),
        temp: numeric(row.temperature_avg ?? row.temperature),
        hum: numeric(row.humidity_avg ?? row.humidity)
    }));
}

function average(values) {
    const valid = values.filter(value => value !== null);
    return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
}

function fixed(value, digits, suffix = "") {
    return value === null || value === undefined ? "--" : `${value.toFixed(digits)}${suffix}`;
}

function monthName(dateText) {
    const date = new Date(`${dateText}T00:00:00`);

    return Number.isNaN(date.getTime())
        ? dateText.slice(0, 7)
        : date.toLocaleString("en-US", { month: "long", year: "numeric" });
}

function setText(id, text) {
    const element = $(id);
    if (element) element.textContent = text;
}

function drawWeatherCharts(rows) {
    const labels = rows.map(row => row.date);

    rainChart = drawChart(rainChart, "rain", labels, rows.map(row => row.rain), "Rainfall (mm)");
    tempChart = drawChart(tempChart, "temp", labels, rows.map(row => row.temp), "Temperature (°C)");
    humChart = drawChart(humChart, "humidity", labels, rows.map(row => row.hum), "Humidity (%)");
}

function buildTable(container, headings, rows, firstRowClass) {
    const table = document.createElement("table");
    const head = document.createElement("tr");

    headings.forEach(text => {
        const cell = document.createElement("th");
        cell.textContent = text;
        head.appendChild(cell);
    });

    table.appendChild(head);

    rows.forEach((values, index) => {
        const row = document.createElement("tr");

        if (index === 0 && firstRowClass) row.className = firstRowClass;

        values.forEach(value => {
            const cell = document.createElement("td");
            cell.textContent = String(value);
            row.appendChild(cell);
        });

        table.appendChild(row);
    });

    container.appendChild(table);
}

function renderWeather(records) {
    const rows = toWeatherRows(records);

    lastWeather = rows;
    drawWeatherCharts(rows);
    renderWeatherNumbers(rows);
}

function renderWeatherNumbers(rows) {
    const withData = rows.filter(row => row.rain !== null || row.temp !== null || row.hum !== null);
    const latest = withData.length ? withData[withData.length - 1] : null;

    // the two rainfall cards at the top
    const last7 = withData.slice(-7).map(row => row.rain);

    setText("r24", latest ? fixed(latest.rain, 2, " mm") : "--");
    setText("r24Date", latest ? `(${latest.date})` : "");
    setText(
        "r7",
        last7.some(value => value !== null)
            ? `${last7.reduce((sum, value) => sum + (value ?? 0), 0).toFixed(2)} mm`
            : "--"
    );

    ["rain-note", "temp-note", "hum-note"].forEach(id => setText(id, ""));

    const summary = $("weather-summary");
    const daily = $("daily-table");

    if (!summary || !daily) return;

    summary.replaceChildren();
    daily.replaceChildren();

    if (!latest) {
        summary.textContent = "No weather data is stored for this location yet.";
        summary.classList.add("empty");
        return;
    }

    summary.classList.remove("empty");

    const month = latest.date.slice(0, 7);
    const monthRows = withData.filter(row => row.date.startsWith(month));
    const label = monthName(latest.date);

    const stats = key => {
        const values = monthRows.map(row => row[key]).filter(value => value !== null);

        return {
            n: values.length,
            avg: average(values),
            min: values.length ? Math.min(...values) : null,
            max: values.length ? Math.max(...values) : null,
            total: values.reduce((sum, value) => sum + value, 0)
        };
    };

    const rain = stats("rain");
    const temp = stats("temp");
    const hum = stats("hum");

    // a line of numbers under each chart title
    setText("rain-note", `Latest (${latest.date}): ${fixed(latest.rain, 1, " mm")}  |  ${label} average: ${fixed(rain.avg, 1, " mm per day")}`);
    setText("temp-note", `Latest (${latest.date}): ${fixed(latest.temp, 1, " °C")}  |  ${label} average: ${fixed(temp.avg, 1, " °C")}`);
    setText("hum-note", `Latest (${latest.date}): ${fixed(latest.hum, 0, " %")}  |  ${label} average: ${fixed(hum.avg, 0, " %")}`);

    buildTable(
        summary,
        ["Measure", `Latest day (${latest.date})`, `Average for ${label} (${monthRows.length} days so far)`, `${label}: total or range`],
        [
            ["Rainfall (mm per day)", fixed(latest.rain, 1), fixed(rain.avg, 1), rain.n ? `total ${rain.total.toFixed(1)} mm` : "--"],
            ["Temperature (°C)", fixed(latest.temp, 1), fixed(temp.avg, 1), temp.n ? `${temp.min.toFixed(1)} to ${temp.max.toFixed(1)}` : "--"],
            ["Humidity (%)", fixed(latest.hum, 0), fixed(hum.avg, 0), hum.n ? `${hum.min.toFixed(0)} to ${hum.max.toFixed(0)}` : "--"]
        ]
    );

    // the newest 30 days, newest first
    const list = withData.slice(-30).reverse().map(row => [
        row.date, fixed(row.rain, 1), fixed(row.temp, 1), fixed(row.hum, 0)
    ]);

    buildTable(daily, ["Date", "Rain (mm)", "Temperature (°C)", "Humidity (%)"], list, "latest");
}

// ---------- Historical rainfall indicator ----------

async function loadRainfallIndicator(id) {
    const result = await api(`/rainfall-indicator/${id}`);

    if ($("rainfallIndicator")) {
        $("rainfallIndicator").textContent =
            result.rainfall_indicator ?? "--";
    }

    if ($("rainfallDetails")) {
        const total = numeric(result.rainfall_3day_total);
        const threshold = numeric(result.threshold_95);

        $("rainfallDetails").textContent =
            `Rain in the 3 days to ${result.observation_date ?? "--"}: ${total === null ? "--" : total.toFixed(1)} mm ` +
            `(high-rainfall threshold ${threshold === null ? "--" : threshold.toFixed(0)} mm). ` +
            "A historical indicator, not a flood prediction.";
    }
}

// ---------- Selected city ----------

async function selected() {
    showPlace();

    const districtId = selectedDistrictId();

    if (districtId) {
        await districtSelected(districtId);
        return;
    }

    const id = selectedCityId();

    if (!id) {
        status("Please select a location.");
        return;
    }

    status("Loading city data...");

    const results = await Promise.allSettled([
        weather(id),
        history(id),
        loadRainfallIndicator(id)
    ]);

    const failures = results
        .filter(result => result.status === "rejected")
        .map(result => result.reason?.message || "Unknown error");

    if (failures.length) {
        showError(failures.join(" | "));
        return;
    }

    if ($("risk")) $("risk").textContent = "--";
    if ($("prob")) $("prob").textContent = "--";

    status("City data loaded.");
}

// ---------- Load cities and map ----------

async function load() {
    status("Loading locations...");

    const locations = await api("/locations");

    if (!Array.isArray(locations)) {
        throw new Error("The locations API did not return a list.");
    }

    const select = $("locations");

    if (!select) {
        throw new Error('Missing HTML element: id="locations".');
    }

    select.replaceChildren();

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select a location";
    select.appendChild(placeholder);

    locations.forEach(location => {
        const option = document.createElement("option");
        option.value = String(location.location_id);
        option.dataset.country = location.country;
        option.textContent =
            `${location.location_name}, ${location.country}`;
        select.appendChild(option);
    });

    if (map) {
        map.eachLayer(layer => {
            if (layer instanceof L.CircleMarker) {
                map.removeLayer(layer);
            }
        });

        locations.forEach(location => {
            const latitude = numeric(location.latitude);
            const longitude = numeric(location.longitude);

            if (latitude === null || longitude === null) return;

            L.circleMarker([latitude, longitude], { radius: 6 })
                .addTo(map)
                .bindPopup(
                    `${location.location_name}, ${location.country}`
                );
        });
    }

    await addDistrictOptions(select);
    loadAllDistricts();

    if (!locations.length) {
        status("No locations were returned by the API.");
        return;
    }

    select.value = String(locations[0].location_id);

    if (map) {
        const first = locations[0];
        const latitude = numeric(first.latitude);
        const longitude = numeric(first.longitude);

        if (latitude !== null && longitude !== null) {
            map.setView([latitude, longitude], 6);
        }
    }

    await selected();
}

// ---------- City-based Haor model prediction ----------

async function predict() {
    const districtId = selectedDistrictId() || bangladeshCityDistrictId();

    if (districtId) {
        await districtPredict(districtId);
        return;
    }

    const id = selectedCityId();

    if (!id) {
        status("Please select a location.");
        return;
    }

    const button = $("predict");
    if (button) button.disabled = true;

    status("Running experimental Haor model with latest city weather...");

    try {
        const result = await api(
            `/city-haor-predict?location_id=${encodeURIComponent(id)}`,
            { method: "POST" }
        );

        const probability = Number(result.flood_probability);

        if (!Number.isFinite(probability)) {
            throw new Error("The API returned an invalid probability.");
        }

        if ($("risk")) $("risk").textContent = result.risk_level ?? "--";

        if ($("prob")) {
            $("prob").textContent =
                `${(probability * 100).toFixed(1)}%`;
        }

        status(
            `Experimental estimate for ${result.city}, based on weather ` +
            `dated ${result.weather_observation_date}.`
        );

        const resultBox = $("haor-result");

        if (resultBox) {
            resultBox.replaceChildren();

            const details = [
                ["Experimental Haor model result", true],
                [`City: ${result.city}`, false],
                [`Latest weather date: ${result.weather_observation_date}`, false],
                [`Model output: ${(probability * 100).toFixed(1)}%`, false],
                [`Model category: ${result.risk_level}`, false],
                [`Warning: ${result.warning ?? "Research estimate only."}`, false],
                [
                    "Unavailable live satellite/terrain features: " +
                    (result.missing_live_features || []).join(", "),
                    false
                ]
            ];

            details.forEach(([text, isHeading]) => {
                const element = document.createElement(
                    isHeading ? "h3" : "p"
                );
                element.textContent = text;
                resultBox.appendChild(element);
            });
        }
    } catch (error) {
        showError(`Prediction failed: ${error.message}`);
    } finally {
        if (button) button.disabled = false;
    }
}

// ---------- Refresh NASA data ----------

async function update() {
    const button = $("refresh");
    if (button) button.disabled = true;

    try {
        const districtId = selectedDistrictId();

        if (districtId) {
            status("Downloading the newest NASA data for all 64 districts (about a minute)...");
            await api("/bd/refresh", { method: "POST" });
            await loadAllDistricts();
            await districtSelected(districtId);
            status("District data and predictions updated.");
            return;
        }

        status("Downloading NASA weather data (the first time can take a minute)...");

        const result = await api("/sync-nasa", {
            method: "POST"
        });

        const failures = Array.isArray(result.results)
            ? result.results.filter(item => item.status === "error")
            : [];

        await load();

        if (failures.length) {
            status(
                `Update finished with ${failures.length} location error(s).`
            );
        } else {
            status("NASA data update completed.");
        }
    } catch (error) {
        showError(`Update failed: ${error.message}`);
    } finally {
        if (button) button.disabled = false;
    }
}

// ---------- Manual 14-feature Haor research model ----------

async function predictHaor(event) {
    event.preventDefault();

    const form = $("haor-form");
    const resultBox = $("haor-result");

    if (!form) return;

    const fields = [
        "VV", "VH", "vv_vh_ratio", "rainfall",
        "soil_moisture", "temp", "wind", "slope",
        "twi", "rain_24h", "ndwi", "upstream_vv",
        "rain_96h", "temp_anomaly"
    ];

    const features = {};

    for (const name of fields) {
        const input = form.elements.namedItem(name);

        if (!input || input.value.trim() === "") {
            if (resultBox) {
                resultBox.textContent = `Please enter ${name}.`;
            }
            return;
        }

        const value = Number(input.value);

        if (!Number.isFinite(value)) {
            if (resultBox) {
                resultBox.textContent = `${name} must be numeric.`;
            }
            return;
        }

        features[name] = value;
    }

    const button = $("haor-submit");
    if (button) button.disabled = true;

    if (resultBox) resultBox.textContent = "Running research model...";

    try {
        const result = await api("/haor-predict", {
            method: "POST",
            body: JSON.stringify({ features })
        });

        if (resultBox) {
            resultBox.replaceChildren();

            const heading = document.createElement("h3");
            heading.textContent = "Haor research model result";

            const probability = document.createElement("p");
            probability.textContent =
                `Model output: ${
                    (Number(result.flood_probability) * 100).toFixed(1)
                }%`;

            const level = document.createElement("p");
            level.textContent = `Model category: ${result.risk_level}`;

            const warning = document.createElement("p");
            warning.textContent = result.warning ?? "Experimental result.";

            resultBox.append(heading, probability, level, warning);
        }
    } catch (error) {
        if (resultBox) {
            resultBox.textContent = `Prediction failed: ${error.message}`;
        }
        showError(`Haor prediction failed: ${error.message}`);
    } finally {
        if (button) button.disabled = false;
    }
}

// ---------- Bangladesh: all 64 districts ----------

const RISK_NAMES = {
    "LOW": "Low",
    "MODERATE": "Moderate",
    "HIGH": "High",
    "VERY HIGH": "Very high"
};

const RISK_COLORS = {
    "LOW": "#3f9b6b",
    "MODERATE": "#e3a72f",
    "HIGH": "#e36b2c",
    "VERY HIGH": "#b8282f"
};

let bdMarkers = {};
const BD_IDS = new Set();

async function addDistrictOptions(select) {
    let districts;

    try {
        districts = await api("/bd/districts");
    } catch (error) {
        return;   // the district module is optional
    }

    if (!Array.isArray(districts) || !districts.length) return;

    const group = document.createElement("optgroup");
    group.label = "Bangladesh districts (64)";

    districts
        .slice()
        .sort((a, b) => a.district.localeCompare(b.district))
        .forEach(item => {
            const option = document.createElement("option");
            option.value = `bd:${item.location_id}`;
            option.dataset.name = item.district;
            option.dataset.division = item.division;
            option.textContent = `${item.district} (${item.division})`;
            group.appendChild(option);
        });

    districts.forEach(item => BD_IDS.add(Number(item.location_id)));
    select.appendChild(group);

    bdMarkers = {};

    if (map) {
        districts.forEach(item => {
            bdMarkers[item.location_id] = L.circleMarker(
                [item.latitude, item.longitude],
                { radius: 5, color: "#555", weight: 1, fillColor: "#999", fillOpacity: 0.6 }
            )
                .addTo(map)
                .bindPopup(`${item.district}, ${item.division} Division`);
        });
    }
}

function openDistrict(locationId) {
    const select = $("locations");
    if (!select) return;

    select.value = `bd:${locationId}`;
    selected().catch(error => showError(error.message));
}

async function loadAllDistricts() {
    const box = $("bd-all");
    if (!box) return;

    try {
        const payload = await api("/bd/predictions");
        const rows = payload.districts || [];
        const maxProbability = Math.max(0.0001, ...rows.map(item => Number(item.probability) || 0));

        box.replaceChildren();
        box.classList.remove("empty");

        const info = document.createElement("p");
        info.textContent =
            `Conditions as of ${payload.meta.as_of}: chance of a flood within ` +
            `${payload.meta.horizon_days} days. Click a row to open the district.`;
        info.style.margin = "0 0 12px";
        box.appendChild(info);

        const wrap = document.createElement("div");
        wrap.className = "tablewrap";

        const table = document.createElement("table");
        const head = document.createElement("tr");

        ["#", "District", "Division", "Risk", "Chance of flood", "Rain, 3 days"].forEach(text => {
            const cell = document.createElement("th");
            cell.textContent = text;
            head.appendChild(cell);
        });

        table.appendChild(head);

        rows.forEach(item => {
            const color = RISK_COLORS[item.risk_level] || "#999";
            const probability = Number(item.probability) || 0;
            const row = document.createElement("tr");

            row.className = "clickable";
            row.style.cursor = "pointer";
            row.addEventListener("click", () => openDistrict(item.location_id));

            const cells = [];

            [item.rank, item.district, item.division].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = String(value);
                cells.push(cell);
            });

            const risk = document.createElement("td");
            const dot = document.createElement("span");
            dot.className = "dot";
            dot.style.setProperty("--c", color);
            risk.appendChild(dot);
            risk.appendChild(document.createTextNode(RISK_NAMES[item.risk_level] || item.risk_level));
            cells.push(risk);

            const chance = document.createElement("td");
            const meter = document.createElement("span");
            const fill = document.createElement("i");
            meter.className = "meter";
            fill.style.setProperty("--w", `${Math.max(2, probability / maxProbability * 100)}%`);
            fill.style.setProperty("--c", color);
            meter.appendChild(fill);
            chance.appendChild(meter);
            chance.appendChild(document.createTextNode(`${(probability * 100).toFixed(1)}%`));
            cells.push(chance);

            const rain = document.createElement("td");
            rain.textContent = `${item.rain_3d_mm} mm`;
            cells.push(rain);

            cells.forEach(cell => row.appendChild(cell));
            table.appendChild(row);

            const marker = bdMarkers[item.location_id];

            if (marker) {
                marker.setStyle({ fillColor: color, color: color, fillOpacity: 0.85 });
                marker.setRadius(item.risk_level === "LOW" ? 5 : 9);
            }
        });

        wrap.appendChild(table);
        box.appendChild(wrap);
    } catch (error) {
        box.textContent =
            `No district predictions yet. ${error.message} ` +
            "Run run_ml.bat (option 1) to download NASA data and train the model.";
    }
}

async function districtSelected(id) {
    status("Loading district data...");

    const data = await api(`/bd/district/${id}`);
    renderWeather(data.weather || []);

    renderHistory(data.history || []);

    const prediction = data.prediction;

    if ($("risk")) $("risk").textContent = prediction ? prediction.risk_level : "--";

    if ($("prob")) {
        $("prob").textContent = prediction
            ? `${(Number(prediction.probability) * 100).toFixed(1)}%`
            : "--";
    }

    if ($("rainfallIndicator")) {
        $("rainfallIndicator").textContent = prediction ? `${prediction.rain_3d_mm} mm / 3 days` : "--";
    }

    if ($("rainfallDetails")) {
        $("rainfallDetails").textContent = prediction
            ? `District model input, as of ${prediction.as_of}`
            : "No prediction yet";
    }

    if (map) map.setView([data.latitude, data.longitude], 8);

    status(
        (data.notes || []).length
            ? data.notes.join(" ")
            : `${data.district}: data loaded. Press "Run prediction" for the model result.`
    );
}

async function districtPredict(id) {
    const button = $("predict");
    if (button) button.disabled = true;

    status("Loading the district model result...");

    try {
        const data = await api(`/bd/district/${id}`);
        const p = data.prediction;

        if (!p) {
            throw new Error((data.notes || []).join(" ") || "No prediction available yet.");
        }

        const probability = Number(p.probability);

        if ($("risk")) $("risk").textContent = p.risk_level;
        if ($("prob")) $("prob").textContent = `${(probability * 100).toFixed(1)}%`;

        status(
            `${data.district}: ${p.risk_level} - chance of a flood within ` +
            `${p.horizon_days} days, based on NASA data as of ${p.as_of}.`
        );

        const box = $("haor-result");

        if (box) {
            box.replaceChildren();
            box.classList.remove("empty");

            [
                [`Bangladesh district model: ${data.district} (${data.division} Division)`, true],
                [`Conditions as of: ${p.as_of} (NASA POWER / IMERG)`, false],
                [`Chance of a flood within ${p.horizon_days} days: ${(probability * 100).toFixed(1)}%`, false],
                [`Risk level: ${p.risk_level} (rank ${p.rank} of 64)`, false],
                [`Rain: ${p.rain_1d_mm} mm today, ${p.rain_3d_mm} mm in 3 days, ${p.rain_7d_mm} mm in 7 days`, false],
                [`Root-zone soil wetness: ${p.soil_wetness_root}`, false],
                [`Note: ${data.prediction_meta?.caveat ?? "Research estimate only."}`, false]
            ].forEach(([text, isHeading]) => {
                const element = document.createElement(isHeading ? "h3" : "p");
                element.textContent = text;
                box.appendChild(element);
            });
        }
    } catch (error) {
        showError(`Prediction failed: ${error.message}`);
    } finally {
        if (button) button.disabled = false;
    }
}

// ---------- Start dashboard ----------

document.addEventListener("DOMContentLoaded", async () => {
    try {
        if (typeof L === "undefined") {
            throw new Error(
                "Leaflet did not load. Check your internet connection."
            );
        }

        if (typeof Chart === "undefined") {
            throw new Error(
                "Chart.js did not load. Check your internet connection."
            );
        }

        map = L.map("map").setView([23.7, 90.4], 6);

        addBaseMap();
        watchRisk();

        // make sure Leaflet measures the box after the page layout has settled
        setTimeout(() => map.invalidateSize && map.invalidateSize(), 400);

        if (typeof window.addEventListener === "function") {
            window.addEventListener("resize", () => map.invalidateSize && map.invalidateSize());

            window.addEventListener("themechange", () => {
                if (lastWeather) drawWeatherCharts(lastWeather);
            });
        }

        $("locations")?.addEventListener("change", async () => {
            try {
                await selected();
            } catch (error) {
                showError(error.message);
            }
        });

        $("predict")?.addEventListener("click", predict);
        $("refresh")?.addEventListener("click", update);
        $("haor-form")?.addEventListener("submit", predictHaor);

        await load();
    } catch (error) {
        showError(`Dashboard loading failed: ${error.message}`);
    }
});
