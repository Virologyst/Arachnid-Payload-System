<script>
    import { onMount } from 'svelte';
    import {
        AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
    } from 'recharts';

    let historicData = [];

    async function fetchHistory() {
        const res = await fetch('/enviro/history');
        historicData = await res.json();
    }

    onMount(() => {
        fetchHistory();
        setInterval(fetchHistory, 4000);
    });
</script>

<style>
    @import '../../styling.css';

    .full-page-graph {
        width: 100%;
        height: 100vh;
        padding: 20px;
        background: #101820;
        color: white;
    }
</style>

<div class="full-page-graph">
    <h2>Full Sensor History</h2>
    <ResponsiveContainer width="100%" height="80%">
        <AreaChart data={historicData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="timestamp" tick={{ fontSize: 10 }} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Area type="monotone" dataKey="temperature" stroke="#ff7300" fill="#ff7300" fillOpacity={0.3} />
            <Area type="monotone" dataKey="humidity" stroke="#00c3ff" fill="#00c3ff" fillOpacity={0.3} />
            <Area type="monotone" dataKey="pressure" stroke="#8884d8" fill="#8884d8" fillOpacity={0.2} />
        </AreaChart>
    </ResponsiveContainer>
</div>