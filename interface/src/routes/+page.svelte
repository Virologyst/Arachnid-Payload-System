<script>
    import { onMount } from 'svelte';

    let backendLogs = [];
    let statusA = "unknown";
    let statusB = "unknown";
    let statusC = "unknown";

    async function fetchBackendLogs() {
        const res = await fetch('/logs');
        backendLogs = await res.json();
    }

    let isMobile = false;

    function checkMobile() {
        isMobile = window.innerWidth <= 768;
    }

    let logs = [];
    const MAX_LOGS = 1000;

    function log(message, type = 'INFO') {
        const timestamp = new Date().toLocaleTimeString();
        logs = [{ timestamp, message, type }, ...logs].slice(0, MAX_LOGS);
        console.log(`[${type}] ${message}`);
    }

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
    let panelContent = '';
    let currentView = 'sensors';
    let enviro = {};
    let mobileMenuOpen = false;
    let lastEnviro = {};

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
        { label: 'Ammonia', key: 'ammonia', value: 0, max: 1000, color: 'green' },
        { label: 'Temp', key: 'temperature', value: 0, max: 100, color: 'green' },
        { label: 'Humidity', key: 'humidity', value: 0, max: 100, color: 'green' },
        { label: 'NH3', key: 'nh3', value: 0, max: 300, color: 'green' },
        { label: 'Light', key: 'lux', value: 0, max: 1000, color: 'green' }
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
        fetchHistory();
        setInterval(fetchHistory, 4000);
        loadPanel('sensors');
        fetchEnviro();
        setInterval(fetchEnviro, 4000);
        fetchThumbnails();
        setInterval(fetchThumbnails, 4000); // 4s
        fetchBackendLogs();
        checkMobile();
        window.addEventListener("resize", checkMobile);
        return () => window.removeEventListener("resize", checkMobile);
    });

    function toggleMobileMenu() {
        mobileMenuOpen = !mobileMenuOpen;
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
                <img src="/video_feed" alt="Live Feed">
                <div class="sensor-overlay">
                    🌡 {enviro.temperature}°C | 💧 {enviro.humidity}% | 📈 {enviro.pressure}hPa
                </div>
                <div class="capture-overlay">
                    <button class="capture-btn" on:click={captureImage}>📸 Capture Image</button>
                </div>
            </div>

            <!-- Dynamic Panel -->
            <div class="panel-pane">

                <div class="tab-buttons">
                    <button on:click={() => loadPanel('sensors')}>Sensors</button>
                    <button on:click={() => loadPanel('logs')}>Logs</button>
                    <button on:click={() => loadPanel('targets')}>Targets</button>
                    <button on:click={() => loadPanel('system')}>System</button>
                </div>

                <div id="dynamicPanel">
                    {#if currentView === 'sensors'}
                        <div class="panel-sensors">
                            <h2>Sensor Data (Graph Connected to Database)</h2>
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
                        <div><h2>Targets</h2><p>No targets detected yet.</p></div>
                    {:else if currentView === 'system'}
                        <div>
                            <h2>System Controls</h2>
                           <button on:click={updateDevice} disabled={loading} class="update-btn">
                                Update & Restart
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

<!--                <div class="sensor-graph">-->
<!--                    <h3>Historic Sensor Data</h3>-->
<!--                    <Line-->
<!--                        data={{-->
<!--                            labels: historicData.map(d => new Date(d.timestamp).toLocaleTimeString()),-->
<!--                            datasets: [-->
<!--                                {-->
<!--                                    label: 'Temperature (°C)',-->
<!--                                    data: historicData.map(d => d.temperature),-->
<!--                                    borderColor: 'orange',-->
<!--                                    fill: false-->
<!--                                },-->
<!--                                {-->
<!--                                    label: 'Humidity (%)',-->
<!--                                    data: historicData.map(d => d.humidity),-->
<!--                                    borderColor: 'blue',-->
<!--                                    fill: false-->
<!--                                },-->
<!--                                {-->
<!--                                    label: 'Pressure (hPa)',-->
<!--                                    data: historicData.map(d => d.pressure),-->
<!--                                    borderColor: 'purple',-->
<!--                                    fill: false-->
<!--                                }-->
<!--                            ]-->
<!--                        }}-->
<!--                        options={{-->
<!--                            responsive: true,-->
<!--                            plugins: {-->
<!--                                legend: { display: true },-->
<!--                                tooltip: { mode: 'index', intersect: false }-->
<!--                            },-->
<!--                            scales: {-->
<!--                                x: {-->
<!--                                    title: { display: true, text: 'Timestamp' }-->
<!--                                },-->
<!--                                y: {-->
<!--                                    beginAtZero: false-->
<!--                                }-->
<!--                            }-->
<!--                        }}-->
<!--                    />-->
<!--                </div>-->

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
                            <tr><th>Targets</th><th>Current Status</th></tr>
                        </thead>
                        <tbody>
                            <tr><td class="label">A:</td><td class="status">{statusA}</td></tr>
                            <tr><td class="label">B:</td><td class="status">{statusB}</td></tr>
                            <tr><td class="label">C:</td><td class="status">{statusC}</td></tr>
                        </tbody>
                    </table>
                </div>

                <div class="enviro-card-mobile">
    <!--              <h3>Enviro+ Data</h3>-->
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
                                <tr><th>🎯 Targets</th><th>Current Status</th></tr>
                            </thead>
                            <tbody>
                                <tr><td class="label">A:</td><td class="status">{statusA}</td></tr>
                                <tr><td class="label">B:</td><td class="status">{statusB}</td></tr>
                                <tr><td class="label">C:</td><td class="status">{statusC}</td></tr>
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

