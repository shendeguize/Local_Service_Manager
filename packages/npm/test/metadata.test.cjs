const assert = require("node:assert/strict");
const { readFile } = require("node:fs/promises");
const test = require("node:test");

const packagePath = require.resolve("../package.json");

test("npm wrapper exposes the LocalSM launcher metadata", async () => {
  const packageJson = JSON.parse(await readFile(packagePath, "utf8"));
  assert.equal(packageJson.name, "@shendeguize/local-sm");
  assert.match(packageJson.version, /^\d+\.\d+\.\d+$/);
  assert.equal(packageJson.bin.LocalSM, "bin/local-sm.js");
  assert.ok(packageJson.files.includes("wheel"));
  assert.match(packageJson.scripts.prepublishOnly, /Expected exactly one matching LocalSM wheel/);
});
