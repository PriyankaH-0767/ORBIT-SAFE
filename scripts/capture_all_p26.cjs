const http = require('http')
const fs = require('fs')
const path = require('path')
const { spawn } = require('child_process')

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const PORT = 9232
const OUT_DIR = path.resolve('E:/D-DATO/docs/screenshots/p26')
const ARTIFACTS_DIR = 'C:\\Users\\prajwal s\\.gemini\\antigravity-ide\\brain\\a6d100e1-0082-4478-b3e4-fe5e7432962f'

if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true })
}

function sleep(ms) {
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
    const res = await this.send('Page.captureScreenshot', { format: 'png' })
    const localPath = path.join(OUT_DIR, filename)
    fs.writeFileSync(localPath, Buffer.from(res.data, 'base64'))
    
    // Copy to artifacts directory
    const artPath = path.join(ARTIFACTS_DIR, filename)
    try {
      fs.writeFileSync(artPath, Buffer.from(res.data, 'base64'))
    } catch {}

    console.log(`Saved screenshot: ${filename} (${res.data.length} bytes base64)`)
    return localPath
  }
}

async function main() {
  console.log('Launching isolated Chrome...')
  const chromeProcess = spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--window-size=1440,1080',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank'
  ])

  await sleep(1500)

  const req = http.request({
    hostname: '127.0.0.1',
    port: PORT,
    path: `/json/new?http://localhost:5173/results/4d7dd60f-26b3-44cc-a84e-626548e7d8cf`,
    method: 'PUT'
  }, async (res) => {
    let d = ''
    res.on('data', c => d += c)
    res.on('end', async () => {
      const target = JSON.parse(d)
      console.log('Target created:', target.webSocketDebuggerUrl)
      const client = new CDPClient(target.webSocketDebuggerUrl)
      await client.connect()

      console.log('Waiting for ResultsPage hydration & Cesium initialization...')
      await sleep(4000)

      // 1. Mission Briefing (expand help panel)
      console.log('1. Capturing Mission Briefing...')
      await client.evaluate(`
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('How to Read'));
        if (btn) btn.click();
        window.scrollTo(0, 0);
      `)
      await sleep(800)
      await client.captureScreenshot('01_mission_briefing.png')

      // 2. Mission Envelope
      console.log('2. Capturing Mission Envelope...')
      await client.evaluate(`
        const env = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('YOUR MISSION SEARCH ENVELOPE'))?.closest('div');
        if (env) {
          env.scrollIntoView({ behavior: 'instant', block: 'start' });
        } else {
          window.scrollTo(0, 500);
        }
      `)
      await sleep(600)
      await client.captureScreenshot('02_mission_envelope.png')

      // 3. Candidate Trade-off Comparison
      console.log('3. Capturing Candidate Trade-off Comparison...')
      await client.evaluate(`
        const compareBtns = Array.from(document.querySelectorAll('button')).filter(b => b.textContent.includes('+ Compare'));
        if (compareBtns.length >= 2) {
          compareBtns[0].click();
          compareBtns[1].click();
        }
      `)
      await sleep(600)
      await client.evaluate(`
        const cmpPanel = document.querySelector('[data-testid="candidate-comparison"]');
        if (cmpPanel) {
          cmpPanel.scrollIntoView({ behavior: 'instant', block: 'start' });
        } else {
          const candSec = document.getElementById('candidate-table-heading');
          if (candSec) candSec.scrollIntoView({ behavior: 'instant', block: 'start' });
        }
      `)
      await sleep(600)
      await client.captureScreenshot('03_candidate_comparison.png')

      // 4. Heatmap Selected Candidate
      console.log('4. Capturing Risk Heatmap...')
      await client.evaluate(`
        const heatmapSec = document.getElementById('heatmap-section-heading');
        if (heatmapSec) heatmapSec.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(1000)
      await client.captureScreenshot('04_heatmap_selected.png')

      // 5. Globe Selected Candidate
      console.log('5. Capturing 3D Orbit Geometry Globe...')
      await client.evaluate(`
        const globeSec = document.getElementById('globe-section') || document.getElementById('globe-section-heading');
        if (globeSec) globeSec.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(2000)
      await client.captureScreenshot('05_globe_selected.png')

      // 6. Event Investigation
      console.log('6. Capturing Event Investigation...')
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

      // 7. Validation Explanation
      console.log('7. Capturing Reference Comparison & Validation...')
      await client.evaluate(`
        const valSec = document.getElementById('validation-heading');
        if (valSec) valSec.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(800)
      await client.captureScreenshot('07_validation_explanation.png')

      // 8. Data Trust & Provenance Strip
      console.log('8. Capturing Data Trust & Provenance Strip...')
      await client.evaluate(`
        const prov = document.querySelector('[data-testid="data-provenance-strip"]');
        if (prov) {
          prov.scrollIntoView({ behavior: 'instant', block: 'center' });
        } else {
          window.scrollTo(0, 320);
        }
      `)
      await sleep(600)
      await client.captureScreenshot('08_provenance.png')

      // 9. Export Section
      console.log('9. Capturing Analysis Package & Export Section...')
      await client.evaluate(`
        const expSec = document.getElementById('export-section-heading');
        if (expSec) expSec.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(600)
      await client.captureScreenshot('09_export.png')

      console.log('All 9 screenshots captured successfully!')
      chromeProcess.kill()
      process.exit(0)
    })
  })
  req.end()
}

main().catch(err => {
  console.error('Error running capture script:', err)
  process.exit(1)
})
