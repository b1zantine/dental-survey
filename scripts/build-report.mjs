import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

import {
  collectFigureSpecs,
  renderChartSvg,
  renderReportHtml,
} from "./report-renderer.mjs";
import { buildDocx } from "./docx-builder.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");
const CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const CHROME_SCALE_FACTOR = 2;
const CHROME_VERTICAL_BUFFER = 160;

function ensureDir(target) {
  fs.mkdirSync(target, { recursive: true });
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    stdio: "pipe",
    encoding: "utf-8",
    ...options,
  });
  if (result.status !== 0) {
    const output = [result.stdout, result.stderr].filter(Boolean).join("\n");
    throw new Error(`${command} ${args.join(" ")} failed.\n${output}`);
  }
  return result;
}

function chromeScreenshot(svgPath, outputPath, { width, height, profileDir }) {
  const tempOutputPath = `${outputPath}.raw.png`;
  const windowHeight = height + CHROME_VERTICAL_BUFFER;
  const result = spawnSync(
    CHROME_BIN,
    [
      "--headless",
      "--disable-gpu",
      "--hide-scrollbars",
      "--no-first-run",
      "--disable-crash-reporter",
      "--disable-breakpad",
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-default-apps",
      "--disable-sync",
      "--metrics-recording-only",
      "--run-all-compositor-stages-before-draw",
      `--force-device-scale-factor=${CHROME_SCALE_FACTOR}`,
      `--user-data-dir=${profileDir}`,
      `--window-size=${width},${windowHeight}`,
      `--screenshot=${tempOutputPath}`,
      `file://${svgPath}`,
    ],
    {
      cwd: ROOT,
      stdio: "pipe",
      encoding: "utf-8",
      timeout: 8000,
    },
  );

  if (fs.existsSync(tempOutputPath) && fs.statSync(tempOutputPath).size > 0) {
    cropChromeScreenshot(tempOutputPath, outputPath, width * CHROME_SCALE_FACTOR, height * CHROME_SCALE_FACTOR);
    fs.rmSync(tempOutputPath, { force: true });
    return;
  }

  const output = [result.stdout, result.stderr].filter(Boolean).join("\n");
  if (result.error) {
    throw new Error(`Chrome screenshot failed for ${svgPath}.\n${result.error.message}\n${output}`);
  }
  throw new Error(`Chrome screenshot failed for ${svgPath}.\n${output}`);
}

function cropChromeScreenshot(sourcePath, outputPath, widthPx, heightPx) {
  const cropScript = `
from pathlib import Path
from PIL import Image

source = Path(${JSON.stringify(sourcePath)})
target = Path(${JSON.stringify(outputPath)})
width = ${widthPx}
height = ${heightPx}

image = Image.open(source)
if image.width < width or image.height < height:
    raise SystemExit(f"Screenshot too small for crop: {image.size}, expected at least {(width, height)}")

cropped = image.crop((0, 0, width, height))
cropped.save(target, dpi=image.info.get("dpi", (144, 144)))
`;
  run(resolvePython(), ["-c", cropScript]);
}

function resolvePython() {
  const venvPython = path.join(ROOT, ".venv", "bin", "python");
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return "python3";
}

function buildDataLayer(paths) {
  run(resolvePython(), [
    path.join("analysis", "build_bangalore_report_data.py"),
    "--input",
    "periodontal_survey_mar_8_cutoff_plus_generated.csv",
    "--out-json",
    paths.reportJson,
    "--out-mapping",
    paths.mappingCsv,
    "--out-analysis",
    paths.analysisCsv,
  ]);
}

function buildCharts(reportData, svgDir) {
  ensureDir(svgDir);
  const chartSvgs = new Map();
  const figureSpecs = collectFigureSpecs(reportData);
  for (const figure of figureSpecs) {
    const svgMarkup = renderChartSvg(figure);
    const svgPath = path.join(svgDir, `${figure.id}.svg`);
    fs.writeFileSync(svgPath, svgMarkup, "utf-8");
    chartSvgs.set(figure.id, svgMarkup);
  }
  return chartSvgs;
}

