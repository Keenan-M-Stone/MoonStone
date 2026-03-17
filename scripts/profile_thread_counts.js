const fs = require('fs')
const p = JSON.parse(fs.readFileSync('/home/lemma137/dev/MoonStone/tmp_firefox_profile.json', 'utf8'))
const threads = Array.isArray(p.threads) ? p.threads : []

const rows = []
for (let i = 0; i < threads.length; i++) {
  const t = threads[i] || {}
  const s = t.samples || {}
  const stackArr = Array.isArray(s.stack) ? s.stack : []
  const timeArr = Array.isArray(s.timeDeltas) ? s.timeDeltas : []
  const weightArr = Array.isArray(s.weight) ? s.weight : []
  const lengthVal = typeof s.length === 'number' ? s.length : -1
  rows.push({
    i,
    name: t.name || 'UNKNOWN',
    pid: t.pid,
    tid: t.tid,
    stackLen: stackArr.length,
    timeLen: timeArr.length,
    weightLen: weightArr.length,
    lengthVal,
  })
}
rows.sort((a, b) => Math.max(b.stackLen, b.lengthVal) - Math.max(a.stackLen, a.lengthVal))
console.log('THREAD_COUNTS_TOP')
for (const r of rows.slice(0, 80)) {
  console.log(`${r.i}\t${r.name}\tpid=${r.pid}\ttid=${r.tid}\tstack=${r.stackLen}\ttime=${r.timeLen}\tweight=${r.weightLen}\tlength=${r.lengthVal}`)
}
