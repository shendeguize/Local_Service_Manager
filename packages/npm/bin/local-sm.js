#!/usr/bin/env node

const { spawnSync } = require("node:child_process");

const version = require("../package.json").version;

function main() {
  const result = spawnSync(
    "uv",
    ["tool", "run", "--from", `local-sm==${version}`, "LocalSM", ...process.argv.slice(2)],
    { stdio: "inherit" },
  );

  if (result.error && result.error.code === "ENOENT") {
    console.error("LocalSM requires uv. Install it from https://docs.astral.sh/uv/");
    return 127;
  }
  if (result.error) {
    console.error(`LocalSM could not start uv: ${result.error.message}`);
    return 1;
  }
  return result.status ?? 1;
}

process.exitCode = main();
