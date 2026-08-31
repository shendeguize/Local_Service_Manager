#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const { mkdtempSync, rmSync } = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const INSTALL_URL = "https://astral.sh/uv/install.sh";

function uvCandidates() {
  const home = os.homedir();
  return [
    process.env.LOCALSM_UV,
    "uv",
    path.join(home, ".local", "bin", "uv"),
    path.join(home, ".cargo", "bin", "uv"),
    path.join(home, ".local", "bin", "uv.exe"),
  ].filter(Boolean);
}

function canRun(command) {
  const result = spawnSync(command, ["--version"], { stdio: "ignore" });
  return !result.error && result.status === 0;
}

function findUv() {
  return uvCandidates().find((candidate) => canRun(candidate)) ?? null;
}

function installUv() {
  if (process.platform === "win32") {
    console.error("LocalSM: installing uv with the official PowerShell installer...");
    const result = spawnSync(
      "powershell",
      [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "irm https://astral.sh/uv/install.ps1 | iex",
      ],
      { stdio: "inherit" },
    );
    if (result.error || result.status !== 0) {
      console.error(`LocalSM: uv installation failed${result.error ? `: ${result.error.message}` : "."}`);
      return null;
    }
    return findUv();
  }

  console.error(`LocalSM: uv not found; installing from ${INSTALL_URL}...`);
  const temporaryDirectory = mkdtempSync(path.join(os.tmpdir(), "localsm-uv-"));
  const installerPath = path.join(temporaryDirectory, "install.sh");
  try {
    const download = spawnSync("curl", ["-LsSf", INSTALL_URL, "-o", installerPath], {
      stdio: "inherit",
    });
    if (download.error || download.status !== 0) {
      console.error(
        `LocalSM: could not download the uv installer${download.error ? `: ${download.error.message}` : "."}`,
      );
      return null;
    }
    const run = spawnSync("sh", [installerPath], { stdio: "inherit" });
    if (run.error || run.status !== 0) {
      console.error(`LocalSM: uv installation failed${run.error ? `: ${run.error.message}` : "."}`);
      return null;
    }
  } finally {
    rmSync(temporaryDirectory, { recursive: true, force: true });
  }

  const uv = findUv();
  if (!uv) {
    console.error("LocalSM: uv installer completed, but the uv executable was not found.");
  }
  return uv;
}

function ensureUv() {
  return findUv() ?? installUv();
}

if (require.main === module) {
  process.exitCode = ensureUv() ? 0 : 1;
}

module.exports = { ensureUv, findUv };
