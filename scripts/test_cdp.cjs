const http = require('http')
const { spawn } = require('child_process')

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const PORT = 9230

async function main() {
  const p = spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--window-size=1440,900',
    'about:blank'
  ])

  await new Promise(r => setTimeout(r, 1000))

  const req = http.request({
    hostname: '127.0.0.1',
    port: PORT,
    path: `/json/new?http://localhost:5173/results/4d7dd60f-26b3-44cc-a84e-626548e7d8cf`,
    method: 'PUT'
  }, (res) => {
    let d = ''
    res.on('data', c => d += c)
    res.on('end', () => {
      const target = JSON.parse(d)
      console.log('Target created:', target.webSocketDebuggerUrl)
      const ws = new WebSocket(target.webSocketDebuggerUrl)
      ws.onopen = () => {
        console.log('WS connected!')
        setTimeout(() => {
          console.log('Sending captureScreenshot...')
          ws.send(JSON.stringify({ id: 1, method: 'Page.captureScreenshot', params: { format: 'png' } }))
        }, 3000)
      }
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        console.log('Got msg id:', msg.id, msg.error ? msg.error : (msg.result ? 'has result data len: ' + msg.result.data.length : 'other'))
        p.kill()
        process.exit(0)
      }
      ws.onerror = (e) => {
        console.error('WS error:', e)
        p.kill()
        process.exit(1)
      }
    })
  })
  req.end()
}

main()
