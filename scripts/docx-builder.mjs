import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

function xmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function pngDimensions(buffer) {
  if (buffer.toString("ascii", 1, 4) !== "PNG") {
    throw new Error("Expected a PNG buffer.");
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

function toEmu(px) {
  return Math.round(px * 9525);
}

function twipsToEmu(twips) {
  return Math.round(twips * 635);
}

function textRun(text, { bold = false, italic = false, color = "", size = 24 } = {}) {
  const props = [];
  if (bold) props.push("<w:b/>");
  if (italic) props.push("<w:i/>");
  if (color) props.push(`<w:color w:val="${color}"/>`);
  if (size) props.push(`<w:sz w:val="${size}"/><w:szCs w:val="${size}"/>`);
  const space = /^\s|\s$/.test(text) ? ' xml:space="preserve"' : "";
  return `<w:r><w:rPr>${props.join("")}</w:rPr><w:t${space}>${xmlEscape(text)}</w:t></w:r>`;
}

function paragraph(text, options = {}) {
  const style = options.style || "Normal";
  const spacingAfter = options.spacingAfter ?? 120;
  const spacingBefore = options.spacingBefore ?? 0;
  return `
    <w:p>
      <w:pPr>
        <w:pStyle w:val="${style}"/>
        <w:spacing w:before="${spacingBefore}" w:after="${spacingAfter}"/>
      </w:pPr>
      ${textRun(text, options)}
    </w:p>
  `;
}

function multiRunParagraph(runs, options = {}) {
  const style = options.style || "Normal";
  const spacingAfter = options.spacingAfter ?? 120;
  return `
    <w:p>
      <w:pPr>
        <w:pStyle w:val="${style}"/>
        <w:spacing w:after="${spacingAfter}"/>
      </w:pPr>
      ${runs.join("")}
    </w:p>
  `;
}

function pageBreak() {
  return `<w:p><w:r><w:br w:type="page"/></w:r></w:p>`;
}

function imageParagraph(imageInfo, relationshipId, docPrId) {
  const buffer = fs.readFileSync(imageInfo.path);
  const { width, height } = pngDimensions(buffer);
  const pageWidthTwips = 11_906;
  const pageMarginTwips = 1_080;
  const safeInsetTwips = 1_440;
  const maxWidthEmu = twipsToEmu(pageWidthTwips - pageMarginTwips * 2 - safeInsetTwips);
  let cx = toEmu(width);
  let cy = toEmu(height);
  if (cx > maxWidthEmu) {
    const scale = maxWidthEmu / cx;
    cx = Math.round(cx * scale);
    cy = Math.round(cy * scale);
  }
  return `
    <w:p>
      <w:pPr>
        <w:jc w:val="center"/>
        <w:spacing w:after="160"/>
      </w:pPr>
      <w:r>
        <w:drawing>
          <wp:inline distT="0" distB="0" distL="0" distR="0"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
            <wp:extent cx="${cx}" cy="${cy}"/>
            <wp:docPr id="${docPrId}" name="${xmlEscape(imageInfo.name)}"/>
            <wp:cNvGraphicFramePr>
              <a:graphicFrameLocks noChangeAspect="1"
                xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>
            </wp:cNvGraphicFramePr>
            <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:nvPicPr>
                    <pic:cNvPr id="${docPrId}" name="${xmlEscape(imageInfo.name)}"/>
                    <pic:cNvPicPr/>
                  </pic:nvPicPr>
                  <pic:blipFill>
                    <a:blip r:embed="${relationshipId}"/>
                    <a:stretch><a:fillRect/></a:stretch>
                  </pic:blipFill>
                  <pic:spPr>
                    <a:xfrm>
                      <a:off x="0" y="0"/>
                      <a:ext cx="${cx}" cy="${cy}"/>
                    </a:xfrm>
                    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                  </pic:spPr>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  `;
}

function stylesXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:color w:val="12202C"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="34"/>
      <w:szCs w:val="34"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="30"/>
      <w:szCs w:val="30"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="26"/>
      <w:szCs w:val="26"/>
    </w:rPr>
  </w:style>
</w:styles>`;
}

function contentTypesXml(imageCount) {
  const overrides = [
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>',
    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
    '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
  ];
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  ${imageCount ? '<Default Extension="png" ContentType="image/png"/>' : ""}
  ${overrides.join("")}
</Types>`;
}

function rootRelsXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`;
}

function appPropsXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>`;
}

