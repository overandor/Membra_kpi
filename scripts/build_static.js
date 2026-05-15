const fs = require('fs');
const path = require('path');

const root = process.cwd();
const out = path.join(root, 'public');
const files = [
  'index.html',
  'dashboard.html',
  'membra-config.json',
  'manifest.webmanifest',
  'robots.txt',
  'sitemap.xml'
];

function copyFile(srcRel) {
  const src = path.join(root, srcRel);
  const dst = path.join(out, srcRel);
  if (!fs.existsSync(src)) throw new Error(`Missing required static file: ${srcRel}`);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
}

function copyDir(srcRel) {
  const src = path.join(root, srcRel);
  const dst = path.join(out, srcRel);
  if (!fs.existsSync(src)) throw new Error(`Missing required static directory: ${srcRel}`);
  fs.rmSync(dst, { recursive: true, force: true });
  fs.mkdirSync(dst, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dst, entry.name);
    if (entry.isDirectory()) {
      fs.cpSync(s, d, { recursive: true });
    } else {
      fs.copyFileSync(s, d);
    }
  }
}

fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });
for (const file of files) copyFile(file);
copyDir('assets');
console.log('MEMBRA KPI static frontend built into public/.');
