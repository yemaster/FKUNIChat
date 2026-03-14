import fs from "node:fs/promises";
import path from "node:path";

const releaseDir = path.resolve("release");
const system = process.env.PACKAGE_SYSTEM;
const arch = process.env.PACKAGE_ARCH;
const extensions = (process.env.PACKAGE_EXTENSIONS || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

if (!system || !arch || extensions.length === 0) {
  throw new Error("Missing release package rename configuration");
}

const packageJson = JSON.parse(
  await fs.readFile(path.resolve("package.json"), "utf8"),
);
const productName = packageJson.build?.productName || packageJson.productName || packageJson.name;
const version = packageJson.version;

const files = await fs.readdir(releaseDir);

for (const extension of extensions) {
  const expectedSuffix = `.${extension}`;
  const matches = files
    .filter((file) => file.endsWith(expectedSuffix))
    .filter((file) => !file.endsWith(`${expectedSuffix}.blockmap`))
    .sort();

  if (matches.length !== 1) {
    throw new Error(
      `Expected exactly one ${extension} package in release/, found ${matches.length}`,
    );
  }

  const source = path.join(releaseDir, matches[0]);
  const target = path.join(
    releaseDir,
    `${productName}-${version}-${system}-${arch}.${extension}`,
  );

  if (source !== target) {
    await fs.rename(source, target);
  }
}
