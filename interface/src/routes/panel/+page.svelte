<!--<script>-->
<!--  import { onMount } from 'svelte';-->
<!--  import {-->
<!--    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer-->
<!--  } from 'recharts';-->

<!--  // panel state-->
<!--  let currentView = 'sensors';-->
<!--  let logs = [];-->
<!--  let loading = false;-->
<!--  const MAX_LOGS = 1000;-->

<!--  function log(message, type = 'INFO') {-->
<!--    const timestamp = new Date().toLocaleTimeString();-->
<!--    logs = [{ timestamp, message, type }, ...logs].slice(0, MAX_LOGS);-->
<!--    console.log(`[${type}] ${message}`);-->
<!--  }-->

<!--  // targets-->
<!--  let statusA = "unknown";-->
<!--  let statusB = "unknown";-->
<!--  let statusC = "unknown";-->

<!--  async function fetchTargets() {-->
<!--    const res = await fetch("/targets");-->
<!--    const data = await res.json();-->
<!--    statusA = data[0]?.type || "unknown";-->
<!--    statusB = data[1]?.type || "unknown";-->
<!--    statusC = data[2]?.type || "unknown";-->
<!--  }-->

<!--  async function fetchBackendLogs() {-->
<!--    const res = await fetch('/logs');-->
<!--    const backend = await res.json();-->

<!--    const mapped = backend.map(l => {-->
<!--      const parts = l.match(/^(.*?) \[(.*?)\] (.*)$/);-->
<!--      if (!parts) return { timestamp: new Date().toLocaleTimeString(), type: "INFO", message: l };-->
<!--      return { timestamp: parts[1], type: parts[2], message: parts[3] };-->
<!--    });-->

<!--    logs = [...mapped, ...logs].slice(0, MAX_LOGS);-->
<!--  }-->

<!--  // graph data-->
<!--  let historicData = [];-->

<!--  async function fetchHistory() {-->
<!--    const res = await fetch('/enviro/history');-->
<!--    historicData = await res.json();-->
<!--  }-->

<!--  function loadPanel(view) {-->
<!--    currentView = view;-->
<!--  }-->

<!--  async function updateDevice() {-->
<!--    loading = true;-->
<!--    await fetch('/update', { method: 'POST' });-->
<!--    setTimeout(() => loading = false, 5000);-->
<!--  }-->

<!--  onMount(() => {-->
<!--    fetchTargets();-->
<!--    fetchBackendLogs();-->
<!--    fetchHistory();-->

<!--    setInterval(fetchBackendLogs, 4000);-->
<!--    setInterval(fetchHistory, 4000);-->
<!--  });-->
<!--</script>-->


<!--<style>-->
<!--    @import '../../../styling.css';-->

<!--    .panel-container {-->
<!--        padding: 20px;-->
<!--    }-->
<!--</style>-->

<!--<h1 style="text-align: center; margin-top: 20px;">Flight Data</h1>-->

<!--<div class="panel-container">-->
<!--    <div class="tab-buttons">-->
<!--&lt;!&ndash;        <button on:click={() => loadPanel('sensors')}>Graph</button>&ndash;&gt;-->
<!--        <button on:click={() => loadPanel('logs')}>Logs</button>-->
<!--&lt;!&ndash;        <button on:click={() => loadPanel('targets')}>Targets</button>&ndash;&gt;-->
<!--        <button on:click={() => loadPanel('system')}>System</button>-->
<!--    </div>-->

<!--    <div id="dynamicPanel">-->

<!--        {#if currentView === 'logs'}-->
<!--            <div class="logs-panel">-->
<!--                <h2>Live Logs</h2>-->
<!--                <div class="log-feed">-->
<!--                {#each logs as logItem}-->
<!--                    <div class="log-entry {logItem.type.toLowerCase()}">-->
<!--                        <span class="log-time">[{logItem.timestamp}]</span>-->
<!--                        <span class="log-type">[{logItem.type}]</span>-->
<!--                        <span class="log-msg">{logItem.message}</span>-->
<!--                    </div>-->
<!--                {/each}-->
<!--                </div>-->
<!--            </div>-->

<!--        {:else if currentView === 'targets'}-->
<!--            -->
<!--            <div class="targets-panel">-->
<!--&lt;!&ndash;                <h2>Targets</h2>&ndash;&gt;-->
<!--&lt;!&ndash;                <div class="targets-grid">&ndash;&gt;-->
<!--&lt;!&ndash;                    <div class="target-card"><h3>A</h3><p>{statusA}</p></div>&ndash;&gt;-->
<!--&lt;!&ndash;                    <div class="target-card"><h3>B</h3><p>{statusB}</p></div>&ndash;&gt;-->
<!--&lt;!&ndash;                    <div class="target-card"><h3>C</h3><p>{statusC}</p></div>&ndash;&gt;-->
<!--&lt;!&ndash;                </div>&ndash;&gt;-->
<!--            </div>-->

<!--        {:else if currentView === 'system'}-->
<!--            <div>-->
<!--                <h2>System Controls</h2>-->
<!--                <button on:click={updateDevice} disabled={loading} class="update-btn">-->
<!--                    🔄 Update & Restart-->
<!--                </button>-->
<!--                {#if loading}-->
<!--                    <div id="loading">-->
<!--                        <img src="loading.gif" alt="Loading..." style="width: 50px;">-->
<!--                        <p>Updating... please wait</p>-->
<!--                    </div>-->
<!--                {/if}-->
<!--            </div>-->
<!--        {/if}-->
<!--    </div>-->
<!--</div>-->

