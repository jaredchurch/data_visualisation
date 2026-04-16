/* ════════════════════════════════════════════════════════════════════════════
   Data Visualisation — SPA client
   ════════════════════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────────────────────────
let TOKEN       = localStorage.getItem('dv_token') || null
let USER_EMAIL  = localStorage.getItem('dv_email') || null
let currentObjId = null
let currentChart = null   // Chart.js instance

// ── Boot ──────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  document.body.insertAdjacentHTML('beforeend', '<div id="toast"></div>')
  if (TOKEN) {
    showApp()
  }
})

// ── API helper ────────────────────────────────────────────────────────────────
async function api (method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN
  const res = await fetch('/api' + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  })
  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data))
  return data
}

// ── Toast ─────────────────────────────────────────────────────────────────────
let _toastTimer = null
function toast (msg, type = 'ok') {
  const el = document.getElementById('toast')
  if (!el) return
  el.textContent = msg
  el.className   = 'show ' + type
  clearTimeout(_toastTimer)
  _toastTimer = setTimeout(() => { el.className = '' }, 3000)
}

// ── Auth ──────────────────────────────────────────────────────────────────────
let authMode = 'login'

function showAuthTab (mode) {
  authMode = mode
  document.querySelectorAll('.tab-btn').forEach((b, i) => {
    b.classList.toggle('active', (i === 0 && mode === 'login') || (i === 1 && mode === 'register'))
  })
  const btn = document.getElementById('auth-submit-btn')
  if (btn) btn.textContent = mode === 'login' ? 'Sign in' : 'Create account'
  setMsg('auth-msg', '')
}

async function submitAuth (e) {
  e.preventDefault()
  const email    = document.getElementById('auth-email').value.trim()
  const password = document.getElementById('auth-password').value
  setMsg('auth-msg', '')
  try {
    const path = authMode === 'login' ? '/auth/login' : '/auth/register'
    const data = await api('POST', path, { email, password })
    TOKEN      = data.access_token
    USER_EMAIL = data.email
    localStorage.setItem('dv_token', TOKEN)
    localStorage.setItem('dv_email', USER_EMAIL)
    showApp()
  } catch (err) {
    setMsg('auth-msg', err.message, 'error')
  }
}

function logout () {
  TOKEN = null; USER_EMAIL = null
  localStorage.removeItem('dv_token')
  localStorage.removeItem('dv_email')
  document.getElementById('screen-app').classList.add('hidden')
  document.getElementById('screen-auth').classList.remove('hidden')
}

function showApp () {
  document.getElementById('screen-auth').classList.add('hidden')
  document.getElementById('screen-app').classList.remove('hidden')
  const navUser = document.getElementById('nav-user')
  if (navUser) navUser.textContent = USER_EMAIL || ''
  showObjects()
}

// ── Objects ───────────────────────────────────────────────────────────────────
async function showObjects () {
  show('view-objects'); hide('view-object')
  const list = document.getElementById('objects-list')
  list.innerHTML = '<p class="empty-state">Loading…</p>'
  try {
    const objects = await api('GET', '/objects')
    if (!objects.length) {
      list.innerHTML = '<p class="empty-state">No objects yet — create one to get started.</p>'
      return
    }
    list.innerHTML = objects.map(o => `
      <div class="obj-card" onclick="openObject(${o.id}, '${esc(o.name)}')">
        <h4>${esc(o.name)}</h4>
        <p>${esc(o.description || 'No description')}</p>
        <div class="obj-card-footer">
          <button class="btn btn-danger btn-sm" onclick="event.stopPropagation();deleteObject(${o.id})">Delete</button>
        </div>
      </div>
    `).join('')
  } catch (err) {
    list.innerHTML = `<p class="empty-state" style="color:var(--danger)">${esc(err.message)}</p>`
  }
}

async function createObject () {
  const name = document.getElementById('new-obj-name').value.trim()
  const desc = document.getElementById('new-obj-desc').value.trim()
  if (!name) { setMsg('new-obj-msg', 'Name is required', 'error'); return }
  try {
    await api('POST', '/objects', { name, description: desc })
    hideModal('modal-new-object')
    document.getElementById('new-obj-name').value = ''
    document.getElementById('new-obj-desc').value = ''
    toast('Object created')
    showObjects()
  } catch (err) {
    setMsg('new-obj-msg', err.message, 'error')
  }
}

async function deleteObject (id) {
  if (!confirm('Delete this object and all its data?')) return
  try {
    await api('DELETE', `/objects/${id}`)
    toast('Object deleted')
    showObjects()
  } catch (err) {
    toast(err.message, 'err')
  }
}

// ── Object detail ─────────────────────────────────────────────────────────────
async function openObject (id, name) {
  currentObjId = id
  hide('view-objects'); show('view-object')
  document.getElementById('obj-title').textContent = name
  showObjTab('connections')
}

function showObjTab (tab) {
  document.querySelectorAll('.objtab').forEach(t => t.classList.add('hidden'))
  document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'))
  show('objtab-' + tab)
  const stabs = document.querySelectorAll('.stab')
  const order = ['connections','queries','tables','charts']
  stabs[order.indexOf(tab)]?.classList.add('active')

  if (tab === 'connections') loadConnections()
  else if (tab === 'queries') loadQueries()
  else if (tab === 'tables')  loadTables()
  else if (tab === 'charts')  loadCharts()
}

// ── Connections ───────────────────────────────────────────────────────────────
async function loadConnections () {
  const el = document.getElementById('connections-list')
  el.innerHTML = '<p class="empty-state">Loading…</p>'
  try {
    const conns = await api('GET', `/objects/${currentObjId}/connections`)
    if (!conns.length) { el.innerHTML = '<p class="empty-state">No connections yet.</p>'; return }
    el.innerHTML = conns.map(c => `
      <div class="list-item">
        <div class="list-item-info">
          <h4>${esc(c.name)}</h4>
          <p>${esc(c.username)}@${esc(c.host)}:${c.port} / ${esc(c.dbname)}</p>
        </div>
        <div class="list-item-actions">
          <button class="btn btn-danger btn-sm" onclick="deleteConnection(${c.id})">Delete</button>
        </div>
      </div>
    `).join('')
  } catch (err) {
    el.innerHTML = `<p class="empty-state" style="color:var(--danger)">${esc(err.message)}</p>`
  }
}

async function createConnection () {
  const body = {
    name:     document.getElementById('conn-name').value.trim(),
    host:     document.getElementById('conn-host').value.trim(),
    port:     parseInt(document.getElementById('conn-port').value) || 5432,
    dbname:   document.getElementById('conn-dbname').value.trim(),
    username: document.getElementById('conn-user').value.trim(),
    password: document.getElementById('conn-pass').value,
  }
  if (!body.name || !body.host || !body.dbname || !body.username) {
    setMsg('conn-msg', 'Please fill in all required fields', 'error'); return
  }
  try {
    await api('POST', `/objects/${currentObjId}/connections`, body)
    hideModal('modal-new-connection')
    clearConnectionForm()
    toast('Connection saved')
    loadConnections()
  } catch (err) {
    setMsg('conn-msg', err.message, 'error')
  }
}

async function testConnection () {
  // Save temporarily and test, or just test with current form values
  const body = {
    name:     document.getElementById('conn-name').value.trim() || 'test',
    host:     document.getElementById('conn-host').value.trim(),
    port:     parseInt(document.getElementById('conn-port').value) || 5432,
    dbname:   document.getElementById('conn-dbname').value.trim(),
    username: document.getElementById('conn-user').value.trim(),
    password: document.getElementById('conn-pass').value,
  }
  if (!body.host || !body.dbname || !body.username) {
    setMsg('conn-msg', 'Fill in host, database, and username first', 'error'); return
  }
  setMsg('conn-msg', 'Testing connection…')
  try {
    // Create temp, test, delete
    const created = await api('POST', `/objects/${currentObjId}/connections`, body)
    const result  = await api('POST', `/objects/${currentObjId}/connections/${created.id}/test`)
    await api('DELETE', `/objects/${currentObjId}/connections/${created.id}`)
    setMsg('conn-msg', '✓ ' + result.message, 'success')
  } catch (err) {
    setMsg('conn-msg', '✗ ' + err.message, 'error')
  }
}

async function deleteConnection (id) {
  if (!confirm('Delete this connection?')) return
  await api('DELETE', `/objects/${currentObjId}/connections/${id}`)
  toast('Connection deleted')
  loadConnections()
}

function clearConnectionForm () {
  ['conn-name','conn-host','conn-port','conn-dbname','conn-user','conn-pass']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = id === 'conn-port' ? '5432' : '' })
  setMsg('conn-msg', '')
}

// ── Queries ───────────────────────────────────────────────────────────────────
async function loadQueries () {
  const el = document.getElementById('queries-list')
  el.innerHTML = '<p class="empty-state">Loading…</p>'
  try {
    const queries = await api('GET', `/objects/${currentObjId}/queries`)
    if (!queries.length) { el.innerHTML = '<p class="empty-state">No queries yet.</p>'; return }
    el.innerHTML = queries.map(q => `
      <div class="list-item">
        <div class="list-item-info">
          <h4>${esc(q.name)} <span class="badge">${esc(q.target_table)}</span></h4>
          <p style="font-family:monospace;font-size:0.78rem;margin-top:4px;">${esc(q.sql_text.slice(0,80))}${q.sql_text.length > 80 ? '…' : ''}</p>
          ${q.last_run_at ? `<p style="margin-top:4px;">Last run: ${q.last_run_at} · ${q.row_count ?? 0} rows</p>` : '<p style="margin-top:4px;color:var(--muted)">Not yet run</p>'}
        </div>
        <div class="list-item-actions">
          <button class="btn btn-success btn-sm" onclick="runQuery(${q.id})">▶ Run</button>
          <button class="btn btn-danger btn-sm"  onclick="deleteQuery(${q.id})">Delete</button>
        </div>
      </div>
    `).join('')
  } catch (err) {
    el.innerHTML = `<p class="empty-state" style="color:var(--danger)">${esc(err.message)}</p>`
  }
}

async function openNewQueryModal () {
  // Populate connection selector
  const sel = document.getElementById('q-conn')
  sel.innerHTML = '<option value="">Loading…</option>'
  try {
    const conns = await api('GET', `/objects/${currentObjId}/connections`)
    if (!conns.length) {
      sel.innerHTML = '<option value="">No connections — add one first</option>'
    } else {
      sel.innerHTML = conns.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')
    }
  } catch (_) {}
  showModal('modal-new-query')
}

async function createQuery () {
  const body = {
    name:          document.getElementById('q-name').value.trim(),
    connection_id: parseInt(document.getElementById('q-conn').value),
    target_table:  document.getElementById('q-table').value.trim(),
    sql_text:      document.getElementById('q-sql').value.trim(),
  }
  if (!body.name || !body.connection_id || !body.target_table || !body.sql_text) {
    setMsg('q-msg', 'Please fill in all fields', 'error'); return
  }
  try {
    await api('POST', `/objects/${currentObjId}/queries`, body)
    hideModal('modal-new-query')
    toast('Query saved')
    loadQueries()
  } catch (err) {
    setMsg('q-msg', err.message, 'error')
  }
}

async function runQuery (qid) {
  toast('Running query…')
  try {
    const res = await api('POST', `/objects/${currentObjId}/queries/${qid}/run`)
    toast(`✓ ${res.message}`, 'ok')
    loadQueries()
  } catch (err) {
    toast('✗ ' + err.message, 'err')
  }
}

async function deleteQuery (qid) {
  if (!confirm('Delete this query?')) return
  await api('DELETE', `/objects/${currentObjId}/queries/${qid}`)
  toast('Query deleted')
  loadQueries()
}

// Override the Add query button to populate connections first
document.addEventListener('DOMContentLoaded', () => {
  // Patch the "Add query" button after DOM loads
  document.querySelectorAll('[onclick="showModal(\'modal-new-query\')"]').forEach(btn => {
    btn.onclick = openNewQueryModal
  })
})

// ── Tables ────────────────────────────────────────────────────────────────────
async function loadTables () {
  const el = document.getElementById('tables-list')
  el.innerHTML = '<p class="empty-state">Loading…</p>'
  try {
    const tables = await api('GET', `/objects/${currentObjId}/tables`)
    if (!tables.length) {
      el.innerHTML = '<p class="empty-state">No ingested data yet — run a query to populate DuckDB.</p>'
      return
    }
    el.innerHTML = '<div class="tables-grid">' + tables.map(t => `
      <div class="table-card">
        <h4>📋 ${esc(t.table)}</h4>
        ${t.columns.map(c => `<span class="col-pill">${esc(c)}</span>`).join('')}
      </div>
    `).join('') + '</div>'
  } catch (err) {
    el.innerHTML = `<p class="empty-state" style="color:var(--danger)">${esc(err.message)}</p>`
  }
}

// ── Charts ────────────────────────────────────────────────────────────────────
async function loadCharts () {
  const el = document.getElementById('charts-list')
  el.innerHTML = '<p class="empty-state">Loading…</p>'
  try {
    const charts = await api('GET', `/objects/${currentObjId}/charts`)
    if (!charts.length) {
      el.innerHTML = '<p class="empty-state">No charts yet.</p>'
      return
    }
    el.innerHTML = charts.map(c => `
      <div class="chart-card">
        <div class="chart-card-header">
          <h4>${esc(c.name)} <span class="badge">${esc(c.chart_type)}</span></h4>
          <div style="display:flex;gap:6px;">
            <button class="btn btn-primary btn-sm" onclick="viewChart(${c.id},'${esc(c.name)}','${esc(c.chart_type)}')">View</button>
            <button class="btn btn-danger btn-sm"  onclick="deleteChart(${c.id})">Delete</button>
          </div>
        </div>
        <p class="chart-meta">Measure: <code>${esc(c.measure)}</code> &nbsp;·&nbsp; Dimension: <code>${esc(c.dimension)}</code></p>
      </div>
    `).join('')
  } catch (err) {
    el.innerHTML = `<p class="empty-state" style="color:var(--danger)">${esc(err.message)}</p>`
  }
}

async function openNewChartModal () {
  // Load tables hint
  const hint = document.getElementById('chart-tables-hint')
  try {
    const tables = await api('GET', `/objects/${currentObjId}/tables`)
    if (tables.length) {
      hint.textContent = 'Available tables: ' + tables.map(t =>
        t.table + ' (' + t.columns.join(', ') + ')'
      ).join(' · ')
    } else {
      hint.textContent = 'No ingested tables yet — run your queries first.'
    }
  } catch (_) {}
  showModal('modal-new-chart')
}

async function createChart () {
  const body = {
    name:       document.getElementById('chart-name').value.trim(),
    chart_type: document.getElementById('chart-type').value,
    measure:    document.getElementById('chart-measure').value.trim(),
    dimension:  document.getElementById('chart-dimension').value.trim(),
  }
  if (!body.name || !body.measure || !body.dimension) {
    setMsg('chart-msg', 'Please fill in all fields', 'error'); return
  }
  try {
    await api('POST', `/objects/${currentObjId}/charts`, body)
    hideModal('modal-new-chart')
    toast('Chart created')
    loadCharts()
  } catch (err) {
    setMsg('chart-msg', err.message, 'error')
  }
}

async function viewChart (chid, name, chartType) {
  document.getElementById('chart-view-title').textContent = name
  document.getElementById('chart-sql').textContent = 'Loading…'
  showModal('modal-chart-view')

  try {
    const data = await api('GET', `/objects/${currentObjId}/charts/${chid}/data`)

    // Destroy previous chart
    if (currentChart) { currentChart.destroy(); currentChart = null }

    const ctx = document.getElementById('chart-canvas').getContext('2d')

    // Map chart type
    let type = chartType
    if (chartType === 'horizontalBar') type = 'bar'
    const indexAxis = chartType === 'horizontalBar' ? 'y' : 'x'

    const colors = data.labels.map((_, i) => `hsl(${(i * 47) % 360},65%,55%)`)

    currentChart = new Chart(ctx, {
      type: type,
      data: {
        labels: data.labels,
        datasets: [{
          label: name,
          data: data.values,
          backgroundColor: colors,
          borderColor: colors.map(c => c.replace('55%', '45%')),
          borderWidth: 1.5,
          borderRadius: type === 'bar' ? 4 : 0,
        }]
      },
      options: {
        indexAxis,
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: ['pie','doughnut'].includes(type) },
          tooltip: { callbacks: { label: ctx => ` ${ctx.formattedValue}` } }
        },
        scales: ['pie','doughnut'].includes(type) ? {} : {
          x: { grid: { color: '#f1f5f9' } },
          y: { grid: { color: '#f1f5f9' } }
        }
      }
    })

    document.getElementById('chart-sql').textContent = data.sql

  } catch (err) {
    if (currentChart) { currentChart.destroy(); currentChart = null }
    document.getElementById('chart-sql').textContent = 'Error: ' + err.message
    toast('Chart failed: ' + err.message, 'err')
  }
}

async function deleteChart (chid) {
  if (!confirm('Delete this chart?')) return
  await api('DELETE', `/objects/${currentObjId}/charts/${chid}`)
  toast('Chart deleted')
  loadCharts()
}

// Patch "Add chart" button
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[onclick="showModal(\'modal-new-chart\')"]').forEach(btn => {
    btn.onclick = openNewChartModal
  })
})

// ── UI helpers ────────────────────────────────────────────────────────────────
function show (id) { document.getElementById(id)?.classList.remove('hidden') }
function hide (id) { document.getElementById(id)?.classList.add('hidden') }

function showModal (id) {
  document.getElementById(id)?.classList.remove('hidden')
}
function hideModal (id) {
  document.getElementById(id)?.classList.add('hidden')
  // Clear messages
  const msgId = id.replace('modal-', '') + '-msg'
  setMsg(msgId, '')
}
function closeModalOutside (e, id) {
  if (e.target.id === id) hideModal(id)
}

function setMsg (id, text, type) {
  const el = document.getElementById(id)
  if (!el) return
  el.textContent = text
  el.className   = 'modal-msg' + (type ? ' ' + type : '')
}

function esc (str) {
  if (str == null) return ''
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;')
}
