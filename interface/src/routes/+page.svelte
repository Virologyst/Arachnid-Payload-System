<script>
    import { onMount } from 'svelte';

    let loading = false;
    let panelContent = '';
    let currentView = 'sensors';
    let enviro = {};
    let mobileMenuOpen = false;

    async function fetchEnviro() {
        const res = await fetch('/enviro');
        enviro = await res.json();
    }

    async function updateDevice() {
        loading = true;
        await fetch('/update', { method: 'POST' });
        setTimeout(() => {
            loading = false;
            window.location.reload();
        }, 5000);
    }

    async function loadPanel(view) {
        currentView = view;
        const res = await fetch(`/panel/${view}`);
        panelContent = await res.text();
    }

    onMount(() => {
        loadPanel('sensors');
        fetchEnviro();
        setInterval(fetchEnviro, 4000);
    });

    function toggleMobileMenu() {
        mobileMenuOpen = !mobileMenuOpen;
    }
</script>

<style>

    @import '../../styling.css';

</style>

<header>
    <h1>EGH455: Advanced System Design - Group 5</h1>

    <nav>
        <button>Dashboard</button>
        <button>Images</button>
        <button>Sensor Data</button>
    </nav>

    <!-- HAMBURGER ICON -->
    <div class="hamburger" on:click={toggleMobileMenu}>
        <div></div>
        <div></div>
        <div></div>
    </div>
</header>

<!-- MOBILE MENU -->
<div class="mobile-menu {mobileMenuOpen ? 'open' : ''}">
    <button on:click={() => mobileMenuOpen = false}>📺 Live Feed</button>
    <button on:click={() => mobileMenuOpen = false}>📸 Images</button>
    <button on:click={() => mobileMenuOpen = false}>📊 Sensor Data</button>
</div>

