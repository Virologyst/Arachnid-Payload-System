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
  @import '../../../styling.css';

  .full-page-graph {
    width: 100%;
    height: 100vh;
    padding: 20px;
    background: #101820;
    color: white;
  }

  .recharts-tooltip-wrapper {
    background: rgba(20, 20, 20, 0.9) !important;
    border-radius: 8px;
    padding: 8px;
    font-size: 12px;
    color: #fff;
  }
</style>

<div class="full-page-graph">
  <h2>Full Sensor History (Last 10 Minutes)</h2>

</div>
