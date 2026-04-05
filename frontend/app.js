// ═══════════════════════════════════════════════════════════
// app.js — BizIntel frontend logic
//
// Responsibilities:
//   1. Handle file selection (click + drag & drop)
//   2. Send file to backend via fetch (FormData)
//   3. Receive JSON and populate the UI
//   4. Draw Chart.js charts (line + bar)
//   5. Handle loading states and errors
// ═══════════════════════════════════════════════════════════

const API_URL = "http://localhost:5000/upload";

// ── DOM references ───────────────────────────────────────────
const dropZone     = document.getElementById("dropZone");
const fileInput    = document.getElementById("fileInput");
const selectedFile = document.getElementById("selectedFile");
const fileName     = document.getElementById("fileName");
const analyzeBtn   = document.getElementById("analyzeBtn");
const loader       = document.getElementById("loader");
const errorBanner  = document.getElementById("errorBanner");
const errorMessage = document.getElementById("errorMessage");
const results      = document.getElementById("results");

// We store chart instances so we can destroy them before
// re-drawing — otherwise Chart.js throws a "canvas already in use" error
// when the user analyzes a second file.
let lineChartInstance = null;
let barChartInstance  = null;

// ── Track selected file globally ───────────────────────────
let selectedFileObj = null;

// ═══════════════════════════════════════════════════════════
// FILE SELECTION — via click on "Browse File" label
// WHY: The label is styled as a button; the real <input> is
//      hidden. When the input changes we store the file and
//      show the file name row.
// ═══════════════════════════════════════════════════════════
fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
        handleFileSelected(fileInput.files[0]);
    }
});

// ═══════════════════════════════════════════════════════════
// DRAG & DROP
// WHY: A more natural UX than always clicking Browse.
//      We prevent the browser's default "open file" behaviour
//      and intercept the drop ourselves.
// ═══════════════════════════════════════════════════════════
dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();                          // Must prevent default to allow drop
    dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelected(file);
});

// Clicking anywhere on the drop zone opens the file picker
dropZone.addEventListener("click", (e) => {
    // Don't re-trigger if the label itself was clicked
    if (e.target.tagName !== "LABEL") fileInput.click();
});

// ═══════════════════════════════════════════════════════════
// HANDLE FILE SELECTED
// WHY: Central function so both click and drag paths
//      go through the same validation + UI update logic.
// ═══════════════════════════════════════════════════════════
function handleFileSelected(file) {
    const allowed = [".xlsx", ".xls", ".csv"];
    const ext     = "." + file.name.split(".").pop().toLowerCase();

    // Client-side type check — server also validates, but this
    // gives instant feedback without a network round-trip.
    if (!allowed.includes(ext)) {
        showError(`Invalid file type '${ext}'. Please upload .xlsx, .xls, or .csv`);
        return;
    }

    selectedFileObj = file;
    fileName.textContent = file.name;
    selectedFile.style.display = "flex";
    hideError();
}

// ═══════════════════════════════════════════════════════════
// ANALYZE BUTTON — sends the file to the backend
// ═══════════════════════════════════════════════════════════
analyzeBtn.addEventListener("click", async () => {
    if (!selectedFileObj) return;

    // — UI: enter loading state —
    analyzeBtn.disabled = true;
    showLoader();
    hideError();
    hideResults();

    // FormData is the correct way to send a file via fetch.
    // WHY "file": that must match the field name multer expects
    //             in upload.single("file") on the server.
    const formData = new FormData();
    formData.append("file", selectedFileObj);

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            body: formData
        });

        // Log raw response status so we can see it in the console
        console.log("Response status:", response.status);

        const data = await response.json();
        console.log("Response data:", data);

        // HTTP 4xx / 5xx — server returned an error object
        if (!response.ok) {
            throw new Error(data.message || "Server error");
        }

        // Guard: analysis object missing from response
        if (!data.analysis) {
            throw new Error("No analysis data returned from server.");
        }

        // — Success: render results —
        renderResults(data.analysis);

    } catch (err) {
        // Network failure OR JSON parse failure OR thrown error above
        console.error("BizIntel error:", err);
        showError(err.message || "Something went wrong. Is the server running?");
    } finally {
        // Always restore button, always hide loader
        hideLoader();
        analyzeBtn.disabled = false;
    }
});

