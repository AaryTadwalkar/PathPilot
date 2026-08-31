const fs = require('fs');
const path = require('path');

const directory = path.join(__dirname, 'src');

const replacements = [
  // Gradients
  { regex: /from-indigo-[456]00/g, replacement: 'from-brand-primary' },
  { regex: /to-purple-[567]00/g, replacement: 'to-brand-primary-hover' },
  { regex: /from-indigo-50/g, replacement: 'from-brand-bg' },
  { regex: /to-purple-50/g, replacement: 'to-brand-card' },

  // Text
  { regex: /text-slate-[89]00/g, replacement: 'text-brand-heading' },
  { regex: /text-slate-[567]00/g, replacement: 'text-brand-text' },
  { regex: /text-gray-[567]00/g, replacement: 'text-brand-text' },
  { regex: /text-indigo-[67]00/g, replacement: 'text-brand-primary' },
  { regex: /text-purple-[67]00/g, replacement: 'text-brand-primary' },

  // Backgrounds
  { regex: /bg-indigo-[567]00/g, replacement: 'bg-brand-primary' },
  { regex: /bg-purple-[567]00/g, replacement: 'bg-brand-primary' },
  { regex: /hover:bg-indigo-[67]00/g, replacement: 'hover:bg-brand-primary-hover' },
  { regex: /hover:bg-purple-[67]00/g, replacement: 'hover:bg-brand-primary-hover' },
  
  { regex: /bg-indigo-50/g, replacement: 'bg-brand-secondary' },
  { regex: /bg-purple-50/g, replacement: 'bg-brand-secondary' },
  { regex: /bg-slate-50/g, replacement: 'bg-brand-bg' },
  { regex: /bg-gray-50/g, replacement: 'bg-brand-bg' },

  // Borders
  { regex: /border-indigo-[23]00/g, replacement: 'border-brand-primary' },
  { regex: /border-slate-[23]00/g, replacement: 'border-brand-border' },
  { regex: /border-gray-[23]00/g, replacement: 'border-brand-border' },

  // Rings
  { regex: /ring-indigo-[345]00/g, replacement: 'ring-brand-primary' },
  { regex: /ring-purple-[345]00/g, replacement: 'ring-brand-primary' },
  { regex: /hover:ring-indigo-[345]00/g, replacement: 'hover:ring-brand-primary-hover' }
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
