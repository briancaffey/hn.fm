// Tiny HTTP wrapper around the `hyperframes` CLI and a headless browser.
//
// POST /render { project, output, format?, fps?, quality? }
// POST /check  { project }                 lint + runtime + layout, as JSON
// POST /frames { project, at: [seconds], output }   PNG stills of the timeline
// POST /card   { html, output, width?, height? }   HTML string -> PNG still
//   project: absolute path to a composition project dir (an index.html lives here)
//   output:  absolute path to write the rendered file
// Both paths live on the shared /outputs volume the pipeline also mounts.
//
// POST /shot { url, output, width?, height?, timeout? }
//   url:    an http(s) page to photograph
//   output: absolute path to write the PNG, on the same shared volume
//
// GET /health -> "ok"
//
// Kept dependency-free (Node stdlib only) so the image stays small and portable.
import http from "node:http";
import { spawn } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";

// The workers run as another user and read what is written here.
process.umask(0o002);

const PORT = process.env.PORT || 8088;

// One container, and every screenshot is two chromium launches. Six requests
// arriving together meant twelve browsers competing for the same CPU and
// memory, and three of them fell over — pages that render fine when asked one
// at a time. A gate rather than a bigger container: the work is a background
// nicety, so queueing is the right answer to a burst.
const MAX_BROWSERS = Number(process.env.SHOT_CONCURRENCY || 2);
let running = 0;
const waiting = [];

function acquire() {
  if (running < MAX_BROWSERS) {
    running += 1;
    return Promise.resolve();
  }
  return new Promise((resolve) => waiting.push(resolve));
}

function release() {
  const next = waiting.shift();
  if (next) return next();
  running -= 1;
}

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";

// This service photographs URLs submitted by strangers on the internet, from
// inside the private network, so it has to refuse to point the browser at the
// network it is standing in. http(s) only — `file://` would read this
// container's disk — and no address that resolves to somewhere local.
const PRIVATE_HOST = new RegExp(
  [
    "^localhost$", "^127\\.", "^0\\.", "^10\\.",
    "^192\\.168\\.", "^169\\.254\\.",
    "^172\\.(1[6-9]|2[0-9]|3[01])\\.",
    "^\\[?::1\\]?$", "^\\[?f[cd]", "\\.local$", "\\.internal$",
  ].join("|"),
  "i",
);

function refuse(rawUrl) {
  let u;
  try {
    u = new URL(rawUrl);
  } catch {
    return "not a URL";
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    return `refusing ${u.protocol} — http(s) only`;
  }
  if (PRIVATE_HOST.test(u.hostname)) {
    return `refusing a private address: ${u.hostname}`;
  }
  return null;
}

// One page load, three answers: what the page says it is, whether we were
// shown the page at all, and the picture. The CLI needed two chromium
// launches to get the first two, which doubled the time and meant a burst of
// requests ran twice as many browsers as it looked like.
import puppeteer from "puppeteer-core";

// Interstitials this browser is shown instead of the page. Photographing one
// and filing it as the article is worse than having no picture: the card then
// confidently shows the wrong thing.
const BLOCKED = /just a moment|attention required|you have been blocked|access denied|are you a robot|verify you are human|enable javascript and cookies|^403 |forbidden|bot verification|unusual traffic/i;

// Consent overlays, hidden for the photograph.
//
// Hiding is not accepting: nothing is clicked and no consent is given or
// recorded — the banner is simply not in the picture, which is also the
// privacy-preserving outcome, since dismissing one by clicking "accept" is
// the only alternative that makes it go away. Named vendor containers plus
// two conservative attribute matches; deliberately not `[class*=cookie]`,
// which would hide an article about cookies.
const HIDE_CONSENT = `
  #onetrust-consent-sdk, #onetrust-banner-sdk, .onetrust-pc-dark-filter,
  #CybotCookiebotDialog, #CybotCookiebotDialogBodyUnderlay,
  #usercentrics-root, #cmpbox, #cmpbox2, #didomi-host, #qc-cmp2-container,
  #gdpr-consent-tool-wrapper, .cc-window, .cookie-consent-banner,
  .truste_overlay, .truste_box_overlay, #truste-consent-track,
  [id^="sp_message_container"], [class*="CookieBanner"],
  [aria-label="Cookie banner" i], [aria-label="Consent" i] {
    display: none !important;
  }
  /* Banners routinely lock scrolling, which leaves the page frozen mid-fade. */
  html, body { overflow: auto !important; position: static !important; }
`;