<main>
    <div class="sidebar">
        <img src="images/thumb1.jpg" alt="Thumbnail">
        <img src="images/thumb1.jpg" alt="Thumbnail">
        <img src="images/thumb1.jpg" alt="Thumbnail">
    </div>

    <div class="content">
        <div class="top-row">
            <!-- Live Camera Feed -->
            <div class="camera-pane">
                <img src="/video_feed" alt="Live Feed">
                <div class="sensor-overlay">
                    🌡 {enviro.temperature}°C | 💧 {enviro.humidity}% | 📈 {enviro.pressure}hPa
                </div>
            </div>

            <!-- Dynamic Panel -->
            <div class="panel-pane">
                <div class="tab-buttons">
                    <button on:click={() => loadPanel('sensors')}>📊 Sensors</button>
                    <button on:click={() => loadPanel('logs')}>📜 Logs</button>
                    <button on:click={() => loadPanel('targets')}>🎯 Targets</button>
                    <button on:click={() => loadPanel('system')}>⚙ System</button>
                </div>

                <div id="dynamicPanel">
                    {@html panelContent}
                </div>

                <div class="enviro-card">
                    <h2>Enviro+ Live Data</h2>
                    <ul>
                        <li>Temp: {enviro.temperature} °C</li>
                        <li>Humidity: {enviro.humidity} %</li>
                        <li>Pressure: {enviro.pressure} hPa</li>
                        <li>Oxidising: {enviro.oxidising} kΩ</li>
                        <li>Reducing: {enviro.reducing} kΩ</li>
                        <li>Ammonia: {enviro.nh3} kΩ</li>
                        <li>Light: {enviro.lux} lux</li>
                        <li>Proximity: {enviro.proximity}</li>
                    </ul>
                </div>
            </div>
        </div>

        <div class="bottom-row">
            <div class="readings-table">
                <table border="1" cellpadding="5">
                    <thead>
                        <tr><th>Targets</th><th>Average Readings</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>A:</td><td></td></tr>
                        <tr><td>B:</td><td></td></tr>
                        <tr><td>C:</td><td></td></tr>
                    </tbody>
                </table>
            </div>

            <div class="status-bars">
                <div>
                    <div class="bar"><div class="bar-fill" style="height: 60%;"></div></div>
                    <div class="bar-label">CO₂</div>
                </div>
                <div>
                    <div class="bar"><div class="bar-fill" style="height: 45%;"></div></div>
                    <div class="bar-label">Temp</div>
                </div>
                <div>
                    <div class="bar"><div class="bar-fill" style="height: 30%;"></div></div>
                    <div class="bar-label">Humid</div>
                </div>
            </div>
        </div>

        <!-- Update Button -->
        <button on:click={updateDevice} disabled={loading} class="update-btn">
            🔄 Update & Restart
        </button>

        {#if loading}
            <div id="loading">
                <img src="images/loading.gif" alt="Loading..." style="width: 50px;">
                <p>Updating... please wait</p>
            </div>
        {/if}
    </div>
</main>


<!--<script>-->
<!--    import { onMount } from 'svelte';-->

<!--    let loading = false;-->
<!--    let panelContent = '';-->
<!--    let currentView = 'sensors';-->
<!--    let enviro = {};-->

<!--    async function fetchEnviro() {-->
<!--        const res = await fetch('/enviro');-->
<!--        enviro = await res.json();-->
<!--    }-->

<!--    // Deploy/update function-->
<!--    async function updateDevice() {-->
<!--        loading = true;-->
<!--        await fetch('/update', { method: 'POST' });-->
<!--        setTimeout(() => {-->
<!--            loading = false;-->
<!--            window.location.reload();-->
<!--        }, 5000);-->
<!--    }-->

<!--    // Load dashboard panel dynamically-->
<!--    async function loadPanel(view) {-->
<!--        currentView = view;-->
<!--        const res = await fetch(`/panel/${view}`);-->
<!--        panelContent = await res.text();-->
<!--    }-->

<!--    // Load default tab on page load-->
<!--    onMount(() => {-->
<!--        loadPanel('sensors');-->
<!--        fetchEnviro();-->
<!--        setInterval(fetchEnviro, 4000);  // refresh every 4 seconds-->
<!--    });-->
<!--</script>-->

<!--<style>-->

<!--    @import '../../style.css';-->

<!--</style>-->

<!--<header>-->
<!--    <h1>EGH455 - Team 5</h1>-->
<!--</header>-->

<!--<main>-->
<!--    <div class="sidebar">-->
<!--        <img src="images/thumb1.jpg" alt="Thumbnail">-->
<!--        <img src="images/thumb1.jpg" alt="Thumbnail">-->
<!--        <img src="images/thumb1.jpg" alt="Thumbnail">-->
<!--    </div>-->

<!--    <div class="content">-->
<!--        <div class="top-row">-->
<!--            &lt;!&ndash; Live Camera Feed &ndash;&gt;-->
<!--            <div class="camera-pane">-->
<!--                <img src="/video_feed" alt="Live Feed">-->
<!--            </div>-->

<!--            &lt;!&ndash; Dynamic Panel &ndash;&gt;-->
<!--            <div class="panel-pane">-->
<!--                <div class="tab-buttons">-->
<!--                    <button on:click={() => loadPanel('sensors')}>📊 Sensor Data</button>-->
<!--                    <button on:click={() => loadPanel('logs')}>📜 Logs</button>-->
<!--                    <button on:click={() => loadPanel('targets')}>🎯 Targets</button>-->
<!--                    <button on:click={() => loadPanel('system')}>⚙ System</button>-->
<!--                </div>-->

<!--                <div id="dynamicPanel" bind:this={dynamicPanel}>-->
<!--                    {@html panelContent}-->
<!--                </div>-->

<!--                <div class="enviro-card">-->
<!--                    <h2>Enviro+ Live Data</h2>-->
<!--                    <ul>-->
<!--                        <li>Temp: {enviro.temperature} °C</li>-->
<!--                        <li>Humidity: {enviro.humidity} %</li>-->
<!--                        <li>Pressure: {enviro.pressure} hPa</li>-->
<!--                        <li>Oxidising: {enviro.oxidising} kΩ</li>-->
<!--                        <li>Reducing: {enviro.reducing} kΩ</li>-->
<!--                        <li>Ammonia: {enviro.nh3} kΩ</li>-->
<!--                        <li>Light: {enviro.lux} lux</li>-->
<!--                        <li>Proximity: {enviro.proximity}</li>-->
<!--                    </ul>-->
<!--                </div>-->

<!--            </div>-->
<!--        </div>-->

<!--        <div class="bottom-row">-->

<!--            <div class="readings-table">-->
<!--                <table border="1" cellpadding="5">-->
<!--                    <thead>-->
<!--                        <tr><th>Targets</th><th>Average Readings</th></tr>-->
<!--                    </thead>-->
<!--                    <tbody>-->
<!--                        <tr><td>A:</td><td>- - -</td></tr>-->
<!--                        <tr><td>B:</td><td>380 ppm, 22.3°C, 14%</td></tr>-->
<!--                        <tr><td>C:</td><td>- - -</td></tr>-->
<!--                    </tbody>-->
<!--                </table>-->
<!--            </div>-->


<!--            <div class="status-bars">-->
<!--                <div>-->
<!--                    <div class="bar"><div class="bar-fill" style="height: 60%;"></div></div>-->
<!--                    <div class="bar-label">CO₂</div>-->
<!--                </div>-->
<!--                <div>-->
<!--                    <div class="bar"><div class="bar-fill" style="height: 45%;"></div></div>-->
<!--                    <div class="bar-label">Temp</div>-->
<!--                </div>-->
<!--                <div>-->
<!--                    <div class="bar"><div class="bar-fill" style="height: 30%;"></div></div>-->
<!--                    <div class="bar-label">Humid</div>-->
<!--                </div>-->
<!--            </div>-->
<!--        </div>-->

<!--        &lt;!&ndash; Update Button &ndash;&gt;-->
<!--        <button on:click={updateDevice} disabled={loading} style="background: #4CAF50; color: white; padding: 10px; border: none; cursor: pointer;">-->
<!--            🔄 Update & Restart-->
<!--        </button>-->

<!--        {#if loading}-->
<!--            <div id="loading" style="margin-top: 10px;">-->
<!--                <img src="images/loading.gif" alt="Loading..." style="width: 50px;">-->
<!--                <p>Updating... please wait</p>-->
<!--            </div>-->
<!--        {/if}-->
<!--    </div>-->
<!--</main>-->

