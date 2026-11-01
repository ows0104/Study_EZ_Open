/** Package canonical authoring assets without changing their text. */
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, "../../content/prompts/bank");
const read = name => readFileSync(resolve(source, name), "utf8");
const template = read("bankPrompt.md");
const version = /Version:\s*(\S+)/.exec(template)?.[1];
if (!version) throw new Error("Canonical bank prompt version is missing");
const names = ["bankPrompt.md", "lectureScopes.json", "fileDelivery.md", "textDelivery.md"];
const bundle = {
  version, template, lectureScopes: JSON.parse(read("lectureScopes.json")),
  deliveries: { file: read("fileDelivery.md"), text: read("textDelivery.md") },
  sourceSha256: Object.fromEntries(names.map(name => [name,
    createHash("sha256").update(readFileSync(resolve(source, name))).digest("hex")])),
};
const target = resolve(here, "../public/bank-prompt.json");
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, JSON.stringify(bundle));
