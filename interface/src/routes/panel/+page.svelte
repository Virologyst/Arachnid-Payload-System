<script>
  import { onMount } from 'svelte';
  import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
  } from 'recharts';

  // panel state
  let currentView = 'sensors';
  let logs = [];
  let loading = false;
  const MAX_LOGS = 1000;

  function log(message, type = 'INFO') {
    const timestamp = new Date().toLocaleTimeString();
    logs = [{ timestamp, message, type }, ...logs].slice(0, MAX_LOGS);
    console.log(`[${type}] ${message}`);
  }

  // targets
  let statusA = "unknown";
  let statusB = "unknown";
  let statusC = "unknown";

  async function fetchTargets() {
    const res = await fetch("/targets");
    const data = await res.json();
    statusA = data[0]?.type || "unknown";
    statusB = data[1]?.type || "unknown";
    statusC = data[2]?.type || "unknown";
  }

  async function fetchBackendLogs() {
    const res = await fetch('/logs');
    const backend = await res.json();

    const mapped = backend.map(l => {
      const parts = l.match(/^(.*?) \[(.*?)\] (.*)$/);
      if (!parts) return { timestamp: new Date().toLocaleTimeString(), type: "INFO", message: l };
      return { timestamp: parts[1], type: parts[2], message: parts[3] };
    });

    logs = [...mapped, ...logs].slice(0, MAX_LOGS);
  }

  // graph data
  let historicData = [];

  async function fetchHistory() {
    const res = await fetch('/enviro/history');
    historicData = await res.json();
  }

  function loadPanel(view) {
    currentView = view;
  }

  async function updateDevice() {
    loading = true;
    await fetch('/update', { method: 'POST' });
    setTimeout(() => loading = false, 5000);
  }

  onMount(() => {
    fetchTargets();
    fetchBackendLogs();
    fetchHistory();

    setInterval(fetchBackendLogs, 4000);
    setInterval(fetchHistory, 4000);
  });
</script>


<style>
    @import '../../../styling.css';

    .panel-container {
        padding: 20px;
    }
</style>

<h1 style="text-align: center; margin-top: 20px;">Flight Data</h1>

<div class="panel-container">
    <div class="tab-buttons">
        <button on:click={() => loadPanel('sensors')}>Graph</button>
        <button on:click={() => loadPanel('logs')}>Logs</button>
        <button on:click={() => loadPanel('targets')}>Targets</button>
        <button on:click={() => loadPanel('system')}>System</button>
    </div>

    <div id="dynamicPanel">

  {#if currentView === 'sensors'}
    <div class="panel-sensors">
      <h2>Sensor Data (Last 10 Minutes)</h2>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={historicData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" tick={{ fontSize: 8 }} />
          <YAxis />
          <Tooltip />
          <Area type="monotone" dataKey="temperature" stroke="#ff7300" fill="#ff7300" fillOpacity={0.3} />
          <Area type="monotone" dataKey="humidity" stroke="#00c3ff" fill="#00c3ff" fillOpacity={0.3} />
          <Area type="monotone" dataKey="pressure" stroke="#8884d8" fill="#8884d8" fillOpacity={0.2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>

        {:else if currentView === 'logs'}
            <div class="logs-panel">
                <h2>Live Logs</h2>
                <div class="log-feed">
                {#each logs as logItem}
                    <div class="log-entry {logItem.type.toLowerCase()}">
                        <span class="log-time">[{logItem.timestamp}]</span>
                        <span class="log-type">[{logItem.type}]</span>
                        <span class="log-msg">{logItem.message}</span>
                    </div>
                {/each}
                </div>
            </div>

        {:else if currentView === 'targets'}
            <div class="targets-panel">
                <h2>Targets</h2>
                <div class="targets-grid">
                    <div class="target-card"><h3>A</h3><p>{statusA}</p></div>
                    <div class="target-card"><h3>B</h3><p>{statusB}</p></div>
                    <div class="target-card"><h3>C</h3><p>{statusC}</p></div>
                </div>
            </div>

        {:else if currentView === 'system'}
            <div>
                <h2>System Controls</h2>
                <button on:click={updateDevice} disabled={loading} class="update-btn">
                    🔄 Update & Restart
                </button>
                {#if loading}
                    <div id="loading">
                        <img src="loading.gif" alt="Loading..." style="width: 50px;">
                        <p>Updating... please wait</p>
                    </div>
                {/if}
            </div>
        {/if}
    </div>
</div>

