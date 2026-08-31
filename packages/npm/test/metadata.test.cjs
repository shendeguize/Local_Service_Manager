const assert = require("node:assert/strict");
const { readFile } = require("node:fs/promises");
const test = require("node:test");

const packagePath = require.resolve("../package.json");
const { findUv } = require("../bin/ensure-uv.js");

test("npm wrapper exposes the LocalSM launcher metadata", async () => {
  const packageJson = JSON.parse(await readFile(packagePath, "utf8"));
  assert.equal(packageJson.name, "@shendeguize/local-sm");
  assert.match(packageJson.version, /^\d+\.\d+\.\d+$/);
  assert.equal(packageJson.bin.LocalSM, "bin/local-sm.js");
  assert.ok(packageJson.files.includes("wheel"));
  assert.equal(packageJson.scripts.postinstall, "node bin/ensure-uv.js");
  assert.match(packageJson.scripts.prepublishOnly, /Expected exactly one matching LocalSM wheel/);
});

test("npm installer reuses an existing uv-compatible executable", () => {
  const previous = process.env.LOCALSM_UV;
  process.env.LOCALSM_UV = process.execPath;
  try {
    assert.equal(findUv(), process.execPath);
  } finally {
    if (previous === undefined) {
      delete process.env.LOCALSM_UV;
    } else {
      process.env.LOCALSM_UV = previous;
    }
  }
});