// ═══════════════════════════════════════════════════════════
// RENDER RESULTS
// WHY: Separated from the fetch logic so the two concerns
//      (networking vs DOM updates) are clearly distinct.
// ═══════════════════════════════════════════════════════════
function renderResults(analysis) {

    // ── 1. Insights pills ────────────────────────────────────
    const strip = document.getElementById("insightsStrip");
    strip.innerHTML = "";

    if (analysis.insights && analysis.insights.length > 0) {
        analysis.insights.forEach(text => {
            const pill = document.createElement("div");
            pill.className = "insight-pill";
            pill.textContent = text;
            strip.appendChild(pill);
        });
    }

    // ── 2. Metric cards ──────────────────────────────────────
    // WHY toLocaleString: formats 456000 as "456,000" automatically.
    document.getElementById("totalSales").textContent =
        "₹" + (analysis.total_sales ?? 0).toLocaleString();

    document.getElementById("avgSales").textContent =
        "₹" + (analysis.average_sales ?? 0).toLocaleString();

    document.getElementById("totalOrders").textContent =
        (analysis.total_orders ?? 0).toLocaleString();

    document.getElementById("topProduct").textContent =
        analysis.top_product ?? "—";

    document.getElementById("lowestProduct").textContent =
        analysis.lowest_product ?? "—";

    document.getElementById("peakPeriod").textContent =
        analysis.peak_period ?? "—";

    // ── 3. Period label for chart subtitle ───────────────────
    document.getElementById("periodLabel").textContent =
        (analysis.period_label ?? "") + " breakdown";

    // ── 4. Draw charts ───────────────────────────────────────
    drawLineChart(analysis.sales_over_time ?? []);
    drawBarChart(analysis.product_sales ?? []);

    // ── 5. Show results section ──────────────────────────────
    results.style.display = "block";
    // Smooth scroll so the user doesn't miss the results
    results.scrollIntoView({ behavior: "smooth" });
}

// ═══════════════════════════════════════════════════════════
// DRAW LINE CHART — Sales over time
// WHY: Line charts are ideal for time-series because they
//      make trends (upward/downward) immediately visible.
// ═══════════════════════════════════════════════════════════
function drawLineChart(salesOverTime) {

    // Destroy previous chart if it exists
    if (lineChartInstance) lineChartInstance.destroy();

    const labels = salesOverTime.map(d => d.period);
    const values = salesOverTime.map(d => d.sales);

    const ctx = document.getElementById("lineChart").getContext("2d");

    // Gradient fill below the line for depth
    const gradient = ctx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, "rgba(232,255,71,0.25)");
    gradient.addColorStop(1, "rgba(232,255,71,0)");

    lineChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [{
                label: "Sales",
                data: values,
                borderColor: "#e8ff47",
                backgroundColor: gradient,
                borderWidth: 2,
                pointBackgroundColor: "#e8ff47",
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.35       // slight curve — less jagged than tension:0
            }]
        },
        options: chartOptions("Sales (₹)")
    });
}

// ═══════════════════════════════════════════════════════════
// DRAW BAR CHART — Product-wise sales
// WHY: Bar charts make it easy to compare magnitudes
//      across categories at a glance.
// ═══════════════════════════════════════════════════════════
function drawBarChart(productSales) {

    if (barChartInstance) barChartInstance.destroy();

    const labels = productSales.map(d => d.product);
    const values = productSales.map(d => d.sales);

    // Colour the highest bar in accent, rest in muted tones
    const maxVal = Math.max(...values);
    const colors = values.map(v =>
        v === maxVal ? "#e8ff47" : "rgba(232,255,71,0.35)"
    );

    const ctx = document.getElementById("barChart").getContext("2d");

    barChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label: "Sales",
                data: values,
                backgroundColor: colors,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: chartOptions("Sales (₹)")
    });
}

// ═══════════════════════════════════════════════════════════
// SHARED CHART OPTIONS
// WHY: Both charts share the same grid, font, and tooltip
//      style. A single options factory keeps them in sync.
// ═══════════════════════════════════════════════════════════
function chartOptions(yLabel) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: "#1c2030",
                titleColor: "#f0f2f8",
                bodyColor: "#6b7280",
                borderColor: "#272c3d",
                borderWidth: 1,
                callbacks: {
                    // Format tooltip values with ₹ and comma separators
                    label: ctx => " ₹" + ctx.parsed.y.toLocaleString()
                }
            }
        },
        scales: {
            x: {
                ticks: { color: "#6b7280", font: { size: 11 } },
                grid:  { color: "#1c2030" }
            },
            y: {
                title: { display: false },
                ticks: {
                    color: "#6b7280",
                    font:  { size: 11 },
                    // Compact large numbers: 456000 → "456K"
                    callback: v => v >= 1000 ? (v / 1000).toFixed(0) + "K" : v
                },
                grid: { color: "#272c3d" }
            }
        }
    };
}

// ═══════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════
function showLoader()   { loader.style.display = "block"; }
function hideLoader()   { loader.style.display = "none";  }
function hideResults()  { results.style.display = "none"; }

function showError(msg) {
    errorMessage.textContent = msg;
    errorBanner.style.display = "flex";
}

function hideError() {
    errorBanner.style.display = "none";
}

// Reset the entire UI back to the upload state.
// WHY: Called by both the ✕ on the error banner and the
//      "Analyze Another File" button.
function resetUI() {
    selectedFileObj = null;
    fileInput.value = "";
    selectedFile.style.display = "none";
    hideResults();
    hideError();
    hideLoader();

    if (lineChartInstance) { lineChartInstance.destroy(); lineChartInstance = null; }
    if (barChartInstance)  { barChartInstance.destroy();  barChartInstance  = null; }
}