async function shot({ url, output, width = 1200, height = 750, timeout = 25 }) {
  const bad = refuse(url);
  if (bad) return { ok: false, error: bad };
  if (!output) return { ok: false, error: "output required" };

  await acquire();
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
      args: [
        "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
        "--hide-scrollbars", "--no-first-run", "--disable-extensions",
      ],
      headless: true,
    });
    const page = await browser.newPage();
    await page.setUserAgent(UA);
    await page.setExtraHTTPHeaders({ "accept-language": "en-US,en;q=0.9" });
    await page.setViewport({ width: Number(width), height: Number(height) });

    // `domcontentloaded` rather than `networkidle`: a news site with a live
    // ticker never goes idle, and waiting for it is how a capture times out
    // on a page that was ready in two seconds.
    await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: Number(timeout) * 1000,
    });

    const title = ((await page.title()) || "").trim().slice(0, 200);
    if (BLOCKED.test(title)) {
      return { ok: false, error: `blocked: ${title}`, title };
    }

    await page.addStyleTag({ content: HIDE_CONSENT });
    // A beat for lazy images and the fade-ins that most pages open with.
    await new Promise((r) => setTimeout(r, 1800));

    mkdirSync(dirname(output), { recursive: true });
    await page.screenshot({ path: output, type: "png" });
    return { ok: existsSync(output), output, title };
  } catch (e) {
    return { ok: false, error: String(e).slice(0, 300) };
  } finally {
    if (browser) await browser.close().catch(() => {});
    release();
  }
}

// A still from HTML we wrote ourselves: the title card (plans/19). No URL is
// involved — the document arrives in the request body and is handed to the
// page with setContent — so the private-address rule above does not apply,
// and nothing on the network is fetched except the Google Fonts the markup
// asks for. Waits for those fonts, since a screenshot taken a beat early is
// the wordmark in a fallback face.
async function card({ html, output, width = 1280, height = 720, timeout = 25 }) {
  if (!html) return { ok: false, error: "html required" };
  if (!output) return { ok: false, error: "output required" };

  await acquire();
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
      args: [
        "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
        "--hide-scrollbars", "--no-first-run", "--disable-extensions",
      ],
      headless: true,
    });
    const page = await browser.newPage();
    await page.setViewport({ width: Number(width), height: Number(height), deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: "load", timeout: Number(timeout) * 1000 });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await new Promise((r) => setTimeout(r, 300));
    mkdirSync(dirname(output), { recursive: true });
    await page.screenshot({ path: output, type: "png" });
    return { ok: existsSync(output), output };
  } catch (e) {
    return { ok: false, error: String(e).slice(0, 300) };
  } finally {
    if (browser) await browser.close().catch(() => {});
    release();
  }
}

