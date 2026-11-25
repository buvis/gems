// Disposable protocol experiment: no real Herdr files, processes or network.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = (await readFile(new URL("main.js", import.meta.url), "utf8"))
  .replace(/^import .*;\n/gm, "")
  .replace("export default class UpdateProbe", "class UpdateProbe")
  + "\nUpdateProbe;";
const key = "sysup.update-probe";
const state = new Map();
let sampled = { app: { version: "0.1.16", ready: null }, checking: false };

function instance(checkMode = false) {
  let deliver;
  let starts = 0;
  const Probe = vm.runInNewContext(source, {
    View: class {},
    div: () => ({ child() { return this; } }),
    checking: () => checkMode,
    updates: () => structuredClone(sampled),
    nextCommand: () => new Promise(resolve => { deliver = resolve; }),
    setShared: (name, value) => state.set(name, structuredClone(value)),
  });
  const probe = new Probe();
  probe.init(undefined, { spawn(fn) { starts++; void fn({ notify() {} }); } });
  return {
    starts,
    async send(command) {
      assert.ok(deliver, "only a loaded instance accepts commands");
      deliver(command);
      await Promise.resolve();
      await Promise.resolve();
    },
  };
}

function read(nonce) {
  const response = state.get(key);
  return response?.schema === 1 && response?.nonce === nonce
    ? response.state : null;
}

const firstNonce = "1".repeat(32);
const secondNonce = "2".repeat(32);
const absentNonce = "3".repeat(32);
assert.equal(instance(true).starts, 0);
assert.equal(state.size, 0);
const first = instance();
await first.send("probe-bad");
assert.equal(state.size, 0);
await first.send(`probe-${firstNonce}`);
assert.deepEqual(read(firstNonce), sampled);
assert.equal(read(absentNonce), null);

// Simulate losing the first loaded instance. Persistent old state is not fresh.
assert.equal(read(secondNonce), null);
sampled = { app: { version: "0.1.17", ready: null }, checking: false };
const replacement = instance();
await replacement.send(`probe-${secondNonce}`);
assert.deepEqual(read(secondNonce), sampled);
assert.equal(read(firstNonce), null);
console.log("PASS: check-mode silence, malformed command rejection, fresh nonce, stale reply rejection, simulated instance replacement.");
console.log("UNPROVEN: native loading, shared-state flush, actual restart recovery, update completion.");
