<script>
    import { onMount } from 'svelte';

    let backendLogs = [];
    let status = "unknown";
    let value = "unknown";

    async function fetchTargets() {
        try {
            const res = await fetch("/targets");
            const data = await res.json();

            // Log every key/value or just a summary
            if (Array.isArray(data)) {
                data.forEach(target => {
                    log(`Target detected: ${JSON.stringify(target)}`, 'TARGET');
                });
            } else if (typeof data === 'object') {
                for (const [k, v] of Object.entries(data)) {
                    log(`${k}: ${v}`, 'TARGET');
                }
            } else {
                log(`Target update: ${data}`, 'TARGET');
            }
        } catch (err) {
            log(`Target fetch error: ${err}`, 'ERROR');
        }
    }

    async function fetchBackendLogs() {
        const res = await fetch('/logs');
        // backendLogs = await res.json();
        const data = await res.json();
        // Merge backend logs into your local list
        logs = data.concat(logs).slice(-MAX_LOGS).reverse();
    }

    let isMobile = false;

    function checkMobile() {
        console.log('isMobile: ', isMobile)
        isMobile = window.innerWidth <= 768;
    }

    let logs = [];
    const MAX_LOGS = 1000;

    // function log(message, type = 'INFO') {
    //     const timestamp = new Date().toLocaleTimeString();
    //     logs = [{ timestamp, message, type }, ...logs].slice(0, MAX_LOGS);
    //     // console.log(`[${type}] ${message}`);
    // }

    function log(message, type = 'INFO') {
        const timestamp = new Date().toLocaleTimeString();
        const entry = { timestamp, message, type };

        // Keep local list up to date
        logs = [entry, ...logs].slice(0, MAX_LOGS);

        // Push to backend for persistence
        fetch('/logs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(entry)
        }).catch(() => {});
    }

     // Filters
    let fromTime = '';
    let toTime = '';

    $: filteredLogs = logs.filter(l => {
    if (!fromTime && !toTime) return true;

    const [h, m, s] = l.timestamp.split(':').map(Number);
    const logDate = new Date();
    logDate.setHours(h, m, s || 0);

    if (fromTime) {
      const [fh, fm] = fromTime.split(':').map(Number);
      const fromDate = new Date();
      fromDate.setHours(fh, fm, 0);
      if (logDate < fromDate) return false;
    }

    if (toTime) {
      const [th, tm] = toTime.split(':').map(Number);
      const toDate = new Date();
      toDate.setHours(th, tm, 59);
      if (logDate > toDate) return false;
    }

    return true;
    });

    // eslint-disable-next-line no-unused-vars
    let historicData = [];

    async function fetchHistory() {
        const res = await fetch('/enviro/history');
        historicData = await res.json();
    }

    let thumbnails = [];
    let modalImage = null;

    async function fetchThumbnails() {
        const res = await fetch('/images');
        const data = await res.json();
        thumbnails = data.images;
    }

    async function captureImage() {
        await fetch('/capture', { method: 'POST' });
        await fetchThumbnails(); // refresh sidebar
    }

    function openModal(filename) {
        modalImage = `/images/${filename}`;
    }

    async function deleteImage(filename) {
        await fetch(`/images/delete/${filename}`, { method: 'DELETE' });
        modalImage = null;
        await fetchThumbnails();
    }

    let loading = false;
    let currentView = 'logs';
    let enviro = {};
    let mobileMenuOpen = false;
    let lastEnviro = {};
    let panelContent = '';

    async function fetchEnviro() {
        // const res = await fetch('/enviro');
        // enviro = await res.json();
        updateBars();
        const res = await fetch('/enviro');
        const newEnviro = await res.json();

        // 🔥 log changes
        for (const key in newEnviro) {
            if (newEnviro[key] !== lastEnviro[key]) {
                log(`${key} changed to ${newEnviro[key]}`, 'DATA');
            }
        }
        lastEnviro = { ...newEnviro };
        enviro = newEnviro;
    }

    let bars = [
        // { label: 'CO₂', key: 'co2', value: 0, max: 1000, color: 'green' },
        // { label: 'Ammonia', key: 'ammonia', value: 0, max: 1000, color: 'green' },
        { label: 'Temp', key: 'temperature', value: 0, max: 100, color: 'green' },
        { label: 'Humidity', key: 'humidity', value: 0, max: 100, color: 'green' },
        { label: 'NH3', key: 'nh3', value: 0, max: 2000, color: 'green' },
        { label: 'Light', key: 'lux', value: 0, max: 500, color: 'green' }
    ];

    function updateBars() {
        bars = bars.map(bar => {
            // get value from enviro JSON (default to 0 if missing)
            const newValue = enviro[bar.key] || 0;
            const percent = Math.min((newValue / bar.max) * 100, 100);

            // traffic light logic
            let newColor = 'green';
            if (percent > 50 && percent <= 90) newColor = 'orange';
            if (percent > 90) newColor = 'red';

            return { ...bar, value: percent, color: newColor };
        });
    }

    async function updateDevice() {
        log('Update triggered via UI', 'ACTION');
        loading = true;
        await fetch('/update', { method: 'POST' });
        setTimeout(() => {
            loading = false;
            log('Device restarted successfully', 'INFO');
            window.location.reload();
        }, 5000);
    }

    async function loadPanel(view) {
        currentView = view;
        const res = await fetch(`/panel/${view}`);
        panelContent = await res.text();
    }

    onMount(() => {

        log('App initialized', 'INFO');
        fetchBackendLogs();
        fetchHistory();
        setInterval(fetchHistory, 4000);
        fetchEnviro();
        setInterval(fetchEnviro, 4000);
        fetchTargets();
        setInterval(fetchTargets, 4000);
        fetchThumbnails();
        setInterval(fetchThumbnails, 4000); // 4s
        checkMobile();
        fetchTargets();
        window.addEventListener("resize", checkMobile);
        return () => window.removeEventListener("resize", checkMobile);
    });

    function toggleMobileMenu() {
        mobileMenuOpen = !mobileMenuOpen;
    }

    async function runDrill() {
        try {
            const res = await fetch('/drill', { method: 'POST' });
            const data = await res.json();
            log(`Drill: ${data.message}`, data.status === 'success' ? 'ACTION' : 'ERROR');
        } catch (e) {
            log(`Drill error: ${e}`, 'ERROR');
        }
    }


