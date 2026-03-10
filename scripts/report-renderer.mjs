import fs from "node:fs";
import path from "node:path";

const COLORS = {
  ink: "#12202c",
  muted: "#5f6c77",
  line: "#d7ddd7",
  paper: "#f7f3ea",
  paperWarm: "#fcfaf5",
  green: "#1c7c74",
  teal: "#3b9c94",
  gold: "#d78f2f",
  coral: "#d8654d",
  navy: "#234d70",
  plum: "#7a5f9a",
  sand: "#eadfc7",
  success: "#2b8a5e",
};

const SERIES_COLORS = {
  knowledge_pct: COLORS.green,
  attitude_pct: COLORS.gold,
  practice_pct: COLORS.navy,
  bangalore_mean: COLORS.green,
  outside_mean: COLORS.coral,
};

const BASE_SVG_STYLE = `
  .title { font: 700 30px "Avenir Next", "Segoe UI", sans-serif; fill: ${COLORS.ink}; }
  .subtitle { font: 500 15px "Avenir Next", "Segoe UI", sans-serif; fill: ${COLORS.muted}; }
  .axis { font: 500 13px "Avenir Next", "Segoe UI", sans-serif; fill: ${COLORS.muted}; }
  .label { font: 600 15px "Avenir Next", "Segoe UI", sans-serif; fill: ${COLORS.ink}; }
  .labelMuted { font: 500 13px "Avenir Next", "Segoe UI", sans-serif; fill: ${COLORS.muted}; }
  .value { font: 700 14px "Avenir Next", "Segoe UI", sans-serif; fill: ${COLORS.ink}; }
  .small { font: 500 12px "Avenir Next", "Segoe UI", sans-serif; fill: ${COLORS.muted}; }
  .grid { stroke: ${COLORS.line}; stroke-width: 1; stroke-dasharray: 2 6; }
  .axisLine { stroke: ${COLORS.muted}; stroke-width: 1.25; }
`;

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function slugify(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function wrapWords(text, maxChars = 28) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const lines = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars || current.length === 0) {
      current = next;
      continue;
    }
    lines.push(current);
    current = word;
  }
  if (current) {
    lines.push(current);
  }
  return lines.slice(0, 3);
}

function renderTextLines(lines, x, y, lineHeight, className, anchor = "start") {
  const rendered = lines
    .map((line, index) => `<tspan x="${x}" dy="${index === 0 ? 0 : lineHeight}">${escapeXml(line)}</tspan>`)
    .join("");
  return `<text class="${className}" text-anchor="${anchor}" x="${x}" y="${y}">${rendered}</text>`;
}

function formatValue(value, format = "count") {
  if (format === "percent") {
    return `${Number(value).toFixed(1)}%`;
  }
  if (format === "rho") {
    return Number(value).toFixed(3);
  }
  return `${Math.round(Number(value))}`;
}

