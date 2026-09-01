/**
 * The demo's state machine is what a visitor forms their impression of LocalSM
 * from, so its transitions are tested rather than eyeballed in a browser.
 *
 * The mock fetches its fixtures at import time, which in a browser is an HTTP
 * request for the file next to it. Here that request is served from disk.
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test, { before, describe } from "node:test";
import { fileURLToPath } from "node:url";

const FIXTURES = new URL("../public/demo/fixtures.json", import.meta.url);

let api;

before(async () => {
  globalThis.LOCALSM_DEMO_INSTANT = true;
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => JSON.parse(await readFile(fileURLToPath(FIXTURES), "utf8")),
  });
  ({ api } = await import("./mock-api.js"));
});

const find = (rows, name) => rows.find((row) => row.name === name);

describe("services", () => {
  test("opens on the scenario's running services", async () => {
    const services = await api.services();
    assert.equal(find(services, "web").state, "running");
    assert.equal(find(services, "docs").state, "running");
    assert.equal(find(services, "api").state, "stopped");
  });

  test("starting a service assigns its preferred port and a URL from the log", async () => {
    const started = await api.serviceAction("api", "up");
    assert.equal(started.state, "running");
    assert.equal(started.port, 8080);
    assert.equal(started.url, "http://127.0.0.1:8080/");
    assert.match(started.log, /8080/);
    assert.equal(started.managed_by, "detached");
    const logs = await api.logs("api");
    assert.equal(logs.content, started.log);
  });

  test("stopping releases the pid but remembers the port for the next start", async () => {
    const stopped = await api.serviceAction("api", "down");
    assert.equal(stopped.state, "stopped");
    assert.equal(stopped.pid, null);
    const restarted = await api.serviceAction("api", "up");
    assert.equal(restarted.port, 8080);
    await api.serviceAction("api", "down");
  });

  test("a launchd-managed service refuses to stop, as it does on a real machine", async () => {
    await assert.rejects(() => api.serviceAction("web", "down"), /managed by launchd/);
    assert.equal(find(await api.services(), "web").state, "running");
  });

  test("restarting keeps the port and changes the pid", async () => {
    const before = find(await api.services(), "docs");
    const after = await api.serviceAction("docs", "restart");
    assert.equal(after.port, before.port);
    assert.notEqual(after.pid, before.pid);
    assert.equal(after.state, "running");
  });

  test("set-port moves a running service and rejects an occupied port", async () => {
    const moved = await api.serviceAction("docs", "set-port", { port: 8010 });
    assert.equal(moved.port, 8010);
    assert.equal(moved.url, "http://127.0.0.1:8010/");
    await assert.rejects(() => api.serviceAction("api", "up", { port: 8010 }), /已被占用/);
    await api.serviceAction("docs", "set-port", { port: 8000 });
  });

  test("auto-port falls through the pool when the preferred port is taken", async () => {
    await api.serviceAction("worker", "set-port", { port: 8000 });
    const started = await api.serviceAction("worker", "up", { auto_port: true });
    assert.notEqual(started.port, 8000);
    assert.equal(find(await api.services(), "docs").port, 8000, "the occupant keeps its port");
    await api.serviceAction("worker", "down");
  });
});

describe("remote and tunnels", () => {
  test("the scan refreshes the timestamp and keeps the hosts", async () => {
    const before = await api.remote();
    const results = await api.scanRemote();
    const after = await api.remote();
    assert.deepEqual(
      results.map((host) => host.host),
      before.results.map((host) => host.host),
    );
    assert.ok(new Date(after.scanned_at) > new Date(before.scanned_at));
    assert.equal(after.results.find((host) => host.host === "build-box").reachable, false);
  });

  test("a tunnel opened from a scanned port shows up covering it", async () => {
    await api.addTunnel({ name: "pg", host: "pod-b", local_port: 15432, remote_port: 5432 });
    const [host] = (await api.scanRemote(["pod-b"])).filter((item) => item.host === "pod-b");
    assert.deepEqual(host.tunnels["5432"], ["pg"]);
    await api.removeTunnel("pg");
  });

  test("adding a tunnel rejects duplicates, taken ports and unknown hosts", async () => {
    const valid = { name: "dupe", host: "pod-a", local_port: 19090, remote_port: 9090 };
    await api.addTunnel(valid);
    await assert.rejects(() => api.addTunnel(valid), /already exists/);
    await assert.rejects(
      () => api.addTunnel({ ...valid, name: "other" }),
      /local port 19090 is already in use/,
    );
    await assert.rejects(
      () => api.addTunnel({ ...valid, name: "other", host: "nowhere", local_port: 19091 }),
      /不在 ~\/.ssh\/config 中/,
    );
    await api.removeTunnel("dupe");
  });

  test("ensure starts the stopped tunnels and leaves the live one alone", async () => {
    const before = await api.tunnels();
    const live = before.find((tunnel) => tunnel.state === "running");
    assert.ok(live, "the scenario should open with a live tunnel");
    const after = await api.ensureTunnels();
    assert.ok(after.every((tunnel) => tunnel.state === "running"));
    assert.equal(after.find((tunnel) => tunnel.name === live.name).pid, live.pid);
  });

  test("removing an unknown tunnel reports it rather than passing silently", async () => {
    await assert.rejects(() => api.removeTunnel("ghost"), /not found/);
  });
});

test("SSH says plainly that a page cannot open a terminal", async () => {
  await assert.rejects(() => api.ssh("pod-a"), /演示环境无法打开终端/);
});