function corePropsXml(title) {
  const now = new Date().toISOString();
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:dcmitype="http://purl.org/dc/dcmitype/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>${xmlEscape(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">${now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">${now}</dcterms:modified>
</cp:coreProperties>`;
}

function documentRelsXml(imageInfos) {
  const imageRelationships = imageInfos
    .map(
      (image, index) =>
        `<Relationship Id="rId${index + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/${xmlEscape(image.name)}"/>`,
    )
    .join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  ${imageRelationships}
</Relationships>`;
}

function buildDocumentXml(reportData, imageInfos, imageRelMap) {
  const body = [];
  body.push(paragraph(reportData.meta.title, { style: "Title", bold: true, size: 34, spacingAfter: 200 }));
  body.push(paragraph(reportData.hero.summary, { size: 22, spacingAfter: 160 }));
  body.push(paragraph("Executive bullets", { style: "Heading2", bold: true, size: 26, spacingAfter: 100 }));
  reportData.hero.executive_bullets.forEach((item) => {
    body.push(paragraph(`- ${item}`, { size: 22, spacingAfter: 60 }));
  });

  let docPrId = 1;
  for (const section of reportData.sections) {
    body.push(pageBreak());
    body.push(paragraph(section.title, { style: "Heading1", bold: true, size: 30, spacingAfter: 140 }));
    body.push(paragraph(section.summary, { size: 22, spacingAfter: 110 }));
    section.highlights.forEach((item) => {
      body.push(paragraph(`- ${item}`, { size: 21, spacingAfter: 50 }));
    });
    for (const figure of section.figures) {
      body.push(paragraph(figure.title, { style: "Heading2", bold: true, size: 24, spacingAfter: 90 }));
      body.push(paragraph(figure.caption, { size: 20, spacingAfter: 90 }));
      const imageInfo = imageInfos.find((item) => item.id === figure.id);
      if (imageInfo) {
        body.push(imageParagraph(imageInfo, imageRelMap.get(imageInfo.id), docPrId));
        docPrId += 1;
      }
    }
  }

  body.push(pageBreak());
  body.push(paragraph("Insights", { style: "Heading1", bold: true, size: 30, spacingAfter: 140 }));
  reportData.insights.forEach((insight) => {
    body.push(
      multiRunParagraph(
        [
          textRun(`[${insight.scope}] `, { bold: true, color: "1C7C74", size: 20 }),
          textRun(insight.title, { bold: true, size: 24 }),
        ],
        { spacingAfter: 90 },
      ),
    );
    body.push(paragraph(insight.summary, { size: 21, spacingAfter: 80 }));
    insight.evidence.forEach((item) => {
      body.push(paragraph(`- ${item}`, { size: 20, spacingAfter: 50 }));
    });
    body.push(paragraph(`Why this matters: ${insight.why_it_matters}`, { italic: true, size: 20, spacingAfter: 80 }));
    const imageInfo = imageInfos.find((item) => item.id === insight.chart.id);
    if (imageInfo) {
      body.push(imageParagraph(imageInfo, imageRelMap.get(imageInfo.id), docPrId));
      docPrId += 1;
      body.push(paragraph(insight.chart.caption, { size: 19, spacingAfter: 90 }));
    }
  });

  body.push(pageBreak());
  body.push(paragraph("Method note and appendix", { style: "Heading1", bold: true, size: 30, spacingAfter: 140 }));
  reportData.appendix.method_notes.forEach((note) => {
    body.push(paragraph(`- ${note}`, { size: 20, spacingAfter: 50 }));
  });
  body.push(paragraph("Most notable subgroup tests", { style: "Heading2", bold: true, size: 24, spacingAfter: 90 }));
  reportData.tables.subgroup_tests
    .filter((row) => row.p_value <= 0.05)
    .slice(0, 10)
    .forEach((row) => {
      body.push(
        paragraph(
          `${row.metric} | ${row.group} | ${row.test_type} | p=${row.p_value.toFixed(4)} | ${row.effect_size_name}=${row.effect_size}`,
          { size: 19, spacingAfter: 40 },
        ),
      );
    });
  body.push(paragraph("Regression highlights", { style: "Heading2", bold: true, size: 24, spacingAfter: 90 }));
  reportData.tables.regression_highlights.slice(0, 10).forEach((row) => {
    body.push(
      paragraph(
        `${row.model} | ${row.term_label} | coef=${row.coef.toFixed(3)} | p=${row.p_value.toFixed(4)}`,
        { size: 19, spacingAfter: 40 },
      ),
    );
  });

  body.push(`
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  `);

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
  xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
  xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
  xmlns:o="urn:schemas-microsoft-com:office:office"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
  xmlns:v="urn:schemas-microsoft-com:vml"
  xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:w10="urn:schemas-microsoft-com:office:word"
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
  xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
  xmlns:wne="http://schemas.microsoft.com/office/2006/wordml"
  xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
  mc:Ignorable="w14 wp14">
  <w:body>
    ${body.join("")}
  </w:body>
</w:document>`;
}

function runZip(outputPath, zipRoot) {
  if (fs.existsSync(outputPath)) {
    fs.rmSync(outputPath);
  }
  const result = spawnSync("zip", ["-qr", outputPath, "[Content_Types].xml", "_rels", "docProps", "word"], {
    cwd: zipRoot,
    stdio: "pipe",
    encoding: "utf-8",
  });
  if (result.status !== 0) {
    throw new Error(`zip failed.\n${[result.stdout, result.stderr].filter(Boolean).join("\n")}`);
  }
}

export function buildDocx(reportData, pngMap, outputPath, tempRoot) {
  const buildDir = path.join(tempRoot, "docx-build");
  fs.rmSync(buildDir, { recursive: true, force: true });
  fs.mkdirSync(path.join(buildDir, "_rels"), { recursive: true });
  fs.mkdirSync(path.join(buildDir, "docProps"), { recursive: true });
  fs.mkdirSync(path.join(buildDir, "word", "_rels"), { recursive: true });
  fs.mkdirSync(path.join(buildDir, "word", "media"), { recursive: true });

  const imageInfos = [];
  let imageIndex = 1;
  for (const [id, sourcePath] of pngMap.entries()) {
    const name = `image${imageIndex}.png`;
    fs.copyFileSync(sourcePath, path.join(buildDir, "word", "media", name));
    imageInfos.push({ id, path: sourcePath, name });
    imageIndex += 1;
  }

  const imageRelMap = new Map();
  imageInfos.forEach((image, index) => {
    imageRelMap.set(image.id, `rId${index + 2}`);
  });

  fs.writeFileSync(path.join(buildDir, "[Content_Types].xml"), contentTypesXml(imageInfos.length), "utf-8");
  fs.writeFileSync(path.join(buildDir, "_rels", ".rels"), rootRelsXml(), "utf-8");
  fs.writeFileSync(path.join(buildDir, "docProps", "app.xml"), appPropsXml(), "utf-8");
  fs.writeFileSync(path.join(buildDir, "docProps", "core.xml"), corePropsXml(reportData.meta.title), "utf-8");
  fs.writeFileSync(path.join(buildDir, "word", "styles.xml"), stylesXml(), "utf-8");
  fs.writeFileSync(
    path.join(buildDir, "word", "_rels", "document.xml.rels"),
    documentRelsXml(imageInfos),
    "utf-8",
  );
  fs.writeFileSync(
    path.join(buildDir, "word", "document.xml"),
    buildDocumentXml(reportData, imageInfos, imageRelMap),
    "utf-8",
  );

  runZip(outputPath, buildDir);
  fs.rmSync(buildDir, { recursive: true, force: true });
}
