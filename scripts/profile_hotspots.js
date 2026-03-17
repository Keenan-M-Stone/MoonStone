const fs = require('fs')

const profilePath = '/home/lemma137/dev/MoonStone/tmp_firefox_profile.json'
const raw = fs.readFileSync(profilePath, 'utf8')
const profile = JSON.parse(raw)

const threads = Array.isArray(profile.threads) ? profile.threads : []
console.log('threads', threads.length)

for (let i = 0; i < threads.length; i++) {
  const t = threads[i] || {}
  const samples = t && t.samples && Array.isArray(t.samples.data) ? t.samples.data.length : 0
  if (samples > 0) {
    console.log(`[${i}] ${t.name || 'UNKNOWN'} pid=${t.pid} tid=${t.tid} samples=${samples}`)
  }
}

let targetIndex = -1
let targetSamples = -1
for (let i = 0; i < threads.length; i++) {
  const t = threads[i] || {}
  const samples = t && t.samples && Array.isArray(t.samples.data) ? t.samples.data.length : 0
  if (samples > targetSamples) {
    targetSamples = samples
    targetIndex = i
  }
}

if (targetIndex < 0) {
  process.exit(0)
}

const t = threads[targetIndex]
console.log('TARGET_THREAD', targetIndex, t.name || 'UNKNOWN', 'samples', targetSamples)

const stackTable = t.stackTable || {}
const frameTable = t.frameTable || {}
const stringArray = Array.isArray(t.stringArray) ? t.stringArray : []
const sampleRows = t.samples && Array.isArray(t.samples.data) ? t.samples.data : []

const inclusiveCounts = new Map()
const leafCounts = new Map()

function inc(map, key) {
  if (key == null || key < 0) return
  map.set(key, (map.get(key) || 0) + 1)
}

for (const row of sampleRows) {
  const leafStack = row[0]
  if (leafStack == null || leafStack < 0) continue

  const leafStackRow = stackTable.data && stackTable.data[leafStack] ? stackTable.data[leafStack] : null
  if (leafStackRow && leafStackRow.length > 0) {
    inc(leafCounts, leafStackRow[0])
  }

  let cursor = leafStack
  let guard = 0
  while (cursor != null && cursor >= 0 && guard < 512) {
    guard += 1
    const sRow = stackTable.data && stackTable.data[cursor] ? stackTable.data[cursor] : null
    if (!sRow || sRow.length < 2) break
    const frameIndex = sRow[0]
    const prefix = sRow[1]
    inc(inclusiveCounts, frameIndex)
    if (prefix == null || prefix < 0) break
    cursor = prefix
  }
}

function frameLabel(frameIndex) {
  const fRow = frameTable.data && frameTable.data[frameIndex] ? frameTable.data[frameIndex] : null
  if (!fRow) return 'NO_FRAME'
  const locIndex = fRow[0]
  if (locIndex == null || locIndex < 0 || locIndex >= stringArray.length) return 'NO_LOC'
  return String(stringArray[locIndex])
}

function printTop(title, counts, n) {
  const top = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).slice(0, n)
  console.log(title)
  for (const [frameIndex, count] of top) {
    console.log(`${count}\tframe=${frameIndex}\t${frameLabel(frameIndex)}`)
  }
}

printTop('TOP_INCLUSIVE', inclusiveCounts, 80)
printTop('TOP_LEAF', leafCounts, 80)
