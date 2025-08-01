<script>
    import { onMount } from 'svelte';

    let loading = false;

    function updateDevice() {
        loading = true;
        fetch('/update', { method: 'POST' })
            .then(() => {
                setTimeout(() => {
                    loading = false;
                    window.location.reload();
                }, 5000);
            });
    }

    let currentView = 'sensors';
    let panelContent = '';

    async function loadPanel(view) {
        currentView = view;
        const res = await fetch(`/panel/${view}`);
        panelContent = await res.text();
    }

    onMount(() => {
        loadPanel('sensors'); // default panel
    });
</script>

<style>
    /* You can keep most of your old CSS in static/style.css and import it */
    @import '/style.css';

    .camera-pane img {
        width: 100%;
        height: auto;
        max-height: 400px;
        object-fit: contain;
    }

    .tab-buttons button {
        margin-right: 5px;
        padding: 8px 12px;
        border: none;
        cursor: pointer;
        background: #333;
        color: white;
    }
</style>

<header>
    <h1>EGH455 - Team 5</h1>
</header>

<main>
    <div class="sidebar">
        <img src="/thumb1.jpg" alt="Thumbnail 1">
        <img src="/thumb1.jpg" alt="Thumbnail 2">
        <img src="/thumb1.jpg" alt="Thumbnail 3">
    </div>

    <div class="content">
        <div class="top-row">
            <!-- Left: Camera -->
            <div class="camera-pane">
                <img src="/mars.jpg" alt="Live Camera Feed">
            </div>

            <!-- Right: Dynamic Panel -->
            <div class="panel-pane">
                <div class="tab-buttons">
                    <button on:click={() => loadPanel('sensors')}>📊 Sensors</button>
                    <button on:click={() => loadPanel('logs')}>📜 Logs</button>
                    <button on:click={() => loadPanel('targets')}>🎯 Targets</button>
                    <button on:click={() => loadPanel('system')}>⚙ System</button>
                </div>

<!--                <div id="dynamicPanel" bind:this={dynamicPanel}>-->
<!--                    {@html panelContent}-->
<!--                </div>-->
            </div>
        </div>

        <div class="bottom-row">
            <div class="readings-table">
                <table border="1" cellpadding="5">
                    <thead>
                        <tr><th>Targets</th><th>Average Readings</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>A:</td><td>- - -</td></tr>
                        <tr><td>B:</td><td>380 ppm, 22.3°C, 14%</td></tr>
                        <tr><td>C:</td><td>- - -</td></tr>
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
        <button on:click={updateDevice} disabled={loading} style="background: #4CAF50; color: white; padding: 10px; border: none; cursor: pointer;">
            🔄 Update & Restart
        </button>

        {#if loading}
            <div id="loading" style="margin-top: 10px;">
                <img src="/loading.gif" alt="Loading..." style="width: 50px;">
                <p>Updating... please wait</p>
            </div>
        {/if}
    </div>
</main>

