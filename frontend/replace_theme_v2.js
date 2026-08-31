const fs = require('fs');
const path = require('path');

const directory = path.join(__dirname, 'src');

const replacements = [
  // TEXT
  // Slate/Gray text
  { regex: /text-(slate|gray)-[1234]00(\/[0-9]+)?/g, replacement: 'text-brand-text' },
  { regex: /text-(slate|gray)-[56]00(\/[0-9]+)?/g, replacement: 'text-brand-text' },
  { regex: /text-(slate|gray)-[789]00(\/[0-9]+)?/g, replacement: 'text-brand-heading' },
  
  // Color text
  { regex: /text-(indigo|purple|blue|violet|pink)-[1234]00(\/[0-9]+)?/g, replacement: 'text-brand-ai' }, // lighter accent
  { regex: /text-(indigo|purple|blue|violet|pink)-[56789]00(\/[0-9]+)?/g, replacement: 'text-brand-primary' },

  // BACKGROUNDS
  // Slate/Gray bg
  { regex: /bg-(slate|gray)-50(\/[0-9]+)?/g, replacement: 'bg-brand-bg' },
  { regex: /bg-(slate|gray)-100(\/[0-9]+)?/g, replacement: 'bg-brand-secondary' },
  { regex: /bg-(slate|gray)-[234]00(\/[0-9]+)?/g, replacement: 'bg-brand-border' },
  { regex: /bg-(slate|gray)-[567]00(\/[0-9]+)?/g, replacement: 'bg-brand-text' },
  { regex: /bg-(slate|gray)-[89]00(\/[0-9]+)?/g, replacement: 'bg-brand-sidebar' },

  // Color bg
  { regex: /bg-(indigo|purple|blue|violet|pink)-50(\/[0-9]+)?/g, replacement: 'bg-brand-secondary' },
  { regex: /bg-(indigo|purple|blue|violet|pink)-100(\/[0-9]+)?/g, replacement: 'bg-brand-secondary' },
  { regex: /bg-(indigo|purple|blue|violet|pink)-[234]00(\/[0-9]+)?/g, replacement: 'bg-brand-ai-light' },
  { regex: /bg-(indigo|purple|blue|violet|pink)-[56]00(\/[0-9]+)?/g, replacement: 'bg-brand-primary' },
  { regex: /bg-(indigo|purple|blue|violet|pink)-[789]00(\/[0-9]+)?/g, replacement: 'bg-brand-sidebar' },
  
  // HOVER BACKGROUNDS
  { regex: /hover:bg-(indigo|purple|blue|violet|pink)-[56789]00(\/[0-9]+)?/g, replacement: 'hover:bg-brand-primary-hover' },
  { regex: /hover:bg-(slate|gray)-[89]00(\/[0-9]+)?/g, replacement: 'hover:bg-brand-primary' },
  
  // BORDERS
  { regex: /border-(slate|gray)-[1234]00(\/[0-9]+)?/g, replacement: 'border-brand-border' },
  { regex: /border-(indigo|purple|blue|violet|pink)-[1234]00(\/[0-9]+)?/g, replacement: 'border-brand-border' },
  { regex: /border-(indigo|purple|blue|violet|pink)-[56789]00(\/[0-9]+)?/g, replacement: 'border-brand-primary' },
  { regex: /hover:border-(indigo|purple|blue|violet|pink)-[4567]00(\/[0-9]+)?/g, replacement: 'hover:border-brand-primary-hover' },
  
  // RINGS
  { regex: /ring-(indigo|purple|blue|violet|pink)-[3456]00(\/[0-9]+)?/g, replacement: 'ring-brand-primary' },
  { regex: /focus:border-(indigo|purple|blue|violet|pink)-[456]00(\/[0-9]+)?/g, replacement: 'focus:border-brand-primary' },
  { regex: /accent-(indigo|purple|blue|violet|pink)-[456]00/g, replacement: 'accent-brand-primary' },

  // GRADIENTS
  { regex: /from-(indigo|purple|blue|violet|pink)-[56789]00(\/[0-9]+)?/g, replacement: 'from-brand-primary' },
  { regex: /to-(indigo|purple|blue|violet|pink)-[56789]00(\/[0-9]+)?/g, replacement: 'to-brand-primary-hover' },
  { regex: /via-(indigo|purple|blue|violet|pink)-[56789]00(\/[0-9]+)?/g, replacement: 'via-brand-primary-hover' },
  { regex: /from-(slate|gray|indigo|purple)-50(\/[0-9]+)?/g, replacement: 'from-brand-bg' },
  { regex: /via-(slate|gray|indigo|purple)-50(\/[0-9]+)?/g, replacement: 'via-brand-card' },
  
  // SHADOWS
  { regex: /shadow-(indigo|purple|blue|violet|pink)-[456]00(\/[0-9]+)?/g, replacement: 'shadow-none' } // Use standard shadows instead of colored
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
