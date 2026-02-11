import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

const starDustSrc = (function(){
  const candidate = path.resolve(__dirname, '../../StarDust/frontend/src')
  if(fs.existsSync(candidate)) return candidate
  return null
})()

const starDustEntrypoint = starDustSrc ? path.resolve(starDustSrc, 'stardust-ui.ts') : null
const starDustCss = starDustSrc ? path.resolve(starDustSrc, 'index.css') : null

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      ...(starDustCss ? [{ find: '@stardust/ui/index.css', replacement: starDustCss }] : []),
      ...(starDustEntrypoint ? [{ find: '@stardust/ui', replacement: starDustEntrypoint }] : []),
    ]
  },
  server: {
    port: 3000,
  }
})
