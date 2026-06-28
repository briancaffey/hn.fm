// Tiny HTTP wrapper around `hyperframes render`.
//
// POST /render { project, output, format?, fps?, quality? }
//   project: absolute path to a composition project dir (an index.html lives here)
//   output:  absolute path to write the rendered file
// Both paths live on the shared /outputs volume the pipeline also mounts.
//
// GET /health -> "ok"
//
// Kept dependency-free (Node stdlib only) so the image stays small and portable.
import http from "node:http";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

const PORT = process.env.PORT || 8088;

function render({ project, output, format = "mp4", fps = 30, quality = "standard" }) {
  return new Promise((resolve) => {
    if (!project || !existsSync(project)) {
      return resolve({ ok: false, error: `project not found: ${project}` });
    }
    const args = [
      project,
      "-o", output,
      "--format", String(format),
      "--fps", String(fps),
      "--quality", String(quality),
    ];
    const p = spawn("hf-render", args, { stdio: ["ignore", "pipe", "pipe"] });
    let log = "";
    p.stdout.on("data", (d) => (log += d));
    p.stderr.on("data", (d) => (log += d));
    p.on("close", (code) =>
      resolve({ ok: code === 0 && existsSync(output), code, output, log: log.slice(-3000) }),
    );
    p.on("error", (e) => resolve({ ok: false, error: String(e) }));
  });
}

http
  .createServer((req, res) => {
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200);
      return res.end("ok");
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