function niceMax(value) {
  const target = Math.max(Number(value) || 0, 1);
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const normalized = target / magnitude;
  let rounded = 1;
  if (normalized > 1 && normalized <= 2) rounded = 2;
  else if (normalized <= 5) rounded = 5;
  else rounded = 10;
  return rounded * magnitude;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function hexToRgb(hex) {
  const normalized = hex.replace("#", "");
  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

function mixColor(startHex, endHex, ratio) {
  const start = hexToRgb(startHex);
  const end = hexToRgb(endHex);
  const safeRatio = clamp(ratio, 0, 1);
  const r = Math.round(start.r + (end.r - start.r) * safeRatio);
  const g = Math.round(start.g + (end.g - start.g) * safeRatio);
  const b = Math.round(start.b + (end.b - start.b) * safeRatio);
  return `rgb(${r}, ${g}, ${b})`;
}

function valueKey(spec) {
  return spec.value_key || spec.valueKey || "count";
}

function labelKey(spec) {
  return spec.label_key || spec.labelKey || "label";
}

function seriesLabel(key) {
  return {
    knowledge_pct: "Knowledge",
    attitude_pct: "Attitude",
    practice_pct: "Practice",
    bangalore_mean: "Bangalore",
    outside_mean: "Outside Bangalore",
  }[key] || key;
}

function chartShell({ width, height, title, subtitle, body, extraDefs = "" }) {
  const titleLines = wrapWords(title, 42).slice(0, 2);
  const subtitleLines = wrapWords(subtitle || "", 82).slice(0, 2);
  const titleText = titleLines
    .map((line, index) => `<tspan x="52" dy="${index === 0 ? 0 : 34}">${escapeXml(line)}</tspan>`)
    .join("");
  const subtitleStart = 68 + (titleLines.length - 1) * 34 + 28;
  const subtitleText = subtitleLines
    .map((line, index) => `<tspan x="52" dy="${index === 0 ? 0 : 18}">${escapeXml(line)}</tspan>`)
    .join("");
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="${slugify(title)}-title ${slugify(title)}-subtitle">
  <defs>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#0f1a24" flood-opacity="0.08" />
    </filter>
    ${extraDefs}
  </defs>
  <style>${BASE_SVG_STYLE}</style>
  <rect x="0" y="0" width="${width}" height="${height}" rx="30" fill="${COLORS.paperWarm}" />
  <rect x="16" y="16" width="${width - 32}" height="${height - 32}" rx="26" fill="${COLORS.paper}" stroke="${COLORS.line}" />
  <text id="${slugify(title)}-title" class="title" x="52" y="68">${titleText}</text>
  <text id="${slugify(title)}-subtitle" class="subtitle" x="52" y="${subtitleStart}">${subtitleText}</text>
  ${body}
</svg>`;
}

function polarToCartesian(cx, cy, radius, angleInDegrees) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
  return {
    x: cx + radius * Math.cos(angleInRadians),
    y: cy + radius * Math.sin(angleInRadians),
  };
}

function donutPath(cx, cy, outerRadius, innerRadius, startAngle, endAngle) {
  const startOuter = polarToCartesian(cx, cy, outerRadius, endAngle);
  const endOuter = polarToCartesian(cx, cy, outerRadius, startAngle);
  const startInner = polarToCartesian(cx, cy, innerRadius, startAngle);
  const endInner = polarToCartesian(cx, cy, innerRadius, endAngle);
  const largeArc = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    "M",
    startOuter.x,
    startOuter.y,
    "A",
    outerRadius,
    outerRadius,
    0,
    largeArc,
    0,
    endOuter.x,
    endOuter.y,
    "L",
    startInner.x,
    startInner.y,
    "A",
    innerRadius,
    innerRadius,
    0,
    largeArc,
    1,
    endInner.x,
    endInner.y,
    "Z",
  ].join(" ");
}

function renderDonut(spec) {
  const width = 1120;
  const height = 640;
  const data = spec.data || [];
  const total = data.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const colors = [COLORS.green, COLORS.navy, COLORS.gold, COLORS.coral, COLORS.plum, COLORS.teal];
  const cx = 250;
  const cy = 340;
  const outerRadius = 140;
  const innerRadius = 84;
  let angle = 0;
  const paths = [];
  const legends = [];
  data.forEach((row, index) => {
    const value = Number(row.count || 0);
    const slice = total ? (value / total) * 360 : 0;
    const fill = colors[index % colors.length];
    paths.push(`<path d="${donutPath(cx, cy, outerRadius, innerRadius, angle, angle + slice)}" fill="${fill}" stroke="${COLORS.paperWarm}" stroke-width="3" />`);
    const legendY = 220 + index * 68;
    legends.push(`
      <rect x="560" y="${legendY - 14}" width="18" height="18" rx="4" fill="${fill}" />
      <text class="label" x="590" y="${legendY}">${escapeXml(row.label)}</text>
      <text class="labelMuted" x="590" y="${legendY + 22}">${value} respondents (${Number(row.percent ?? row.percent_of_bangalore ?? 0).toFixed(1)}%)</text>
    `);
    angle += slice;
  });
  const centerLines = String(spec.center_label || "").split("\n");
  const centerText = centerLines
    .map((line, index) => `<tspan x="${cx}" dy="${index === 0 ? 0 : 28}">${escapeXml(line)}</tspan>`)
    .join("");
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: `
      <g filter="url(#softShadow)">
        ${paths.join("")}
        <circle cx="${cx}" cy="${cy}" r="${innerRadius - 4}" fill="${COLORS.paperWarm}" />
      </g>
      <text class="title" text-anchor="middle" x="${cx}" y="${cy - (centerLines.length - 1) * 14}">${centerText}</text>
      <text class="subtitle" x="560" y="166">Legend</text>
      ${legends.join("")}
    `,
  });
}

function renderHorizontalBar(spec) {
  const data = spec.data || [];
  const width = 1120;
  const height = 180 + data.length * 54;
  const chartX = 360;
  const chartY = 150;
  const chartWidth = 680;
  const barHeight = 22;
  const key = valueKey(spec);
  const label = labelKey(spec);
  const values = data.map((row) => Number(row[key] || 0));
  const maxValue = niceMax(Math.max(...values) * 1.08);
  const gridTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ratio * maxValue);
  const rows = [];

  gridTicks.forEach((tick) => {
    const x = chartX + (tick / maxValue) * chartWidth;
    rows.push(`<line class="grid" x1="${x}" x2="${x}" y1="${chartY - 16}" y2="${height - 48}" />`);
    rows.push(`<text class="axis" text-anchor="middle" x="${x}" y="${height - 20}">${formatValue(tick, spec.format)}</text>`);
  });

  data.forEach((row, index) => {
    const y = chartY + index * 54;
    const barWidth = (Number(row[key] || 0) / maxValue) * chartWidth;
    const color = index === 0 ? COLORS.green : mixColor(COLORS.sand, COLORS.green, 0.45 + index * 0.05);
    rows.push(`<rect x="${chartX}" y="${y}" width="${chartWidth}" height="${barHeight}" rx="11" fill="#ebe6db" />`);
    rows.push(`<rect x="${chartX}" y="${y}" width="${barWidth}" height="${barHeight}" rx="11" fill="${color}" />`);
    const labelLines = wrapWords(row[label], 26);
    rows.push(renderTextLines(labelLines, 44, y + 16, 16, "label"));
    rows.push(`<text class="value" x="${chartX + barWidth + 12}" y="${y + 16}">${formatValue(row[key], spec.format)}</text>`);
  });

  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: rows.join(""),
  });
}

function renderLollipop(spec) {
  const data = spec.data || [];
  const width = 1120;
  const height = 180 + data.length * 54;
  const chartX = 360;
  const chartY = 150;
  const chartWidth = 680;
  const key = valueKey(spec);
  const label = labelKey(spec);
  const maxValue = 100;
  const parts = [];
  [0, 25, 50, 75, 100].forEach((tick) => {
    const x = chartX + (tick / maxValue) * chartWidth;
    parts.push(`<line class="grid" x1="${x}" x2="${x}" y1="${chartY - 16}" y2="${height - 48}" />`);
    parts.push(`<text class="axis" text-anchor="middle" x="${x}" y="${height - 20}">${tick}%</text>`);
  });
  data.forEach((row, index) => {
    const y = chartY + index * 54;
    const value = Number(row[key] || 0);
    const x = chartX + (value / maxValue) * chartWidth;
    parts.push(`<line x1="${chartX}" x2="${x}" y1="${y + 11}" y2="${y + 11}" stroke="${COLORS.line}" stroke-width="6" stroke-linecap="round" />`);
    parts.push(`<circle cx="${x}" cy="${y + 11}" r="12" fill="${index === 0 ? COLORS.coral : COLORS.green}" stroke="${COLORS.paperWarm}" stroke-width="3" />`);
    parts.push(renderTextLines(wrapWords(row[label], 24), 44, y + 16, 16, "label"));
    parts.push(`<text class="value" x="${x + 18}" y="${y + 16}">${value.toFixed(1)}%</text>`);
  });
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: parts.join(""),
  });
}

function renderLegendItems(items, startX, startY) {
  return items
    .map((item, index) => {
      const x = startX + index * 170;
      return `
        <circle cx="${x}" cy="${startY}" r="7" fill="${item.color}" />
        <text class="labelMuted" x="${x + 14}" y="${startY + 5}">${escapeXml(item.label)}</text>
      `;
    })
    .join("");
}

function renderMultiDot(spec) {
  const data = spec.data || [];
  const width = 1180;
  const height = 190 + data.length * 58;
  const chartX = 380;
  const chartY = 164;
  const chartWidth = 700;
  const rows = [];
  [0, 20, 40, 60, 80, 100].forEach((tick) => {
    const x = chartX + (tick / 100) * chartWidth;
    rows.push(`<line class="grid" x1="${x}" x2="${x}" y1="${chartY - 24}" y2="${height - 42}" />`);
    rows.push(`<text class="axis" text-anchor="middle" x="${x}" y="${height - 18}">${tick}%</text>`);
  });
  rows.push(
    renderLegendItems(
      spec.series.map((key) => ({ label: seriesLabel(key), color: SERIES_COLORS[key] })),
      420,
      126,
    ),
  );

  data.forEach((row, index) => {
    const y = chartY + index * 58;
    const values = spec.series.map((key) => Number(row[key] || 0));
    const minX = chartX + (Math.min(...values) / 100) * chartWidth;
    const maxX = chartX + (Math.max(...values) / 100) * chartWidth;
    rows.push(`<line x1="${minX}" x2="${maxX}" y1="${y}" y2="${y}" stroke="#c2cbc2" stroke-width="4" stroke-linecap="round" />`);
    spec.series.forEach((key) => {
      const x = chartX + (Number(row[key] || 0) / 100) * chartWidth;
      rows.push(`<circle cx="${x}" cy="${y}" r="10" fill="${SERIES_COLORS[key]}" stroke="${COLORS.paperWarm}" stroke-width="3" />`);
    });
    rows.push(renderTextLines(wrapWords(row.label, 24), 44, y + 5, 16, "label"));
    rows.push(`<text class="labelMuted" x="300" y="${y + 5}">n=${row.n}</text>`);
  });

  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: rows.join(""),
  });
}

function renderDumbbell(spec) {
  const data = spec.data || [];
  const width = 1180;
  const height = 190 + data.length * 58;
  const chartX = 380;
  const chartY = 164;
  const chartWidth = 700;
  const leftKey = spec.left_key || spec.leftKey;
  const rightKey = spec.right_key || spec.rightKey;
  const label = labelKey(spec);
  const isPct = spec.format === "percent" || leftKey.includes("mean") || leftKey.includes("_pct");
  const axisMax = isPct ? 100 : niceMax(
    Math.max(...data.flatMap((row) => [Number(row[leftKey] || 0), Number(row[rightKey] || 0)])) * 1.08,
  );
  const rows = [];
  const ticks = isPct ? [0, 20, 40, 60, 80, 100] : [0, axisMax * 0.25, axisMax * 0.5, axisMax * 0.75, axisMax];
  ticks.forEach((tick) => {
    const x = chartX + (tick / axisMax) * chartWidth;
    rows.push(`<line class="grid" x1="${x}" x2="${x}" y1="${chartY - 24}" y2="${height - 42}" />`);
    rows.push(`<text class="axis" text-anchor="middle" x="${x}" y="${height - 18}">${formatValue(tick, spec.format)}</text>`);
  });
  rows.push(
    renderLegendItems(
      [
        { label: seriesLabel(leftKey), color: SERIES_COLORS[leftKey] || COLORS.coral },
        { label: seriesLabel(rightKey), color: SERIES_COLORS[rightKey] || COLORS.green },
      ],
      460,
      126,
    ),
  );
  data.forEach((row, index) => {
    const y = chartY + index * 58;
    const leftValue = Number(row[leftKey] || 0);
    const rightValue = Number(row[rightKey] || 0);
    const leftX = chartX + (leftValue / axisMax) * chartWidth;
    const rightX = chartX + (rightValue / axisMax) * chartWidth;
    rows.push(`<line x1="${Math.min(leftX, rightX)}" x2="${Math.max(leftX, rightX)}" y1="${y}" y2="${y}" stroke="#c5cdcf" stroke-width="5" stroke-linecap="round" />`);
    rows.push(`<circle cx="${leftX}" cy="${y}" r="11" fill="${SERIES_COLORS[leftKey] || COLORS.coral}" stroke="${COLORS.paperWarm}" stroke-width="3" />`);
    rows.push(`<circle cx="${rightX}" cy="${y}" r="11" fill="${SERIES_COLORS[rightKey] || COLORS.green}" stroke="${COLORS.paperWarm}" stroke-width="3" />`);
    rows.push(renderTextLines(wrapWords(row[label], 24), 44, y + 5, 16, "label"));
  });
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: rows.join(""),
  });
}

function renderDivergingLikert(spec) {
  const data = spec.data || [];
  const width = 1280;
  const rowHeights = data.map((row) => Math.max(50, wrapWords(row.statement, 34).length * 18 + 18));
  const height = 210 + rowHeights.reduce((sum, value) => sum + value, 0);
  const chartX = 490;
  const chartY = 172;
  const chartWidth = 700;
  const parts = [];
  [0, 25, 50, 75, 100].forEach((tick) => {
    const x = chartX + (tick / 100) * chartWidth;
    parts.push(`<line class="grid" x1="${x}" x2="${x}" y1="${chartY - 28}" y2="${height - 42}" />`);
    parts.push(`<text class="axis" text-anchor="middle" x="${x}" y="${height - 20}">${Math.abs(tick - 50) * 2}%</text>`);
  });
  parts.push(`<line class="axisLine" x1="${chartX + chartWidth / 2}" x2="${chartX + chartWidth / 2}" y1="${chartY - 28}" y2="${height - 42}" />`);
  parts.push(
    renderLegendItems(
      [
        { label: "Strongly Disagree", color: COLORS.coral },
        { label: "Disagree", color: "#e7bf75" },
        { label: "Agree", color: COLORS.teal },
        { label: "Strongly Agree", color: COLORS.navy },
      ],
      520,
      126,
    ),
  );
  let y = chartY;
  data.forEach((row, index) => {
    const rowHeight = rowHeights[index];
    const centerY = y + rowHeight / 2 - 4;
    const wrap = wrapWords(row.statement, 34);
    parts.push(renderTextLines(wrap, 44, centerY - (wrap.length - 1) * 8, 18, "label"));
    const sd = Number(row.strongly_disagree || 0);
    const dis = Number(row.disagree || 0);
    const agr = Number(row.agree || 0);
    const sagr = Number(row.strongly_agree || 0);
    const totalNeg = sd + dis;
    const zeroX = chartX + chartWidth / 2;
    const scale = (value) => (value / 100) * (chartWidth / 2);
    const leftStart = zeroX - scale(totalNeg);
    const disWidth = scale(dis);
    const sdWidth = scale(sd);
    const agrWidth = scale(agr);
    const sagrWidth = scale(sagr);
    parts.push(`<rect x="${leftStart}" y="${centerY - 12}" width="${disWidth}" height="24" rx="10" fill="#e7bf75" />`);
    parts.push(`<rect x="${leftStart + disWidth}" y="${centerY - 12}" width="${sdWidth}" height="24" rx="10" fill="${COLORS.coral}" />`);
    parts.push(`<rect x="${zeroX}" y="${centerY - 12}" width="${agrWidth}" height="24" rx="10" fill="${COLORS.teal}" />`);
    parts.push(`<rect x="${zeroX + agrWidth}" y="${centerY - 12}" width="${sagrWidth}" height="24" rx="10" fill="${COLORS.navy}" />`);
    y += rowHeight;
  });
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: parts.join(""),
  });
}

function renderHeatmap(spec) {
  const data = spec.data || [];
  const width = 1240;
  const height = 220 + data.length * 60;
  const chartX = 400;
  const chartY = 166;
  const cellWidth = 170;
  const cellHeight = 44;
  const columns = [
    { label: "Least healthy", key: "least_healthy" },
    { label: "Needs work", key: "needs_work" },
    { label: "Reasonable", key: "reasonable" },
    { label: "Best practice", key: "best_practice" },
  ];
  const body = [];
  columns.forEach((column, index) => {
    const x = chartX + index * cellWidth;
    body.push(`<text class="labelMuted" text-anchor="middle" x="${x + cellWidth / 2}" y="${chartY - 26}">${escapeXml(column.label)}</text>`);
  });
  data.forEach((row, rowIndex) => {
    const y = chartY + rowIndex * 60;
    body.push(renderTextLines(wrapWords(row.short, 24), 44, y + 12, 16, "label"));
    columns.forEach((column, columnIndex) => {
      const x = chartX + columnIndex * cellWidth;
      const value = Number(row[column.key] || 0);
      const fill = mixColor("#f1eadc", COLORS.navy, value / 100);
      const textColor = value >= 55 ? "#ffffff" : COLORS.ink;
      body.push(`<rect x="${x}" y="${y - 18}" width="${cellWidth - 12}" height="${cellHeight}" rx="12" fill="${fill}" />`);
      body.push(`<text class="value" fill="${textColor}" text-anchor="middle" x="${x + (cellWidth - 12) / 2}" y="${y + 8}">${value.toFixed(1)}%</text>`);
    });
  });
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: body.join(""),
  });
}

function renderRangePanel(spec) {
  const data = spec.data || [];
  const width = 1120;
  const height = 240 + data.length * 90;
  const chartX = 300;
  const chartY = 180;
  const chartWidth = 700;
  const body = [];
  [0, 20, 40, 60, 80, 100].forEach((tick) => {
    const x = chartX + (tick / 100) * chartWidth;
    body.push(`<line class="grid" x1="${x}" x2="${x}" y1="${chartY - 32}" y2="${height - 48}" />`);
    body.push(`<text class="axis" text-anchor="middle" x="${x}" y="${height - 18}">${tick}%</text>`);
  });
  data.forEach((row, index) => {
    const y = chartY + index * 90;
    const lineY = y;
    const color = SERIES_COLORS[`${row.metric}`] || [COLORS.green, COLORS.gold, COLORS.navy][index % 3];
    const minX = chartX + (Number(row.min_pct) / 100) * chartWidth;
    const q1X = chartX + (Number(row.q1_pct) / 100) * chartWidth;
    const medianX = chartX + (Number(row.median_pct) / 100) * chartWidth;
    const q3X = chartX + (Number(row.q3_pct) / 100) * chartWidth;
    const maxX = chartX + (Number(row.max_pct) / 100) * chartWidth;
    const meanX = chartX + (Number(row.mean_pct) / 100) * chartWidth;
    body.push(`<text class="label" x="44" y="${y + 5}">${escapeXml(row.label)}</text>`);
    body.push(`<text class="labelMuted" x="44" y="${y + 27}">Mean ${Number(row.mean_pct).toFixed(1)}%</text>`);
    body.push(`<line x1="${minX}" x2="${maxX}" y1="${lineY}" y2="${lineY}" stroke="#c2c9c5" stroke-width="5" stroke-linecap="round" />`);
    body.push(`<rect x="${q1X}" y="${lineY - 16}" width="${Math.max(q3X - q1X, 8)}" height="32" rx="12" fill="${color}" opacity="0.88" />`);
    body.push(`<line x1="${medianX}" x2="${medianX}" y1="${lineY - 18}" y2="${lineY + 18}" stroke="${COLORS.paperWarm}" stroke-width="4" />`);
    body.push(`<circle cx="${meanX}" cy="${lineY}" r="7" fill="${COLORS.paperWarm}" stroke="${COLORS.ink}" stroke-width="2" />`);
  });
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: body.join(""),
  });
}

function renderSubgroupHeatmap(spec) {
  const data = spec.data || [];
  const width = 1220;
  const height = 220 + data.length * 52;
  const chartX = 520;
  const chartY = 166;
  const cellWidth = 150;
  const cellHeight = 34;
  const body = [];
  const columns = [
    { key: "knowledge_pct", label: "Knowledge" },
    { key: "attitude_pct", label: "Attitude" },
    { key: "practice_pct", label: "Practice" },
  ];
  columns.forEach((column, index) => {
    const x = chartX + index * cellWidth;
    body.push(`<text class="labelMuted" text-anchor="middle" x="${x + cellWidth / 2 - 6}" y="${chartY - 26}">${escapeXml(column.label)}</text>`);
  });
  body.push(`<text class="labelMuted" text-anchor="middle" x="452" y="${chartY - 26}">n</text>`);
  let previousGroup = "";
  data.forEach((row, rowIndex) => {
    const y = chartY + rowIndex * 52;
    if (row.group !== previousGroup) {
      body.push(`<text class="small" x="44" y="${y - 14}">${escapeXml(row.group)}</text>`);
      previousGroup = row.group;
    }
    body.push(renderTextLines(wrapWords(row.level, 24), 44, y + 10, 16, "label"));
    body.push(`<text class="labelMuted" text-anchor="middle" x="452" y="${y + 10}">${row.n}</text>`);
    columns.forEach((column, columnIndex) => {
      const x = chartX + columnIndex * cellWidth;
      const value = Number(row[column.key] || 0);
      const fill = mixColor("#f1eadc", COLORS.green, (value - 45) / 45);
      const textColor = value >= 70 ? "#ffffff" : COLORS.ink;
      body.push(`<rect x="${x}" y="${y - 16}" width="${cellWidth - 12}" height="${cellHeight}" rx="10" fill="${fill}" />`);
      body.push(`<text class="value" fill="${textColor}" text-anchor="middle" x="${x + (cellWidth - 12) / 2}" y="${y + 8}">${value.toFixed(1)}%</text>`);
    });
  });
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: body.join(""),
  });
}

function renderCorrelationCircles(spec) {
  const width = 920;
  const height = 640;
  const chartX = 220;
  const chartY = 180;
  const cell = 160;
  const labels = ["Knowledge", "Attitude", "Practice"];
  const lookup = new Map();
  for (const row of spec.data || []) {
    lookup.set(`${row.left}|${row.right}`, row);
    lookup.set(`${row.right}|${row.left}`, row);
  }
  const metricKey = {
    Knowledge: "knowledge_pct",
    Attitude: "attitude_pct",
    Practice: "practice_pct",
  };
  const body = [];
  labels.forEach((label, index) => {
    const pos = chartX + index * cell + cell / 2;
    body.push(`<text class="label" text-anchor="middle" x="${pos}" y="${chartY - 36}">${label}</text>`);
    body.push(`<text class="label" x="54" y="${chartY + index * cell + cell / 2 + 6}">${label}</text>`);
  });
  labels.forEach((rowLabel, rowIndex) => {
    labels.forEach((colLabel, colIndex) => {
      const x = chartX + colIndex * cell;
      const y = chartY + rowIndex * cell;
      body.push(`<rect x="${x}" y="${y}" width="${cell - 16}" height="${cell - 16}" rx="22" fill="#f3ede1" stroke="${COLORS.line}" />`);
      if (rowLabel === colLabel) {
        body.push(`<text class="labelMuted" text-anchor="middle" x="${x + (cell - 16) / 2}" y="${y + 82}">Same metric</text>`);
      } else {
        const row = lookup.get(`${metricKey[rowLabel]}|${metricKey[colLabel]}`);
        const rho = Math.abs(Number(row?.rho || 0));
        const radius = 22 + rho * 38;
        const fill = mixColor("#f2dccb", COLORS.navy, rho);
        body.push(`<circle cx="${x + (cell - 16) / 2}" cy="${y + (cell - 16) / 2}" r="${radius}" fill="${fill}" opacity="0.92" />`);
        body.push(`<text class="value" text-anchor="middle" x="${x + (cell - 16) / 2}" y="${y + (cell - 16) / 2 + 6}" fill="#ffffff">${Number(row?.rho || 0).toFixed(3)}</text>`);
      }
    });
  });
  return chartShell({
    width,
    height,
    title: spec.title,
    subtitle: spec.subtitle,
    body: body.join(""),
  });
}

export function renderChartSvg(spec) {
  switch (spec.kind) {
    case "donut":
      return renderDonut(spec);
    case "horizontal-bar":
      return renderHorizontalBar(spec);
    case "lollipop":
      return renderLollipop(spec);
    case "multi-dot":
      return renderMultiDot(spec);
    case "dumbbell":
      return renderDumbbell(spec);
    case "diverging-likert":
      return renderDivergingLikert(spec);
    case "heatmap":
      return renderHeatmap(spec);
    case "range-panel":
      return renderRangePanel(spec);
    case "subgroup-heatmap":
      return renderSubgroupHeatmap(spec);
    case "correlation-circles":
      return renderCorrelationCircles(spec);
    default:
      throw new Error(`Unsupported chart kind: ${spec.kind}`);
  }
}

function renderFigureCard(spec, svgMarkup) {
  return `
    <figure class="figure-card" data-figure-title="${escapeHtml(spec.title || "")}" data-figure-caption="${escapeHtml(spec.caption || "")}">
      <button class="figure-expand" type="button" aria-label="Expand graph: ${escapeHtml(spec.title || "Chart")}">
        <span class="figure-expand__icon" aria-hidden="true">+</span>
        <span class="figure-expand__label">Expand</span>
      </button>
      <div class="figure-art" role="button" tabindex="0" aria-label="Open expanded graph: ${escapeHtml(spec.title || "Chart")}">${svgMarkup}</div>
      <figcaption class="figure-caption">${escapeHtml(spec.caption || "")}</figcaption>
    </figure>
  `;
}

function renderHighlights(items) {
  if (!items?.length) {
    return "";
  }
  return `<ul class="highlights">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderTable(title, rows, columns) {
  if (!rows?.length) {
    return "";
  }
  return `
    <div class="table-block">
      <h3>${escapeHtml(title)}</h3>
      <table>
        <thead>
          <tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) =>
                `<tr>${columns
                  .map((column) => `<td>${escapeHtml(column.render ? column.render(row) : row[column.key])}</td>`)
                  .join("")}</tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

export function renderReportHtml(reportData, chartSvgs) {
  const navItems = [
    ...reportData.sections.map((section) => ({ id: section.id, label: section.title })),
    { id: "insights", label: "Insights" },
    { id: "appendix", label: "Method note and appendix" },
  ];
  const significantSubgroups = reportData.tables.subgroup_tests.filter((row) => row.p_value <= 0.05).slice(0, 10);
  const regressionHighlights = reportData.tables.regression_highlights.slice(0, 10);
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(reportData.meta.title)}</title>
    <style>
      :root {
        --paper: #f7f3ea;
        --paper-alt: #fcfaf5;
        --ink: #12202c;
        --muted: #5f6c77;
        --green: #1c7c74;
        --navy: #234d70;
        --gold: #d78f2f;
        --coral: #d8654d;
        --line: #d8dfd9;
        --shadow: 0 26px 60px rgba(18, 32, 44, 0.08);
      }
      * { box-sizing: border-box; }
      html { scroll-behavior: smooth; }
      body {
        margin: 0;
        background:
          radial-gradient(circle at top left, rgba(28, 124, 116, 0.08), transparent 38%),
          radial-gradient(circle at top right, rgba(215, 143, 47, 0.08), transparent 34%),
          linear-gradient(180deg, #fffdf8 0%, var(--paper) 100%);
        color: var(--ink);
        font: 500 16px/1.6 "Avenir Next", "Segoe UI", sans-serif;
      }
      .layout {
        display: grid;
        grid-template-columns: 280px minmax(0, 1fr);
        max-width: 1600px;
        margin: 0 auto;
      }
      .rail {
        position: sticky;
        top: 0;
        align-self: start;
        min-height: 100vh;
        padding: 40px 28px;
        border-right: 1px solid rgba(18, 32, 44, 0.08);
        background: rgba(252, 250, 245, 0.86);
        backdrop-filter: blur(16px);
      }
      .rail h1 {
        margin: 0 0 18px;
        font: 700 22px/1.14 "Avenir Next", "Segoe UI", sans-serif;
      }
      .rail p {
        margin: 0 0 24px;
        color: var(--muted);
      }
      .rail nav a {
        display: block;
        padding: 10px 12px;
        margin: 4px 0;
        border-radius: 12px;
        color: var(--ink);
        text-decoration: none;
      }
      .rail nav a:hover {
        background: rgba(28, 124, 116, 0.08);
      }
      main {
        padding: 38px 44px 96px;
      }
      .hero {
        margin-bottom: 28px;
        padding: 40px;
        background: rgba(252, 250, 245, 0.88);
        border: 1px solid rgba(18, 32, 44, 0.08);
        border-radius: 28px;
        box-shadow: var(--shadow);
      }
      .eyebrow {
        display: inline-flex;
        padding: 7px 12px;
        border-radius: 999px;
        background: rgba(28, 124, 116, 0.1);
        color: var(--green);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .hero h2,
      section h2,
      #insights h2,
      #appendix h2 {
        margin: 16px 0 12px;
        font: 700 36px/1.08 "Iowan Old Style", "Georgia", serif;
      }
      .hero p,
      section p,
      #insights p,
      #appendix p {
        max-width: 74ch;
        color: var(--muted);
      }
      .kpis {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 18px;
        margin-top: 28px;
      }
      .kpi {
        padding: 18px 20px;
        border-radius: 20px;
        background: linear-gradient(180deg, rgba(255,255,255,0.76), rgba(244,239,228,0.9));
        border: 1px solid rgba(18, 32, 44, 0.08);
      }
      .kpi-value {
        font: 700 32px/1 "Iowan Old Style", "Georgia", serif;
        margin-bottom: 8px;
      }
      .kpi-label {
        font-weight: 700;
      }
      .kpi-detail {
        color: var(--muted);
        font-size: 14px;
      }
      .hero-notes {
        display: grid;
        grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
        gap: 28px;
        margin-top: 24px;
      }
      .notes-card,
      .summary-card {
        padding: 22px 24px;
        border-radius: 22px;
        background: rgba(255,255,255,0.72);
        border: 1px solid rgba(18, 32, 44, 0.08);
      }
      .summary-card h3,
      .notes-card h3,
      .table-block h3 {
        margin: 0 0 12px;
        font: 700 20px/1.2 "Avenir Next", "Segoe UI", sans-serif;
      }
      section,
      #insights,
      #appendix {
        margin-top: 40px;
        padding: 34px 34px 30px;
        border-radius: 28px;
        background: rgba(252, 250, 245, 0.92);
        border: 1px solid rgba(18, 32, 44, 0.08);
        box-shadow: var(--shadow);
      }
      .section-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 22px;
        margin-top: 24px;
      }
      .figure-card {
        position: relative;
        margin: 0;
        padding: 18px;
        border-radius: 22px;
        background: rgba(255,255,255,0.76);
        border: 1px solid rgba(18, 32, 44, 0.08);
      }
      .figure-expand {
        position: absolute;
        top: 28px;
        right: 28px;
        z-index: 2;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border: 0;
        border-radius: 999px;
        background: rgba(18, 32, 44, 0.84);
        color: #fffdf8;
        cursor: pointer;
        opacity: 0;
        transform: translateY(-4px);
        transition: opacity 180ms ease, transform 180ms ease, background 180ms ease;
        box-shadow: 0 16px 34px rgba(18, 32, 44, 0.18);
      }
      .figure-expand:hover,
      .figure-expand:focus-visible {
        background: rgba(28, 124, 116, 0.92);
        outline: none;
      }
      .figure-expand__icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.36);
        font-size: 16px;
        line-height: 1;
        font-weight: 700;
      }
      .figure-expand__label {
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.03em;
      }
      .figure-card:hover .figure-expand,
      .figure-card:focus-within .figure-expand {
        opacity: 1;
        transform: translateY(0);
      }
      .figure-art {
        cursor: zoom-in;
      }
      .figure-art:focus-visible {
        outline: 3px solid rgba(28, 124, 116, 0.34);
        outline-offset: 6px;
        border-radius: 16px;
      }
      .figure-art svg {
        width: 100%;
        height: auto;
        display: block;
        border-radius: 18px;
      }
      .figure-caption {
        margin-top: 14px;
        color: var(--muted);
      }
      .chart-overlay[hidden] {
        display: none;
      }
      .chart-overlay {
        position: fixed;
        inset: 0;
        z-index: 1000;
      }
      .chart-overlay__scrim {
        position: absolute;
        inset: 0;
        background: rgba(11, 18, 26, 0.72);
        backdrop-filter: blur(10px);
      }
      .chart-overlay__dialog {
        position: relative;
        z-index: 1;
        width: min(94vw, 1520px);
        max-height: calc(100vh - 48px);
        margin: 24px auto;
        padding: 28px;
        border-radius: 30px;
        background: rgba(252, 250, 245, 0.98);
        border: 1px solid rgba(18, 32, 44, 0.12);
        box-shadow: 0 28px 80px rgba(0, 0, 0, 0.24);
        overflow: auto;
      }
      .chart-overlay__close {
        position: sticky;
        top: 0;
        float: right;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        margin-left: auto;
        border: 0;
        border-radius: 50%;
        background: rgba(18, 32, 44, 0.08);
        color: var(--ink);
        font-size: 28px;
        line-height: 1;
        cursor: pointer;
      }
      .chart-overlay__close:hover,
      .chart-overlay__close:focus-visible {
        background: rgba(18, 32, 44, 0.14);
        outline: none;
      }
      .chart-overlay__header {
        clear: both;
        margin-bottom: 18px;
      }
      .chart-overlay__header h3 {
        margin: 12px 0 8px;
        font: 700 34px/1.08 "Iowan Old Style", "Georgia", serif;
      }
      .chart-overlay__header p {
        margin: 0;
        color: var(--muted);
      }
      .chart-overlay__canvas {
        padding: 16px;
        border-radius: 24px;
        background: rgba(255,255,255,0.76);
        border: 1px solid rgba(18, 32, 44, 0.08);
      }
      .chart-overlay__canvas svg {
        width: 100%;
        height: auto;
        max-height: calc(100vh - 240px);
        display: block;
        margin: 0 auto;
      }
      body.overlay-open {
        overflow: hidden;
      }
      .highlights {
        margin: 18px 0 0;
        padding-left: 18px;
      }
      .highlights li {
        margin: 0 0 10px;
      }
      .insight-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 24px;
        margin-top: 24px;
      }
      .insight-card {
        display: grid;
        grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
        gap: 22px;
        padding: 26px;
        border-radius: 24px;
        background: linear-gradient(180deg, rgba(255,255,255,0.84), rgba(244,239,228,0.92));
        border: 1px solid rgba(18, 32, 44, 0.08);
      }
      .insight-card h3 {
        margin: 12px 0 10px;
        font: 700 28px/1.1 "Iowan Old Style", "Georgia", serif;
      }
      .insight-meta {
        font-size: 13px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--green);
        font-weight: 700;
      }
      .insight-card ul {
        padding-left: 18px;
      }
      .why {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid rgba(18, 32, 44, 0.08);
      }
      .table-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 22px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
      }
      th, td {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(18, 32, 44, 0.08);
        text-align: left;
        vertical-align: top;
      }
      th {
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
      .table-block {
        padding: 20px 22px;
        border-radius: 22px;
        background: rgba(255,255,255,0.76);
        border: 1px solid rgba(18, 32, 44, 0.08);
      }
      @media (max-width: 1180px) {
        .layout {
          grid-template-columns: 1fr;
        }
        .rail {
          position: static;
          min-height: auto;
          border-right: 0;
          border-bottom: 1px solid rgba(18, 32, 44, 0.08);
        }
        .section-grid,
        .table-grid,
        .hero-notes,
        .kpis,
        .insight-card {
          grid-template-columns: 1fr;
        }
        main {
          padding: 26px 18px 70px;
        }
        .hero,
        section,
        #insights,
        #appendix {
          padding: 24px 18px;
        }
        .figure-expand {
          opacity: 1;
          transform: translateY(0);
          top: 24px;
          right: 24px;
        }
        .chart-overlay__dialog {
          width: min(96vw, 1520px);
          margin: 12px auto;
          padding: 18px;
          max-height: calc(100vh - 24px);
        }
        .chart-overlay__header h3 {
          font-size: 28px;
        }
      }
    </style>
  </head>
  <body>
    <div class="layout">
      <aside class="rail">
        <h1>${escapeHtml(reportData.meta.title)}</h1>
        ${reportData.meta.subtitle ? `<p>${escapeHtml(reportData.meta.subtitle)}</p>` : ""}
        <nav>
          ${navItems.map((item) => `<a href="#${escapeHtml(item.id)}">${escapeHtml(item.label)}</a>`).join("")}
        </nav>
      </aside>
      <main>
        <section class="hero" id="top">
          <h2>${escapeHtml(reportData.meta.title)}</h2>
          <p>${escapeHtml(reportData.hero.summary)}</p>
          <div class="kpis">
            ${reportData.kpis
              .map(
                (kpi) => `
                  <div class="kpi">
                    <div class="kpi-value">${escapeHtml(kpi.value)}</div>
                    <div class="kpi-label">${escapeHtml(kpi.label)}</div>
                    <div class="kpi-detail">${escapeHtml(kpi.detail)}</div>
                  </div>
                `,
              )
              .join("")}
          </div>
          <div class="hero-notes">
            <div class="summary-card">
              <h3>Executive view</h3>
              <ul class="highlights">
                ${reportData.hero.executive_bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
              </ul>
            </div>
            <div class="notes-card">
              <h3>Presenter guidance</h3>
              <p>Use the insight section as the slide-ready narrative. Use the earlier sections when you need to defend the numbers behind those talking points.</p>
            </div>
          </div>
        </section>

        ${reportData.sections
          .map(
            (section) => `
              <section id="${escapeHtml(section.id)}">
                <span class="eyebrow">${escapeHtml(section.eyebrow)}</span>
                <h2>${escapeHtml(section.title)}</h2>
                <p>${escapeHtml(section.summary)}</p>
                ${renderHighlights(section.highlights)}
                <div class="section-grid">
                  ${section.figures.map((figure) => renderFigureCard(figure, chartSvgs.get(figure.id))).join("")}
                </div>
              </section>
            `,
          )
          .join("")}

        <section id="insights">
          <span class="eyebrow">Insights</span>
          <h2>Standalone visual stories from the survey analysis</h2>
          <p>Each insight below is designed to stand on its own: one message, one chart, a few numeric proofs, and a short interpretation that can be reused directly.</p>
          <div class="insight-grid">
            ${reportData.insights
              .map(
                (insight) => `
                  <article class="insight-card">
                    <div>
                      <div class="insight-meta">${escapeHtml(insight.scope)}</div>
                      <h3>${escapeHtml(insight.title)}</h3>
                      <p>${escapeHtml(insight.summary)}</p>
                      <ul class="highlights">
                        ${insight.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
                      </ul>
                      <div class="why">
                        <strong>Why this matters</strong>
                        <p>${escapeHtml(insight.why_it_matters)}</p>
                      </div>
                    </div>
                    <div>${renderFigureCard(insight.chart, chartSvgs.get(insight.chart.id))}</div>
                  </article>
                `,
              )
              .join("")}
          </div>
        </section>

        <section id="appendix">
          <span class="eyebrow">Method note and appendix</span>
          <h2>Supporting methods and validation tables</h2>
          <p>The appendix keeps the statistical validation visible without turning the report into a technical memo.</p>
          ${renderHighlights(reportData.appendix.method_notes)}
          <div class="table-grid">
            ${renderTable("Most notable subgroup tests", significantSubgroups, [
              { key: "metric", label: "Metric" },
              { key: "group", label: "Group" },
              { key: "test_type", label: "Test" },
              { key: "p_value", label: "p", render: (row) => row.p_value.toFixed(4) },
              { key: "effect_size", label: "Effect", render: (row) => `${row.effect_size} (${row.effect_size_name})` },
            ])}
            ${renderTable("Regression highlights", regressionHighlights, [
              { key: "model", label: "Model" },
              { key: "term_label", label: "Term" },
              { key: "coef", label: "Coef", render: (row) => row.coef.toFixed(3) },
              { key: "p_value", label: "p", render: (row) => row.p_value.toFixed(4) },
            ])}
          </div>
        </section>
      </main>
    </div>
    <div class="chart-overlay" id="chart-overlay" hidden>
      <div class="chart-overlay__scrim" data-close-overlay="true"></div>
      <div class="chart-overlay__dialog" role="dialog" aria-modal="true" aria-labelledby="chart-overlay-title" aria-describedby="chart-overlay-caption">
        <button class="chart-overlay__close" type="button" aria-label="Close expanded graph" id="chart-overlay-close">&times;</button>
        <div class="chart-overlay__header">
          <span class="eyebrow">Expanded graph</span>
          <h3 id="chart-overlay-title"></h3>
          <p id="chart-overlay-caption"></p>
        </div>
        <div class="chart-overlay__canvas" id="chart-overlay-canvas"></div>
      </div>
    </div>
    <script>
      (() => {
        const overlay = document.getElementById("chart-overlay");
        const overlayCanvas = document.getElementById("chart-overlay-canvas");
        const overlayTitle = document.getElementById("chart-overlay-title");
        const overlayCaption = document.getElementById("chart-overlay-caption");
        const closeButton = document.getElementById("chart-overlay-close");
        let lastTrigger = null;

        const openOverlay = (figure, trigger) => {
          const svg = figure.querySelector("svg");
          if (!svg) return;
          overlayTitle.textContent = figure.dataset.figureTitle || "Expanded graph";
          overlayCaption.textContent = figure.dataset.figureCaption || "";
          overlayCanvas.innerHTML = svg.outerHTML;
          overlay.hidden = false;
          document.body.classList.add("overlay-open");
          lastTrigger = trigger || null;
          closeButton.focus();
        };

        const closeOverlay = () => {
          overlay.hidden = true;
          overlayCanvas.innerHTML = "";
          document.body.classList.remove("overlay-open");
          if (lastTrigger && typeof lastTrigger.focus === "function") {
            lastTrigger.focus();
          }
          lastTrigger = null;
        };

        document.querySelectorAll(".figure-card").forEach((figure) => {
          const expandButton = figure.querySelector(".figure-expand");
          const art = figure.querySelector(".figure-art");
          expandButton?.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            openOverlay(figure, expandButton);
          });
          art?.addEventListener("dblclick", (event) => {
            event.preventDefault();
            openOverlay(figure, art);
          });
          art?.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              openOverlay(figure, art);
            }
          });
        });

        overlay.addEventListener("click", (event) => {
          if (event.target === overlay || event.target.dataset.closeOverlay === "true") {
            closeOverlay();
          }
        });
        closeButton.addEventListener("click", closeOverlay);
        document.addEventListener("keydown", (event) => {
          if (event.key === "Escape" && !overlay.hidden) {
            closeOverlay();
          }
        });
      })();
    </script>
  </body>
