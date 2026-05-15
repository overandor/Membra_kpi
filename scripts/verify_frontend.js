const fs = require('fs');

const required = [
  'index.html',
  'dashboard.html',
  'assets/membra.css',
  'assets/membra.js',
  'vercel.json'
];

let ok = true;
for (const file of required) {
  if (!fs.existsSync(file)) {
    console.error(`Missing required frontend file: ${file}`);
    ok = false;
  }
}

if (!ok) process.exit(1);
console.log('MEMBRA KPI Vercel frontend verified.');