</script>

<style>

    @import '../../styling.css';

</style>

<h1 style="text-align: center; margin-bottom: -70px;">Dashboard</h1>

<main>

    <div class="sidebar">
        {#each thumbnails as thumb}
            <img src={`/images/${thumb}`} alt="Thumbnail" on:click={() => openModal(thumb)}>
        {/each}
    </div>

    <div class="content">
        <div class="top-row">

            <div class="camera-pane">
<!--                <img src="/live_feed" alt="Live Feed">-->
                <img src="/video_feed" alt="Target Feed">
                <div class="sensor-overlay">
                    🌡 {enviro.temperature}°C | 💧 {enviro.humidity}% | 📈 {enviro.pressure}hPa
                </div>
                <div class="capture-overlay">
                    <button type="button" class="drill-btn" on:click={runDrill}>Start Drill</button>
                    <button class="capture-btn" on:click={captureImage}>📸 Capture Image</button>
                </div>
            </div>

            <!-- Dynamic Panel -->
            <div class="panel-pane">

                <div class="tab-buttons">
<!--                    <button on:click={() => loadPanel('sensors')}>Graph</button>-->
                    <button on:click={() => loadPanel('logs')}>Logs</button>
<!--                    <button on:click={() => loadPanel('targets')}>Targets</button>-->
                    <button on:click={() => loadPanel('system')}>System</button>
                </div>

                <div id="dynamicPanel">
                    {#if currentView === 'sensors'}
                        <div class="panel-sensors">
                            <h2>Sensor Panel</h2>
                        </div>

                    {:else if currentView === 'logs'}

                        <div class="logs-panel">
                            <h2>Live Logs</h2>
                            <div class="log-feed">

                                {#each filteredLogs as logItem}
                                    <div class="log-entry {logItem.type.toLowerCase()}">
                                        <span class="log-time">[{logItem.timestamp}]</span>
                                        <span class="log-type"
                                              style="color: {logItem.type === 'TARGET' ? 'red' : ''}">
                                              [{logItem.type}]
                                        </span>
                                        <span class="log-msg">{logItem.message}</span>
                                    </div>
                                {/each}

                            </div>
                        </div>

                        <div class="filter-bar">
                          <label>From:</label>
                          <input type="time" bind:value={fromTime}>
                          <label>To:</label>
                          <input type="time" bind:value={toTime}>
                        </div>

                    {:else if currentView === 'targets'}
                      <div class="targets-panel">

                      </div>
                    {:else if currentView === 'system'}
                        <div>
                            <h2>System Controls</h2>
                           <button on:click={updateDevice} disabled={loading} class="update-btn">
                                Update & Restart
                            </button>

                            <h2>LCD Controls</h2>
                            <div class="lcd-controls">
                                <button class="update-btn" on:click={() => fetch('/lcd/on', {method: 'POST'})}>Turn on LCD</button>
                                <button class="update-btn" on:click={() => fetch('/lcd/off', {method: 'POST'})}>Turn off LCD</button>
                                <button class="update-btn" on:click={() => fetch('/lcd/show/ip', {method: 'POST'})}>Show IP Address</button>
                                <button class="update-btn" on:click={() => fetch('/lcd/loop', {method: 'POST'})}>Show Sensor Data</button>
                            </div>

                            {#if loading}
                                <div id="loading">
                                    <img src="loading.gif" alt="Loading..." style="width: 50px;">
                                    <p>Updating... please wait</p>
                                </div>
                            {/if}
                        </div>
                    {/if}
                </div>

                <div class="enviro-card">
                    <h2>Enviro+ Live Data</h2>
                        <ul class="readings-list">
                            <li>🌡 Temperature: {enviro.temperature} °C</li>
                            <li>💧 Humidity: {enviro.humidity} %</li>
                            <li>📈 Pressure: {enviro.pressure} hPa</li>
                            <li>🟠 Oxidising Gas: {enviro.oxidising} kΩ</li>
                            <li>🔵 Reducing Gas: {enviro.reducing} kΩ</li>
                            <li>🟢 NH3: {enviro.nh3} kΩ</li>
                            <li>💡 Light: {enviro.lux} lux</li>
                            <li>📏 Proximity: {enviro.proximity}</li>
                        </ul>
                </div>

            </div>
        </div>

        {#if isMobile}

            <div class="bottom-row">

                <div class="readings-table">
                    <table border="1" cellpadding="5">
                        <thead>
                            <tr><th>Target</th><td class="status">Gauge:</td></tr>
                            <tr><th>Status</th><td class="status">{status}</td></tr>
                            <tr><th>Value</th><td class="status">{value}</td></tr>
                        </thead>
                    </table>
                </div>

                <div class="enviro-card-mobile">
<!--                  <h3>Enviro+ Data</h3>-->
                      <ul class="readings-list">
                        <li>🌡 Temperature: {enviro.temperature} °C</li>
                        <li>💧 Humidity: {enviro.humidity} %</li>
                        <li>📈 Pressure: {enviro.pressure} hPa</li>
                        <li>🟠 Oxidising Gas: {enviro.oxidising} kΩ</li>
                        <li>🔵 Reducing Gas: {enviro.reducing} kΩ</li>
                        <li>🟢 NH3: {enviro.nh3} kΩ</li>
                        <li>💡 Light: {enviro.lux} lux</li>
                        <li>📏 Proximity: {enviro.proximity}</li>
                      </ul>
                    </div>
                  </div>

                <div class="status-bars">
                    {#each bars as bar}
                        <div class="status-bar">
                            <div class="bar">
                                <div class="bar-fill" style="height: {bar.value}%; background-color: {bar.color};"></div>
                            </div>
                            <div class="bar-label">{bar.label}</div>
                        </div>
                    {/each}
                </div>

            {:else}

                <div class="bottom-row">
                    <div class="readings-table">
                        <table border="1" cellpadding="5">
                            <thead>
                                <tr><th>Target</th><th>Status</th><th>Reading</th></tr>
                            </thead>
                            <tbody>
                                <tr><td class="label">Gauge:</td><td class="status">{status}</td><td class="status">{value}</td></tr>
                            </tbody>
                        </table>
                    </div>

                    <div class="status-bars">
                        {#each bars as bar}
                            <div class="status-bar">
                                <div class="bar">
                                    <div class="bar-fill" style="height: {bar.value}%; background-color: {bar.color};"></div>
                                </div>
                                <div class="bar-label">{bar.label}</div>
                            </div>
                        {/each}
                    </div>
                </div>

            {/if}

        {#if modalImage}
            <div class="modal">
                <div class="modal-content">
                    <img src={modalImage} alt="Full Image">
                    <button class="delete-btn" on:click={() => deleteImage(modalImage.split('/').pop())}>🗑 Delete</button>
                    <button class="close-btn" on:click={() => modalImage = null}>Close</button>
                </div>
            </div>
            {/if}
    </div>
</main>

