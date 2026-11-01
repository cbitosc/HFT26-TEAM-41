// Generate TypeScript types in lib/contracts/ from ../contracts/*.schema.json.
// Run through `make contracts`. The output is committed; never edit it by hand.
import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compileFromFile } from "json-schema-to-typescript";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const contractsDir = resolve(frontendDir, "..", "contracts");
const outDir = join(frontendDir, "lib", "contracts");

const schemas = readdirSync(contractsDir)
  .filter((name) => name.endsWith(".schema.json"))
  .sort();
if (schemas.length === 0) {
  console.error(`No schemas found in ${contractsDir}`);
  process.exit(1);
}

// Start clean so a deleted schema doesn't leave a stale module behind.
rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

for (const name of schemas) {
  const ts = await compileFromFile(join(contractsDir, name), {
    cwd: contractsDir,
    bannerComment: `// Generated from contracts/${name} by \`make contracts\`. Do not edit.`,
  });
  const outName = `${name.replace(/\.schema\.json$/, "")}.ts`;
  writeFileSync(join(outDir, outName), ts);
  console.log(`${name} -> lib/contracts/${outName}`);
}
