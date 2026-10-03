const http = require('http')
const fs = require('fs')
const path = require('path')
const { spawn } = require('child_process')

const OUT_DIR = path.resolve('E:/D-DATO/docs/screenshots/p26')
if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true })
}

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const PORT = 9228
const USER_DATA_DIR = path.resolve('E:/D-DATO/scratch/chrome_user_data')
if (!fs.existsSync(USER_DATA_DIR)) {
  fs.mkdirSync(USER_DATA_DIR, { recursive: true })
}

async function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try { resolve(JSON.parse(data)) } catch (e) { reject(e) }
      })
    }).on('error', reject)
  })
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms))
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl
    this.ws = null
    this.id = 1
    this.pending = new Map()
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl)
      this.ws.onopen = () => resolve()
      this.ws.onerror = (e) => reject(e)
      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        if (msg.id && this.pending.has(msg.id)) {
          const { res, rej } = this.pending.get(msg.id)
          this.pending.delete(msg.id)
          if (msg.error) rej(msg.error)
          else res(msg.result)
        }
      }
    })
  }

  async send(method, params = {}) {
    const id = this.id++
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej })
      this.ws.send(JSON.stringify({ id, method, params }))
    })
  }

  async evaluate(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true
    })
    return res?.result?.value
  }

  async captureScreenshot(filename) {
    const params = { format: 'png' }
    const res = await this.send('Page.captureScreenshot', params)
    const filePath = path.join(OUT_DIR, filename)
    fs.writeFileSync(filePath, Buffer.from(res.data, 'base64'))
    console.log(`Saved screenshot: ${filePath} (${res.data.length} bytes base64)`)
    return filePath
  }
}