</html>`;
}

function rtfEscape(text) {
  return String(text)
    .replace(/\\/g, "\\\\")
    .replace(/{/g, "\\{")
    .replace(/}/g, "\\}")
    .replace(/\n/g, "\\line ");
}

function pngDimensions(buffer) {
  if (buffer.toString("ascii", 1, 4) !== "PNG") {
    throw new Error("Unsupported PNG buffer.");
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

function pngToRtf(pathToPng, widthTwips = 9000) {
  const buffer = fs.readFileSync(pathToPng);
  const { width, height } = pngDimensions(buffer);
  const ratio = height / width;
  const heightTwips = Math.round(widthTwips * ratio);
  const hex = buffer.toString("hex").toUpperCase();
  return `{\\pard\\qc{\\pict\\pngblip\\picw${width}\\pich${height}\\picwgoal${widthTwips}\\pichgoal${heightTwips} ${hex}}\\par}`;
}

function rtfParagraph(text, options = {}) {
  const prefix = options.bold ? "\\b " : "";
  const suffix = options.bold ? "\\b0 " : "";
  const size = options.size || 24;
  const spacing = options.spacingAfter || 160;
  return `{\\pard\\sa${spacing}\\fs${size} ${prefix}${rtfEscape(text)}${suffix}\\par}`;
}

export function renderReportRtf(reportData, pngPaths) {
  const chunks = [];
  chunks.push("{\\rtf1\\ansi\\deff0");
  chunks.push("{\\fonttbl{\\f0 Helvetica;}{\\f1 Georgia;}}");
  chunks.push("{\\colortbl;\\red18\\green32\\blue44;\\red28\\green124\\blue116;\\red95\\green108\\blue119;}");
  chunks.push(rtfParagraph(reportData.meta.title, { bold: true, size: 40, spacingAfter: 220 }));
  chunks.push(rtfParagraph(reportData.hero.summary, { size: 24, spacingAfter: 180 }));
  chunks.push(rtfParagraph("Executive bullets", { bold: true, size: 28, spacingAfter: 120 }));
  reportData.hero.executive_bullets.forEach((item) => {
    chunks.push(rtfParagraph(`- ${item}`, { size: 24, spacingAfter: 80 }));
  });

  for (const section of reportData.sections) {
    chunks.push("\\page");
    chunks.push(rtfParagraph(section.title, { bold: true, size: 34, spacingAfter: 180 }));
    chunks.push(rtfParagraph(section.summary, { size: 24, spacingAfter: 140 }));
    section.highlights.forEach((item) => {
      chunks.push(rtfParagraph(`- ${item}`, { size: 22, spacingAfter: 70 }));
    });
    for (const figure of section.figures) {
      chunks.push(rtfParagraph(figure.title, { bold: true, size: 26, spacingAfter: 120 }));
      chunks.push(rtfParagraph(figure.caption, { size: 20, spacingAfter: 100 }));
      const pngPath = pngPaths.get(figure.id);
      if (pngPath) {
        chunks.push(pngToRtf(pngPath, 9200));
      }
      chunks.push(rtfParagraph("", { size: 8, spacingAfter: 80 }));
    }
  }

  chunks.push("\\page");
  chunks.push(rtfParagraph("Insights", { bold: true, size: 34, spacingAfter: 180 }));
  for (const insight of reportData.insights) {
    chunks.push(rtfParagraph(`[${insight.scope}] ${insight.title}`, { bold: true, size: 28, spacingAfter: 120 }));
    chunks.push(rtfParagraph(insight.summary, { size: 22, spacingAfter: 90 }));
    insight.evidence.forEach((item) => {
      chunks.push(rtfParagraph(`- ${item}`, { size: 22, spacingAfter: 60 }));
    });
    chunks.push(rtfParagraph(`Why this matters: ${insight.why_it_matters}`, { size: 22, spacingAfter: 90 }));
    const pngPath = pngPaths.get(insight.chart.id);
    if (pngPath) {
      chunks.push(pngToRtf(pngPath, 9200));
      chunks.push(rtfParagraph(insight.chart.caption, { size: 20, spacingAfter: 90 }));
    }
  }

  chunks.push("\\page");
  chunks.push(rtfParagraph("Method note and appendix", { bold: true, size: 34, spacingAfter: 160 }));
  reportData.appendix.method_notes.forEach((note) => {
    chunks.push(rtfParagraph(`- ${note}`, { size: 22, spacingAfter: 70 }));
  });
  chunks.push(rtfParagraph("Most notable subgroup tests", { bold: true, size: 28, spacingAfter: 110 }));
  reportData.tables.subgroup_tests
    .filter((row) => row.p_value <= 0.05)
    .slice(0, 10)
    .forEach((row) => {
      chunks.push(
        rtfParagraph(
          `${row.metric} | ${row.group} | ${row.test_type} | p=${row.p_value.toFixed(4)} | ${row.effect_size_name}=${row.effect_size}`,
          { size: 20, spacingAfter: 60 },
        ),
      );
    });
  chunks.push(rtfParagraph("Regression highlights", { bold: true, size: 28, spacingAfter: 110 }));
  reportData.tables.regression_highlights.slice(0, 10).forEach((row) => {
    chunks.push(
      rtfParagraph(
        `${row.model} | ${row.term_label} | coef=${row.coef.toFixed(3)} | p=${row.p_value.toFixed(4)}`,
        { size: 20, spacingAfter: 60 },
      ),
    );
  });
  chunks.push("}");
  return chunks.join("");
}

export function collectFigureSpecs(reportData) {
  const figureMap = new Map();
  for (const section of reportData.sections) {
    for (const figure of section.figures) {
      figureMap.set(figure.id, figure);
    }
  }
  for (const insight of reportData.insights) {
    figureMap.set(insight.chart.id, insight.chart);
  }
  return [...figureMap.values()];
}
