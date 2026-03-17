import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const root = path.resolve(__dirname, '..')
const srcRoot = path.join(root, 'src')

const violations = []

function walk(dir) {
  const out = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...walk(full))
      continue
    }
    if (/\.(ts|tsx|js|jsx)$/.test(entry.name)) out.push(full)
  }
  return out
}

function rel(file) {
  return path.relative(root, file).split(path.sep).join('/')
}

for (const file of walk(srcRoot)) {
  const text = fs.readFileSync(file, 'utf8')
  const r = rel(file)

  if (text.includes("from '@stardust/ui'") && r !== 'src/stardust.ts') {
    violations.push(`${r}: direct package import; use local adapter src/stardust.ts`)
  }

  if (text.includes("@stardust/ui/index.css")) {
    violations.push(`${r}: forbidden css path @stardust/ui/index.css (use @stardust/ui/style.css)`)
  }

  if (text.includes("@stardust/ui/style.css") && r !== 'src/main.tsx') {
    violations.push(`${r}: style import should live only in src/main.tsx`)
  }
}

if (violations.length) {
  console.error('\nStarDust contract check failed:\n')
  for (const v of violations) console.error(`- ${v}`)
  process.exit(1)
}

console.log('StarDust contract check passed.')
