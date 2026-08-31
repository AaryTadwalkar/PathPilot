const fs = require('fs');
const path = require('path');

const directory = path.join(__dirname, 'src');

// Some files need bg-brand-bg (like page.tsx navbar), some need bg-brand-card (like ui components).
const replacements = [
  // General text-black replacements (heading text)
  { regex: /text-black/g, replacement: 'text-brand-heading' },
  { regex: /text-gray-900/g, replacement: 'text-brand-heading' },
  { regex: /text-gray-[78]00/g, replacement: 'text-brand-text' },
];

function walkDir(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach((file) => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat && stat.isDirectory()) {
      results = results.concat(walkDir(filePath));
    } else {
      if (filePath.endsWith('.tsx') || filePath.endsWith('.ts')) {
        results.push(filePath);
      }
    }
  });
  return results;
}

const files = walkDir(directory);
let changedFiles = 0;

files.forEach((file) => {
  let content = fs.readFileSync(file, 'utf8');
  let originalContent = content;

  // Manual specific replacements for bg-white based on file context
  if (file.includes('card.tsx')) {
    content = content.replace(/bg-white/g, 'bg-brand-card');
  } else if (file.includes('input.tsx') || file.includes('textarea.tsx')) {
    content = content.replace(/bg-white/g, 'bg-brand-card');
  } else if (file.includes('dropdown-menu.tsx')) {
    content = content.replace(/bg-white/g, 'bg-brand-card');
  } else if (file.includes('tabs.tsx')) {
    // Tabs list background could be bg-brand-secondary, tab trigger bg-brand-card
    content = content.replace(/bg-slate-100/g, 'bg-brand-secondary');
    content = content.replace(/data-\[state=active\]:bg-white/g, 'data-[state=active]:bg-brand-card');
  } else if (file.includes('page.tsx')) {
    // Header in dashboard
    content = content.replace(/<header className="bg-white/g, '<header className="bg-brand-bg');
    // Auth page right panel
    content = content.replace(/bg-white shadow-xl/g, 'bg-brand-card shadow-xl');
    content = content.replace(/bg-white p-8/g, 'bg-brand-card p-8');
    // Any remaining bg-white in pages that are containers
    content = content.replace(/bg-white/g, 'bg-brand-card'); 
  }

  replacements.forEach(({ regex, replacement }) => {
    content = content.replace(regex, replacement);
  });

  if (content !== originalContent) {
    fs.writeFileSync(file, content, 'utf8');
    changedFiles++;
    console.log(`Updated ${file.replace(__dirname, '')}`);
  }
});

console.log(`\nFinished! Updated ${changedFiles} files.`);
