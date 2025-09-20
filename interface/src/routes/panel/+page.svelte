<script>
    import { onMount } from 'svelte';

    let currentView = 'sensors';
    let logs = [];
    let loading = false;

    function loadPanel(view) {
        currentView = view;
    }

    async function updateDevice() {
        loading = true;
        await fetch('/update', { method: 'POST' });
        setTimeout(() => loading = false, 5000);
    }

    onMount(() => {
        // preload logs or other data here if needed
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
