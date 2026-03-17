const fs = require('fs')
const p = JSON.parse(fs.readFileSync('/home/lemma137/dev/MoonStone/tmp_firefox_profile.json', 'utf8'))
const threads = Array.isArray(p.threads) ? p.threads : []
console.log('threads', threads.length)
for (let i = 0; i < Math.min(30, threads.length); i++) {
  const t = threads[i] || {}
  const s = t.samples || null
  const keys = s ? Object.keys(s) : []
  let countData = -1
  if (s && Array.isArray(s.data)) countData = s.data.length
  let countStack = -1
  if (s && Array.isArray(s.stack)) countStack = s.stack.length
  let countWeight = -1
  if (s && Array.isArray(s.weight)) countWeight = s.weight.length
  console.log(`[#${i}] name=${t.name || 'UNKNOWN'} pid=${t.pid} tid=${t.tid} sampleKeys=${keys.join(',')} data=${countData} stack=${countStack} weight=${countWeight}`)
}
