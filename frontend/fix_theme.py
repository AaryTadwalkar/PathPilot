import os

pages = [
    'src/app/chat/page.tsx',
    'src/app/courses/page.tsx',
    'src/app/learning-path/page.tsx',
    'src/app/dashboard/page.tsx'
]

replacements = {
    'bg-white/5': 'bg-white shadow-sm',
    'bg-white/10': 'bg-gray-100',
    'bg-white/20': 'bg-gray-200',
    'bg-black/20': 'bg-white shadow-inner',
    'border-white/10': 'border-brand-border',
    'border-white/20': 'border-gray-300',
    'border-white/5': 'border-gray-100',
    'text-white': 'text-brand-heading',
    # Specifically fix primary buttons that SHOULD remain text-white
    'bg-brand-primary text-brand-heading': 'bg-brand-primary text-white',
    'bg-indigo-600 text-brand-heading': 'bg-indigo-600 text-white',
    'bg-green-600 hover:bg-green-700 text-brand-heading': 'bg-green-600 hover:bg-green-700 text-white',
    'text-white w-full': 'text-brand-heading w-full',
}

for page in pages:
    if not os.path.exists(page):
        continue
    with open(page, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements.items():
        content = content.replace(old, new)
        
    with open(page, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed {page}')
