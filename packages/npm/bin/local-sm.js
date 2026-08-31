#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const { existsSync, readdirSync } = require("node:fs");
const path = require("node:path");

const version = require("../package.json").version;

function findWheel() {
  const wheelDirectory = path.resolve(__dirname, "..", "wheel");
  const prefix = `local_sm-${version}-`;
  const wheels = existsSync(wheelDirectory)
    ? readdirSync(wheelDirectory).filter(
        (name) => name.startsWith(prefix) && name.endsWith(".whl"),
      )
    : [];

  if (wheels.length !== 1) {
    throw new Error(
      `LocalSM package is missing its ${version} Python wheel. ` +
        "Please reinstall the package or report a broken npm release.",
    );
  }
  return path.join(wheelDirectory, wheels[0]);
}

function main() {
  let wheel;
  try {
    wheel = findWheel();
  } catch (error) {
    console.error(error.message);
    return 1;
  }

  const result = spawnSync(
    "uv",
    ["tool", "run", "--from", wheel, "LocalSM", ...process.argv.slice(2)],
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
