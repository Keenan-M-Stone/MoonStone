import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

const starDustSrc = (function(){
  const candidate = path.resolve(__dirname, '../../StarDust/frontend/src')
  if(fs.existsSync(candidate)) return candidate
  return null
})()

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      ...(starDustSrc ? { '@stardust/ui': starDustSrc } : {})
    }
  },
  server: {
    port: 3000,
  }
})