function svgDimensions(svgPath) {
  const svg = fs.readFileSync(svgPath, "utf-8");
  const widthMatch = svg.match(/\bwidth="([0-9.]+)"/i);
  const heightMatch = svg.match(/\bheight="([0-9.]+)"/i);
  if (!widthMatch || !heightMatch) {
    throw new Error(`Could not parse SVG dimensions for ${svgPath}`);
  }
  return {
    width: Math.ceil(Number(widthMatch[1])),
    height: Math.ceil(Number(heightMatch[1])),
  };
}

function renderChromePngs(svgDir, pngDir, tempDir) {
  ensureDir(pngDir);
  ensureDir(tempDir);
  if (!fs.existsSync(CHROME_BIN)) {
    throw new Error(`Chrome binary not found at ${CHROME_BIN}`);
  }

  const svgFiles = fs
    .readdirSync(svgDir)
    .filter((file) => file.endsWith(".svg"))
    .map((file) => path.join(svgDir, file));

  if (!svgFiles.length) {
    throw new Error("No SVG charts were generated.");
  }

  for (const svgPath of svgFiles) {
    const profileDir = fs.mkdtempSync(path.join(tempDir, "chrome-profile-"));
    const wrapperPath = path.join(tempDir, `${path.basename(svgPath, ".svg")}.wrapper.html`);
    try {
      writeSvgWrapper(svgPath, wrapperPath);
      const { width, height } = svgDimensions(svgPath);
      const outputPath = path.join(pngDir, `${path.basename(svgPath, ".svg")}.png`);
      chromeScreenshot(wrapperPath, outputPath, { width, height, profileDir });
    } finally {
      fs.rmSync(wrapperPath, { force: true });
      fs.rmSync(profileDir, { recursive: true, force: true });
    }
  }
}

function writeSvgWrapper(svgPath, wrapperPath) {
  const svg = fs.readFileSync(svgPath, "utf-8");
  const { width, height } = svgDimensions(svgPath);
  const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      html, body {
        margin: 0;
        padding: 0;
        width: ${width}px;
        height: ${height}px;
        overflow: hidden;
        background: #ffffff;
      }
      svg {
        display: block;
        width: ${width}px;
        height: ${height}px;
      }
    </style>
  </head>
  <body>${svg}</body>
</html>`;
  fs.writeFileSync(wrapperPath, html, "utf-8");
}

function buildDocxBundle(reportData, pngDir, docsDir, tempDir) {
  const pngPaths = new Map();
  for (const file of fs.readdirSync(pngDir).filter((entry) => entry.endsWith(".png"))) {
    const id = file.replace(/\.png$/, "");
    pngPaths.set(id, path.join(pngDir, file));
  }
  const docxPath = path.join(docsDir, "periodontal-survey-report.docx");
  buildDocx(reportData, pngPaths, docxPath, tempDir);
  return docxPath;
}

function main() {
  const docsDir = path.join(ROOT, "docs");
  const assetsDir = path.join(docsDir, "assets");
  const dataDir = path.join(assetsDir, "data");
  const chartsDir = path.join(assetsDir, "charts");
  const svgDir = path.join(chartsDir, "svg");
  const pngDir = path.join(chartsDir, "png");
  const tempDir = path.join(assetsDir, "tmp");

  [svgDir, pngDir, tempDir].forEach((target) => fs.rmSync(target, { recursive: true, force: true }));
  [docsDir, assetsDir, dataDir, chartsDir, svgDir, pngDir, tempDir].forEach(ensureDir);

  const paths = {
    reportJson: path.join(dataDir, "report-data.json"),
    mappingCsv: path.join(dataDir, "locality-mapping-review.csv"),
    analysisCsv: path.join(dataDir, "analysis-ready.csv"),
  };

  buildDataLayer(paths);
  const reportData = JSON.parse(fs.readFileSync(paths.reportJson, "utf-8"));
  const chartSvgs = buildCharts(reportData, svgDir);

  renderChromePngs(svgDir, pngDir, tempDir);

  const htmlPath = path.join(docsDir, "periodontal-survey-report.html");
  fs.writeFileSync(htmlPath, renderReportHtml(reportData, chartSvgs), "utf-8");

  const docxPath = buildDocxBundle(reportData, pngDir, docsDir, tempDir);

  process.stdout.write(
    [
      `html: ${htmlPath}`,
      `docx: ${docxPath}`,
      `data: ${paths.reportJson}`,
      `svg_dir: ${svgDir}`,
      `png_dir: ${pngDir}`,
    ].join("\n"),
  );
}

main();