// The CLI, run to completion. Renders are serialised with the same gate as
// the screenshots: each one is a browser, and two full renders at once on
// this container's memory is how both die.
function cli(args, { timeout = 900 } = {}) {
  return new Promise((resolve) => {
    const p = spawn("hyperframes", args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    const timer = setTimeout(() => p.kill("SIGKILL"), timeout * 1000);
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("close", (code) => {
      clearTimeout(timer);
      resolve({ code, out, err });
    });
    p.on("error", (e) => {
      clearTimeout(timer);
      resolve({ code: -1, out, err: String(e) });
    });
  });
}

async function render({ project, output, format = "mp4", fps = 30, quality = "standard", timeout = 1500 }) {
  if (!project || !existsSync(project)) return { ok: false, error: `project not found: ${project}` };
  if (!output) return { ok: false, error: "output required" };
  await acquire();
  try {
    mkdirSync(dirname(output), { recursive: true });
    const started = Date.now();
    const r = await cli(
      [
        "render", project, "-o", output,
        "--format", String(format), "--fps", String(fps), "--quality", String(quality),
      ],
      { timeout: Number(timeout) },
    );
    // The trace lines are for a person watching a terminal; the tail of what
    // is left says what went wrong.
    const log = (r.out + r.err)
      .split("\n")
      .filter((l) => !l.includes("[Render:trace]") && !l.startsWith("@hf-progress") && !l.includes("█"))
      .join("\n")
      .slice(-3000);
    return {
      ok: r.code === 0 && existsSync(output), code: r.code, output,
      seconds: Math.round((Date.now() - started) / 100) / 10, log,
    };
  } finally {
    release();
  }
}

// The CLI prints its JSON report after a few lines of its own; the report is
// the last top-level object on stdout.
function lastJson(text) {
  const at = text.lastIndexOf("\n{");
  const start = at >= 0 ? at + 1 : text.indexOf("{");
  if (start < 0) return null;
  try {
    return JSON.parse(text.slice(start));
  } catch {
    return null;
  }
}

async function check({ project, lintOnly = false }) {
  if (!project || !existsSync(project)) return { ok: false, error: `project not found: ${project}` };
  if (lintOnly) {
    const r = await cli(["lint", project, "--json"], { timeout: 120 });
    const report = lastJson(r.out);
    return report ? { ok: true, report } : { ok: false, error: (r.err || r.out).slice(-1500) };
  }
  await acquire();
  try {
    const r = await cli(["check", project, "--json"], { timeout: 600 });
    const report = lastJson(r.out);
    return report ? { ok: true, report } : { ok: false, error: (r.err || r.out).slice(-1500) };
  } finally {
    release();
  }
}

async function frames({ project, at = [], output }) {
  if (!project || !existsSync(project)) return { ok: false, error: `project not found: ${project}` };
  if (!output) return { ok: false, error: "output required" };
  await acquire();
  try {
    mkdirSync(output, { recursive: true });
    const args = ["snapshot", project, "-o", output, "--no-end", "--describe", "false"];
    if (at.length) args.push("--at", at.map((t) => Number(t).toFixed(2)).join(","));
    const r = await cli(args, { timeout: 600 });
    // The CLI writes its frames readable by their owner only, and the
    // worker that asked for them is somebody else.
    try {
      chmodSync(output, 0o2775);
      for (const name of readdirSync(output)) chmodSync(join(output, name), 0o664);
    } catch (e) {
      console.error("frames: could not open up", output, String(e));
    }
    return { ok: r.code === 0, code: r.code, output, log: (r.out + r.err).slice(-1500) };
  } finally {
    release();
  }
}

function route(req, res, fn) {
  let data = "";
  req.on("data", (c) => (data += c));
  req.on("end", async () => {
    try {
      const result = await fn(JSON.parse(data));
      res.writeHead(result.ok ? 200 : 500, { "content-type": "application/json" });
      res.end(JSON.stringify(result));
    } catch (e) {
      res.writeHead(400, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: false, error: String(e) }));
    }
  });
}

http
  .createServer((req, res) => {
    if (req.method === "POST" && req.url === "/check") return route(req, res, check);
    if (req.method === "POST" && req.url === "/frames") return route(req, res, frames);
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200);
      return res.end("ok");
    }
    if (req.method === "POST" && req.url === "/shot") {
      let data = "";
      req.on("data", (c) => (data += c));
      req.on("end", async () => {
        try {
          const result = await shot(JSON.parse(data));
          res.writeHead(result.ok ? 200 : 500, { "content-type": "application/json" });
          res.end(JSON.stringify(result));
        } catch (e) {
          res.writeHead(400, { "content-type": "application/json" });
          res.end(JSON.stringify({ ok: false, error: String(e) }));
        }
      });
      return;
    }
    if (req.method === "POST" && req.url === "/card") {
      let data = "";
      req.on("data", (c) => (data += c));
      req.on("end", async () => {
        try {
          const result = await card(JSON.parse(data));
          res.writeHead(result.ok ? 200 : 500, { "content-type": "application/json" });
          res.end(JSON.stringify(result));
        } catch (e) {
          res.writeHead(400, { "content-type": "application/json" });
          res.end(JSON.stringify({ ok: false, error: String(e) }));
        }
      });
      return;
    }
    if (req.method === "POST" && req.url === "/render") {
      let data = "";
      req.on("data", (c) => (data += c));
      req.on("end", async () => {
        try {
          const result = await render(JSON.parse(data));
          res.writeHead(result.ok ? 200 : 500, { "content-type": "application/json" });
          res.end(JSON.stringify(result));
        } catch (e) {
          res.writeHead(400, { "content-type": "application/json" });
          res.end(JSON.stringify({ ok: false, error: String(e) }));
        }
      });
      return;
    }
    res.writeHead(404);
    res.end("not found");
  })
  .listen(PORT, () => console.log(`hyperframes render server on :${PORT}`));