async function main() {
  console.log('Launching headless Chrome with remote debugging on port ' + PORT)
  const chromeProcess = spawn(CHROME_PATH, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${USER_DATA_DIR}`,
    '--window-size=1440,1100',
    '--disable-gpu',
    '--no-sandbox',
    'http://localhost:5173/results/4d7dd60f-26b3-44cc-a84e-626548e7d8cf'
  ], { detached: false })

  let wsUrl = null
  for (let i = 0; i < 30; i++) {
    try {
      const list = await getJson(`http://127.0.0.1:${PORT}/json/list`)
      if (list && list.length > 0 && list[0].webSocketDebuggerUrl) {
        wsUrl = list[0].webSocketDebuggerUrl
        break
      }
    } catch {
      await sleep(300)
    }
  }

  if (!wsUrl) {
    throw new Error('Failed to connect to Chrome remote debugging port ' + PORT)
  }

  console.log('Connected to Chrome via CDP:', wsUrl)
  const client = new CDPClient(wsUrl)
  await client.connect()

  await client.send('Page.enable')
  await client.send('DOM.enable')

  console.log('Navigating explicitly to results URL...')
  await client.send('Page.navigate', {
    url: 'http://localhost:5173/results/4d7dd60f-26b3-44cc-a84e-626548e7d8cf'
  })

  console.log('Waiting for ResultsPage to fully hydrate...')
  await sleep(4000)

  // 1. Mission Briefing Screenshot (with "How to Read D-DATO Results" opened)
  console.log('Capturing 1. Mission Briefing...')
  await client.evaluate(`
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('How to Read'));
    if (btn) btn.click();
    window.scrollTo(0, 0);
  `)
  await sleep(800)
  await client.captureScreenshot('01_mission_briefing.png')

  // 2. Mission Envelope Screenshot (inside Mission Briefing)
  console.log('Capturing 2. Mission Envelope...')
  await client.evaluate(`
    const env = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('YOUR MISSION SEARCH ENVELOPE'))?.closest('div');
    if (env) {
      env.scrollIntoView({ behavior: 'instant', block: 'start' });
    } else {
      window.scrollTo(0, 450);
    }
  `)
  await sleep(600)
  await client.captureScreenshot('02_mission_envelope.png')

  // 3. Candidate Trade-off Comparison Screenshot
  console.log('Capturing 3. Candidate Comparison...')
  await client.evaluate(`
    const compareBtns = Array.from(document.querySelectorAll('button')).filter(b => b.textContent.includes('+ Compare'));
    if (compareBtns.length >= 2) {
      compareBtns[0].click();
      compareBtns[1].click();
    }
  `)
  await sleep(600)
  await client.evaluate(`
    const cmpPanel = document.querySelector('[data-testid="candidate-comparison-panel"]');
    if (cmpPanel) {
      cmpPanel.scrollIntoView({ behavior: 'instant', block: 'center' });
    } else {
      const candSec = document.getElementById('candidate-table-heading');
      if (candSec) candSec.scrollIntoView({ behavior: 'instant', block: 'start' });
    }
  `)
  await sleep(600)
  await client.captureScreenshot('03_candidate_comparison.png')

  // 4. Heatmap Selected Candidate Screenshot
  console.log('Capturing 4. Heatmap...')
  await client.evaluate(`
    const heatmapSec = document.getElementById('heatmap-section-heading');
    if (heatmapSec) heatmapSec.scrollIntoView({ behavior: 'instant', block: 'start' });
  `)
  await sleep(1000)
  await client.captureScreenshot('04_heatmap_selected.png')

  // 5. Globe Selected Candidate Screenshot
  console.log('Capturing 5. 3D Globe...')
  await client.evaluate(`
    const globeSec = document.getElementById('globe-section') || document.getElementById('globe-section-heading');
    if (globeSec) globeSec.scrollIntoView({ behavior: 'instant', block: 'start' });
  `)
  await sleep(1500)
  await client.captureScreenshot('05_globe_selected.png')

  // 6. Event Investigation Screenshot
  console.log('Capturing 6. Event Investigation...')
  await client.evaluate(`
    const rows = document.querySelectorAll('table tbody tr');
    const evtRow = Array.from(rows).find(r => r.textContent.includes('km/s') || r.textContent.includes('UTC') || r.textContent.includes('ddato'));
    if (evtRow) evtRow.click();
  `)
  await sleep(600)
  await client.evaluate(`
    const panel = document.querySelector('[data-testid="event-detail-panel"]');
    if (panel) {
      panel.scrollIntoView({ behavior: 'instant', block: 'center' });
    } else {
      const evtHeading = document.getElementById('event-table-heading');
      if (evtHeading) evtHeading.scrollIntoView({ behavior: 'instant', block: 'start' });
    }
  `)
  await sleep(600)
  await client.captureScreenshot('06_event_investigation.png')

  // 7. Validation Explanation Screenshot
  console.log('Capturing 7. Validation Explanation...')
  await client.evaluate(`
    const valSec = document.getElementById('validation-heading');
    if (valSec) valSec.scrollIntoView({ behavior: 'instant', block: 'start' });
  `)
  await sleep(600)
  await client.captureScreenshot('07_validation_explanation.png')

  // 8. Data Provenance Strip Screenshot
  console.log('Capturing 8. Data Provenance Strip...')
  await client.evaluate(`
    const prov = document.querySelector('[data-testid="data-provenance-strip"]');
    if (prov) {
      prov.scrollIntoView({ behavior: 'instant', block: 'center' });
    } else {
      window.scrollTo(0, 350);
    }
  `)
  await sleep(600)
  await client.captureScreenshot('08_provenance.png')

  // 9. Export Section Screenshot
  console.log('Capturing 9. Export Section...')
  await client.evaluate(`
    const expSec = document.getElementById('export-section-heading');
    if (expSec) expSec.scrollIntoView({ behavior: 'instant', block: 'start' });
  `)
  await sleep(600)
  await client.captureScreenshot('09_export.png')

  console.log('All 9 screenshots captured successfully!')

  try {
    chromeProcess.kill()
  } catch {}
  process.exit(0)
}

main().catch(err => {
  console.error('Error in capture script:', err)
  process.exit(1)
})
