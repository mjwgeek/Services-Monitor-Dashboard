<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Services Monitor Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: sans-serif;
      background-color: #1e1e1e;
      color: #eee;
      margin: 0;
      padding: 20px;
    }
    .header, .header-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }
    .tabs, .subtabs {
      overflow-x: auto;
      white-space: nowrap;
      background-color: #111;
      margin-bottom: 10px;
      display: flex;
    }
    .tabs button, .subtabs button {
      background-color: inherit;
      border: none;
      cursor: pointer;
      padding: 10px 20px;
      color: #ccc;
      font-size: 16px;
    }
    .tabs button.active, .subtabs button.active {
      background-color: #444;
      color: white;
    }
    .tabcontent {
      display: none;
      padding-top: 10px;
    }
    .tabcontent.active {
      display: block;
    }
    .table-wrapper {
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      min-width: 700px;
    }
    th, td {
      padding: 6px 10px;
      border-bottom: 1px solid #444;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      text-align: left;
    }
    tr:hover { background: #2a2a2a; }
    tr.failed { background: #440000; }

    .status-active { color: #0f0; font-weight: bold; }
    .status-failed { color: #f00; font-weight: bold; }
    .status-inactive { color: #ff0; font-weight: bold; }

    input, select, button {
      background: #222;
      color: #eee;
      border: 1px solid #555;
      border-radius: 4px;
      padding: 4px 8px;
      font-size: 14px;
    }

    .button {
      font-size: 12px;
      margin-left: 2px;
    }

    .form-group {
      margin-bottom: 10px;
    }

    label {
      display: block;
      margin-bottom: 4px;
      font-size: 14px;
    }

    #searchInput {
      width: 100%;
      margin: 10px 0;
    }

    .summary {
      font-size: 14px;
      margin: 6px 0;
      color: #bbb;
    }

    #loadingMessage {
      text-align: center;
      padding: 20px;
      font-size: 18px;
      color: #ddd;
    }

	#toast {
	  position: fixed;
	  top: 20px;
	  right: 20px;
	  background: #333;
	  color: #fff;
	  padding: 12px 20px;
	  border-radius: 5px;
	  box-shadow: 0 0 10px #000;
	  z-index: 9999;
	  display: none;
	}

    #spinnerOverlay {
      display: none;
      position: fixed;
      top: 0; left: 0;
      width: 100%; height: 100%;
      background: rgba(0,0,0,0.6);
      z-index: 9998;
      align-items: center;
      justify-content: center;
    }

    .spinner {
      border: 6px solid #444;
      border-top: 6px solid #0f0;
      border-radius: 50%;
      width: 48px;
      height: 48px;
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    @media (max-width: 600px) {
      th, td { font-size: 13px; padding: 4px; }
      .button { font-size: 10px; padding: 3px 5px; }
    }
  </style>
</head>
<body>

<div class="header">
  <h1>Services Monitor Dashboard</h1>
  <div class="header-controls">
    <span id="lastUpdated">Last updated: --:--:--</span>
    <button onclick="manualRefresh()">Refresh</button>
    <select id="refreshInterval">
      <option value="60000" selected>60s</option>
      <option value="120000">120s</option>
      <option value="300000">300s</option>
    </select>
    <label>
      <input type="checkbox" id="autoRefreshToggle">
      Auto
    </label>
    <select id="statusFilter" onchange="applyFilters()">
      <option value="all">All</option>
      <option value="active">Active</option>
      <option value="inactive">Inactive</option>
      <option value="failed">Failed</option>
      <option value="tcp">TCP</option>
      <option value="udp">UDP</option>
    </select>
    <button onclick="forceRefresh()">🔁 Force Refresh Cache</button>
  </div>
</div>


<!-- Removed search input box -->
<!-- <input type="text" id="searchInput" placeholder="Filter services or ports..." oninput="applyFilters()"> -->
<div id="loadingMessage">⏳ Loading data, please wait...</div>

<!-- Tabs -->
<div class="tabs">
  <button class="tablink active" onclick="openMainTab(event, 'services')">Services</button>
  <button class="tablink" onclick="openMainTab(event, 'ports')">Ports</button>
  <button class="tablink" onclick="openMainTab(event, 'addMachine')">+ New Machine</button>
</div>

<div class="subtabs" id="services-subtabs"></div>
<div class="tabcontent active" id="services-tabcontent"></div>

<div class="subtabs" id="ports-subtabs" style="display:none;"></div>
<div class="tabcontent" id="ports-tabcontent" style="display:none;"></div>

<div class="tabcontent" id="addMachine">
  <h2>Add New Machine</h2>
  <form id="addMachineForm" onsubmit="return submitMachineForm();">
    <div class="form-group">
      <label for="name">Name:</label>
      <input required type="text" name="name" id="name">
    </div>
    <div class="form-group">
      <label for="host">IP Address:</label>
      <input required type="text" name="host" id="host">
    </div>
    <div class="form-group">
      <label for="port">SSH Port:</label>
      <input required type="number" name="port" id="port" value="22">
    </div>
    <div class="form-group">
      <label for="user">Username:</label>
      <input required type="text" name="user" id="user" value="root">
    </div>
    <div class="form-group">
      <label for="password">Password (optional):</label>
      <input type="password" name="password" id="password">
    </div>
    <button type="submit">Add Machine</button>
  </form>
</div>

<div id="toast">Status updated</div>
<div id="spinnerOverlay"><div class="spinner"></div></div>
<script>
let servicesData = {};
let portsData = {};
let refreshTimer = null;
let currentMainTab = 'services';
let currentSubtab = {
  services: 'LOCAL',
  ports: 'LOCAL'
};

function openMainTab(evt, tab) {
  document.querySelectorAll('.tablink').forEach(btn => btn.classList.remove('active'));
  evt.currentTarget.classList.add('active');
  currentMainTab = tab;

  document.getElementById('services-tabcontent').style.display = tab === 'services' ? 'block' : 'none';
  document.getElementById('services-subtabs').style.display = tab === 'services' ? 'flex' : 'none';

  document.getElementById('ports-tabcontent').style.display = tab === 'ports' ? 'block' : 'none';
  document.getElementById('ports-subtabs').style.display = tab === 'ports' ? 'flex' : 'none';

  document.getElementById('addMachine').style.display = tab === 'addMachine' ? 'block' : 'none';

  // ✅ Fetch ports only when entering the ports tab for the first time
  if (tab === 'ports' && Object.keys(portsData).length === 0) {
  showSpinner();
  fetch('/api/unified')
    .then(res => res.json())
    .then(data => {
      portsData = Object.fromEntries(data.ports.map(n => [n.node, n]));
      renderSubtabs('ports', Object.keys(portsData));
      switchSubtab('ports', currentSubtab.ports || 'LOCAL');
      updateTimestamp(data.timestamp);
      hideSpinner();
    })
    .catch(err => {
      showToast("⚠ Failed to fetch ports");
      hideSpinner();
      });
  }
}

function switchSubtab(type, nodeName) {
  currentSubtab[type] = nodeName;

  document.querySelectorAll(`#${type}-subtabs button`).forEach(btn => btn.classList.remove('active'));
  document.getElementById(`${type}-subtab-${nodeName}`)?.classList.add('active');

  const tabcontent = document.getElementById(`${type}-tabcontent`);
  tabcontent.innerHTML = '';

  if (type === 'services') {
    renderServicesPanel(nodeName);
  } else if (type === 'ports') {
    renderPortsPanel(nodeName);
  }

  // Delay filter application until table rows are fully added
  requestAnimationFrame(applyFilters);
}


function renderSubtabs(type, nodeList) {
  const subtabs = document.getElementById(`${type}-subtabs`);
  subtabs.innerHTML = '';
  nodeList.forEach(name => {
    const btn = document.createElement('button');
    btn.textContent = name;
    btn.id = `${type}-subtab-${name}`;
    btn.onclick = () => switchSubtab(type, name);
    if (name === currentSubtab[type]) btn.classList.add('active');
    subtabs.appendChild(btn);
  });
}

function renderServicesPanel(name) {
  const tab = document.getElementById('services-tabcontent');
  const node = servicesData[name];
  if (!node) return;
  const wrapper = document.createElement('div');
  wrapper.className = 'table-wrapper';

  const table = document.createElement('table');
  table.innerHTML = `
    <thead>
      <tr><th>Name</th><th>Load</th><th>Active</th><th>Sub</th><th>Actions</th></tr>
    </thead>`;
  const tbody = document.createElement('tbody');

  node.services.forEach(service => {
    const tr = document.createElement('tr');
    if (service.active === 'failed') tr.classList.add('failed');
    tr.innerHTML = `
      <td>${service.name}</td>
      <td>${service.load}</td>
      <td class="status-${service.active}">${service.active}</td>
      <td>${service.sub}</td>
      <td>
        <form method="post" action="/action" style="display:inline;">
          <input type="hidden" name="host" value="${name}">
          <input type="hidden" name="service" value="${service.name}">
          <button class="button" name="action" value="restart">Restart</button>
          <button class="button" name="action" value="stop">Stop</button>
          <button class="button" name="action" value="start">Start</button>
        </form>
        <button class="button" onclick="viewLogs('${name}', '${service.name}')">Logs</button>
      </td>`;
    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  wrapper.appendChild(table);
  tab.appendChild(wrapper);
}

function renderPortsPanel(name) {
  const tab = document.getElementById('ports-tabcontent');
  const node = portsData[name];
  if (!node) return;
  const wrapper = document.createElement('div');
  wrapper.className = 'table-wrapper';

  const table = document.createElement('table');
  table.innerHTML = `
    <thead>
      <tr><th>Protocol</th><th>Port</th><th>Process</th><th>PID</th></tr>
    </thead>`;
  const tbody = document.createElement('tbody');

  node.ports.forEach(port => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${port.protocol}</td>
      <td>${port.port}</td>
      <td>${port.process}</td>
      <td>${port.pid}</td>`;
    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  wrapper.appendChild(table);
  tab.appendChild(wrapper);
}

function fetchData() {
  showSpinner();
  fetch('/api/unified')
    .then(res => res.json())
    .then(data => {
      if (!data.data) throw new Error("Invalid response structure");

      servicesData = Object.fromEntries(data.data.map(n => [n.node, n]));
      portsData = Object.fromEntries(data.data.map(n => [n.node, n]));

      const nodeNames = Object.keys(servicesData);
      renderSubtabs('services', nodeNames);
      renderSubtabs('ports', nodeNames);

      switchSubtab('services', currentSubtab.services);
      switchSubtab('ports', currentSubtab.ports);

      updateTimestamp(data.timestamp);
      document.getElementById("loadingMessage").style.display = "none";
      hideSpinner();
      scheduleRefresh();
    })
    .catch(err => {
      showToast("⚠ Failed to fetch data: " + err);
      hideSpinner();
    });
}

function manualRefresh() {
  showSpinner();
  fetch('/api/unified')
    .then(res => res.json())
    .then(data => {
      if (!data.data) throw new Error("Invalid response structure");

      servicesData = Object.fromEntries(data.data.map(n => [n.node, n]));
      portsData = Object.fromEntries(data.data.map(n => [n.node, n]));

      const nodeNames = Object.keys(servicesData);
      renderSubtabs('services', nodeNames);
      renderSubtabs('ports', nodeNames);

      switchSubtab(currentMainTab, currentSubtab[currentMainTab]);
      updateTimestamp(data.timestamp);
      hideSpinner();
    })
    .catch(err => {
      showToast("⚠ Manual refresh failed: " + err);
      hideSpinner();
    });
}

function scheduleRefresh(reset = false) {
  const auto = document.getElementById("autoRefreshToggle").checked;
  const interval = Math.max(
    60000,
    Math.min(300000, parseInt(document.getElementById("refreshInterval").value || "60000"))
  );

  // Always clear the existing timer
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }

  if (auto && currentMainTab === 'services') {
    refreshTimer = setTimeout(() => fetchData(), interval);
    if (reset) showToast(`🔁 Auto-refresh set to ${interval / 60000} min`);
  } else if (reset) {
    showToast("⏹ Auto-refresh is off");
  }
}

// ✅ Enable auto-refresh on first load
document.getElementById("autoRefreshToggle").checked = true;
fetchData();

// ⏹ Disable auto-refresh after 5 seconds
setTimeout(() => {
  document.getElementById("autoRefreshToggle").checked = false;
  scheduleRefresh(); // Cancel the timer if running
  showToast("⏹ Auto-refresh disabled after first load");
}, 5000);

// ✅ Add listener once
document.getElementById("autoRefreshToggle").addEventListener("change", () => {
  scheduleRefresh(true);  // Reset or cancel the timer when toggle changes
});

function applyFilters() {
  const statusFilter = document.getElementById("statusFilter")?.value || "all";
  const tabType = currentMainTab;
  const tableWrapper = document.getElementById(`${tabType}-tabcontent`);
  if (!tableWrapper) return;

  tableWrapper.querySelectorAll("tbody tr").forEach(row => {
    if (tabType === 'services') {
      const status = row.querySelector('td:nth-child(3)')?.textContent?.trim()?.toLowerCase();
      row.style.display = (statusFilter === 'all' || status === statusFilter) ? '' : 'none';
    } else if (tabType === 'ports') {
      const proto = row.querySelector('td:nth-child(1)')?.textContent?.trim()?.toLowerCase();
      row.style.display = (statusFilter === 'all' || proto === statusFilter) ? '' : 'none';
    }
  });
}

function updateTimestamp(ts) {
  const span = document.getElementById("lastUpdated");
  if (!ts) return span.innerText = "Last updated: --:--:--";
  const date = new Date(ts * 1000);
  span.innerText = "Last updated: " + date.toLocaleString();
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.style.display = "block";
  toast.style.opacity = 1;
  setTimeout(() => {
    toast.style.opacity = 0;
    setTimeout(() => toast.style.display = "none", 1000);
  }, 4000);
}

function showSpinner() {
  document.getElementById("spinnerOverlay").style.display = "flex";
}
function hideSpinner() {
  document.getElementById("spinnerOverlay").style.display = "none";
}

let liveLogTimer = null;
let currentLogHost = null;
let currentLogService = null;
let isLive = false;
let previousLogLines = [];  // ✅ must be an array

function viewLogs(host, service) {
  currentLogHost = host;
  currentLogService = service;
  isLive = false;
  previousLogLines = [];
  document.getElementById("liveLogBtn").textContent = "▶ Live Logs";
  showSpinner();
  fetchLogs(false);
}

function fetchLogs(follow) {
  fetch("/logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host: currentLogHost, service: currentLogService, follow })
  })
  .then(res => res.json())
  .then(result => {
    if (result.success) {
      const pre = document.getElementById("logContent");
      const newLines = result.logs
	  .trim()
	  .split("\n")
	  .filter(line => !/^-- Logs begin at .* --$/.test(line));  // 🔥 remove journal headers

      if (follow) {
        const freshLines = newLines.filter(line => !previousLogLines.includes(line));
        if (freshLines.length > 0) {
          pre.textContent += (pre.textContent.endsWith("\n") ? "" : "\n") + freshLines.join("\n");
          pre.scrollTop = pre.scrollHeight;
          previousLogLines = previousLogLines.concat(freshLines).slice(-200);
        }
      } else {
        pre.textContent = result.logs;
        pre.scrollTop = pre.scrollHeight;
        previousLogLines = newLines.slice(-200);
        document.getElementById("logModal").style.display = "block";
      }
    } else {
      showToast("❌ Failed to fetch logs: " + result.message);
    }
  })
  .catch(err => {
    showToast("❌ Error fetching logs: " + err);
  });
}

function toggleLiveLogs() {
  if (!isLive) {
    isLive = true;
    document.getElementById("liveLogBtn").textContent = "⏹ Stop";
    liveLogTimer = setInterval(() => fetchLogs(true), 2000);
  } else {
    isLive = false;
    document.getElementById("liveLogBtn").textContent = "▶ Live Logs";
    clearInterval(liveLogTimer);
  }
}

function closeLogModal() {
  document.getElementById("logModal").style.display = "none";

  // Clear the live log interval if it exists
  if (liveLogTimer) {
    clearInterval(liveLogTimer);
    liveLogTimer = null;
  }

  // Reset live state
  isLive = false;
  document.getElementById("liveLogBtn").textContent = "▶ Live Logs";

  // ✅ Also hide spinner if it’s still running
  hideSpinner();
}

function downloadLogs() {
  const blob = new Blob([document.getElementById("logContent").textContent], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${currentLogService || "service"}.log`;
  a.click();
}

function submitMachineForm() {
  const form = document.getElementById("addMachineForm");
  const data = {
    name: form.name.value.trim(),
    host: form.host.value.trim(),
    port: form.port.value.trim(),
    user: form.user.value.trim(),
    password: form.password.value
  };

  showSpinner();

  fetch("/add_node", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  .then(res => res.json())
  .then(result => {
    hideSpinner();
    if (result.success) {
      showToast("✅ Machine added!");
      form.reset();
      fetchData();  // Refresh tabs
      openMainTab({ currentTarget: document.querySelector('.tablink:first-child') }, 'services');
    } else {
      showToast("❌ " + result.message);
    }
  })
  .catch(err => {
    hideSpinner();
    showToast("❌ Error: " + err);
  });

  return false; // Prevent form submission from reloading page
}

function forceRefresh() {
  showToast("Refreshing cache...");
  fetch("/force-refresh", { method: "POST" })
    .then(res => res.json())
    .then(json => {
      showToast(json.success ? "✅ Cache refreshed" : "⚠ " + json.message);
      fetchData(currentMainTab === 'ports'); // refresh current tab
    })
    .catch(err => showToast("⚠ Refresh failed: " + err));
}

fetchData();
</script>

<!-- Modal -->
<div id="logModal" style="display:none; position:fixed; top:10%; left:10%; width:80%; height:80%; background:#111; color:#eee; border:1px solid #444; padding:20px; overflow:auto; z-index:10000;">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <h3 style="margin:0;">Service Logs</h3>
    <div>
      <button onclick="downloadLogs()" class="button">⬇ Download</button>
      <button onclick="toggleLiveLogs()" class="button" id="liveLogBtn">▶ Live Logs</button>
      <button onclick="closeLogModal()" class="button">✖ Close</button>
    </div>
  </div>
  <pre id="logContent" style="white-space:pre-wrap; background:#000; padding:10px; border:1px solid #333; height:90%; overflow:auto; margin-top:10px;"></pre>
</div>
</body>
</html>
