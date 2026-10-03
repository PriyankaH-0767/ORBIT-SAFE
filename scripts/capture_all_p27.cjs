const http = require('http')
const fs = require('fs')
const path = require('path')
const { spawn } = require('child_process')

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const PORT = 9233
const OUT_DIR = path.resolve('E:/D-DATO/docs/screenshots/p27')
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
      returnByValue: true,
      awaitPromise: true,
    })
    return res.result?.value
  }

  async setViewport(width, height) {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width < 600,
    })
  }

  async captureScreenshot(filename) {
    const res = await this.send('Page.captureScreenshot', { format: 'png' })
    const buffer = Buffer.from(res.data, 'base64')
    const filePath = path.join(OUT_DIR, filename)
    fs.writeFileSync(filePath, buffer)
    if (fs.existsSync(ARTIFACTS_DIR)) {
      fs.writeFileSync(path.join(ARTIFACTS_DIR, filename), buffer)
    }
    console.log(`Saved screenshot: ${filename} (${res.data.length} bytes base64)`)
  }
}

async function main() {
  console.log('Launching isolated Chrome for P27 screenshots...')
  const userDataDir = path.resolve('E:/D-DATO/.temp_chrome_p27')
  if (!fs.existsSync(userDataDir)) {
    fs.mkdirSync(userDataDir, { recursive: true })
  }

  const chromeProcess = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--user-data-dir=${userDataDir}`,
    'about:blank',
  ], { stdio: 'ignore' })

  await sleep(1500)

  const req = http.get(`http://127.0.0.1:${PORT}/json`, (res) => {
    let raw = ''
    res.on('data', chunk => raw += chunk)
    res.on('end', async () => {
      const targets = JSON.parse(raw)
      const pageTarget = targets.find(t => t.type === 'page')
      if (!pageTarget) {
        console.error('No page target found')
        chromeProcess.kill()
        process.exit(1)
      }

      console.log('Target created:', pageTarget.webSocketDebuggerUrl)
      const client = new CDPClient(pageTarget.webSocketDebuggerUrl)
      await client.connect()

      await client.send('Page.enable')
      await client.send('DOM.enable')
      await client.send('Runtime.enable')

      // Desktop viewport
      await client.setViewport(1440, 900)

      // ============================================
      // PART A: PLANNER PAGE SCREENSHOTS (1, 2, 3)
      // ============================================
      console.log('Navigating to Planner Page...')
      await client.send('Page.navigate', { url: 'http://localhost:5173/' })
      await sleep(2500)

      // 1. Problem -> Solution hero
      console.log('1. Capturing Problem -> Solution hero...')
      await client.evaluate(`
        const hero = document.querySelector('[data-testid="planner-hero"]');
        if (hero) hero.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(600)
      await client.captureScreenshot('01_problem_solution_hero.png')

      // 2. Mission flow
      console.log('2. Capturing Mission flow...')
      await client.evaluate(`
        const steps = Array.from(document.querySelectorAll('div')).find(d => d.textContent?.includes('Mission Screening Lifecycle Flow'));
        if (steps) steps.scrollIntoView({ behavior: 'instant', block: 'center' });
      `)
      await sleep(600)
      await client.captureScreenshot('02_mission_flow.png')

      // 3. Demo mode
      console.log('3. Capturing Demo mode...')
      await client.evaluate(`
        const presets = document.querySelector('[data-testid="mission-presets"]');
        if (presets) presets.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(600)
      await client.captureScreenshot('03_demo_mode.png')

      // ============================================
      // PART B: RESULTS PAGE SCREENSHOTS (4, 5, 6, 7, 8, 9)
      // ============================================
      console.log('Navigating to Results Page...')
      await client.send('Page.navigate', { url: 'http://localhost:5173/results/4d7dd60f-26b3-44cc-a84e-626548e7d8cf' })
      await sleep(3500)

      // 4. Conjunction timeline
      console.log('4. Capturing Conjunction timeline...')
      await client.evaluate(`
        const timeline = document.querySelector('[data-testid="conjunction-timeline"]');
        if (timeline) timeline.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(800)
      await client.captureScreenshot('04_conjunction_timeline.png')

      // 5. Timeline event selected
      console.log('5. Capturing Timeline event selected...')
      await client.evaluate(`
        const nodes = document.querySelectorAll('[data-testid="conjunction-timeline"] [role="button"]');
        if (nodes.length > 2) {
          nodes[2].click();
        } else if (nodes.length > 0) {
          nodes[0].click();
        }
      `)
      await sleep(800)
      await client.captureScreenshot('05_timeline_event_selected.png')

      // 6. Event + globe synchronization
      console.log('6. Capturing Event + globe synchronization...')
      await client.evaluate(`
        const globeSec = document.getElementById('globe-section') || document.getElementById('globe-section-heading');
        if (globeSec) globeSec.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(2500)
      await client.captureScreenshot('06_event_globe_sync.png')

      // 7. Mobile timeline (390x844 viewport)
      console.log('7. Capturing Mobile timeline (390x844)...')
      await client.setViewport(390, 844)
      await sleep(500)
      await client.evaluate(`
        const timeline = document.querySelector('[data-testid="conjunction-timeline"]');
        if (timeline) timeline.scrollIntoView({ behavior: 'instant', block: 'start' });
      `)
      await sleep(800)
      await client.captureScreenshot('07_mobile_timeline.png')

      // Restore desktop viewport
      await client.setViewport(1440, 900)
      await sleep(500)

      // 8. Screening mode / provenance
      console.log('8. Capturing Screening mode / provenance...')
      await client.evaluate(`
        const prov = document.querySelector('[data-testid="data-provenance-strip"]');
        if (prov) {
          prov.scrollIntoView({ behavior: 'instant', block: 'center' });
        } else {
          window.scrollTo(0, 300);
        }
      `)
      await sleep(800)
      await client.captureScreenshot('08_screening_mode_provenance.png')

      // 9. Final Results page overview
      console.log('9. Capturing Final Results page overview...')
      await client.evaluate(`
        window.scrollTo(0, 0);
      `)
      await sleep(800)
      await client.captureScreenshot('09_final_results_page.png')

      console.log('All 9 P27 screenshots captured successfully!')
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
