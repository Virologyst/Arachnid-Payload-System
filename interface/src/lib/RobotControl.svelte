<script>
    // Drive Huntsman from the browser. Hold an arrow key (or a pad button) to move; release stops.
    // Space / Esc / STOP stop at any time. Arming resets on every page load.
    import { onMount, onDestroy } from 'svelte';

    const KEYS = { ArrowUp: 'forward', ArrowDown: 'back', ArrowLeft: 'left', ArrowRight: 'right' };
    const LABELS = { forward: 'Forward', back: 'Back', left: 'Turn left', right: 'Turn right' };
    const HEARTBEAT_MS = 200;   // backend stops the robot if these stop for 700 ms

    let state = { armed: false, connected: false, moving: null, pose_busy: false, lines: [], host: '' };
    let error = '';
    let held = null;            // direction currently held
    let beat = null;
    let poll = null;

    async function post(path, body = {}) {
        try {
            const res = await fetch(path, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            state = { ...state, ...data };
            error = data.ok === false ? data.error : '';
        } catch (e) {
            error = `No reply from the payload: ${e}`;
        }
    }

    async function refresh() {
        try {
            const res = await fetch('/robot');
            state = { ...state, ...(await res.json()) };
        } catch (e) { /* keep last state */ }
    }

    function setArmed(on) {
        release();
        post('/robot/arm', { armed: on });
    }

    function press(dir) {
        if (!state.armed || held === dir) return;
        held = dir;
        post('/robot/drive', { dir });
        clearInterval(beat);
        beat = setInterval(() => post('/robot/drive', { dir }), HEARTBEAT_MS);
    }

    function release() {
        clearInterval(beat);
        beat = null;
        if (held) {
            held = null;
            post('/robot/stop');
        }
    }

    function stop() {
        clearInterval(beat);
        beat = null;
        held = null;
        post('/robot/stop');
    }

    function typing(e) {
        const t = e.target;
        return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
    }

    function onKeyDown(e) {
        if (typing(e)) return;
        if (e.key === ' ' || e.key === 'Escape') {
            e.preventDefault();
            stop();
            return;
        }
        const dir = KEYS[e.key];
        if (!dir || !state.armed) return;
        e.preventDefault();            // no page scrolling while driving
        if (!e.repeat) press(dir);
    }

    function onKeyUp(e) {
        if (KEYS[e.key] && KEYS[e.key] === held) release();
    }

    function onHide() {
        if (document.hidden) release();
    }

    onMount(() => {
        refresh();
        poll = setInterval(refresh, 1000);
        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('keyup', onKeyUp);
        window.addEventListener('blur', release);
        document.addEventListener('visibilitychange', onHide);
    });

    onDestroy(() => {
        release();
        clearInterval(poll);
        if (typeof window !== 'undefined') {
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('keyup', onKeyUp);
            window.removeEventListener('blur', release);
            document.removeEventListener('visibilitychange', onHide);
        }
    });

    $: status = !state.connected ? 'Disconnected'
        : state.pose_busy ? 'Changing pose…'
        : state.moving ? `Moving: ${LABELS[state.moving]}`
        : 'Idle';
</script>

<div class="robot-card">
    <div class="robot-head">
        <h2>Huntsman control</h2>
        <label class="arm">
            <input type="checkbox" checked={state.armed} on:change={(e) => setArmed(e.target.checked)}>
            Armed
        </label>
    </div>

    <div class="robot-status">
        <span class="dot" class:on={state.connected} class:moving={state.moving || state.pose_busy}></span>
        {status} <span class="host">{state.host}</span>
    </div>

    <div class="pad" class:disabled={!state.armed}>
        <span></span>
        <button class:active={held === 'forward'} disabled={!state.armed}
                on:pointerdown={() => press('forward')} on:pointerup={release} on:pointerleave={release}>▲</button>
        <span></span>
        <button class:active={held === 'left'} disabled={!state.armed}
                on:pointerdown={() => press('left')} on:pointerup={release} on:pointerleave={release}>◀</button>
        <button class="stop" on:click={stop}>STOP</button>
        <button class:active={held === 'right'} disabled={!state.armed}
                on:pointerdown={() => press('right')} on:pointerup={release} on:pointerleave={release}>▶</button>
        <span></span>
        <button class:active={held === 'back'} disabled={!state.armed}
                on:pointerdown={() => press('back')} on:pointerup={release} on:pointerleave={release}>▼</button>
        <span></span>
    </div>

    <div class="poses">
        <button disabled={!state.armed || state.moving || state.pose_busy} on:click={() => post('/robot/pose', { pose: 'stand' })}>Stand</button>
        <button disabled={!state.armed || state.moving || state.pose_busy} on:click={() => post('/robot/pose', { pose: 'sit' })}>Sit</button>
    </div>

    <p class="hint">Arm, then hold the arrow keys to move. Space / Esc = stop.</p>

    {#if error}<p class="error">{error}</p>{/if}

    <div class="robot-log">
        {#each state.lines.slice(-8) as line}<div>{line}</div>{/each}
    </div>
</div>

<style>
    .robot-card {
        background: rgba(0, 32, 64, 0.6);
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 12px;
    }
    .robot-head { display: flex; justify-content: space-between; align-items: center; }
    .robot-head h2 { margin: 4px 0; font-size: 1.1rem; }
    .arm { display: flex; gap: 6px; align-items: center; font-weight: bold; cursor: pointer; }
    .arm input { width: 18px; height: 18px; }
    .robot-status { font-size: 0.9rem; margin: 6px 0 10px; display: flex; align-items: center; gap: 8px; }
    .host { opacity: 0.6; font-size: 0.8rem; }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: #666; display: inline-block; }
    .dot.on { background: #2ecc71; }
    .dot.on.moving { background: #f39c12; }
    .pad {
        display: grid;
        grid-template-columns: repeat(3, 64px);
        grid-template-rows: repeat(3, 48px);
        gap: 6px;
        justify-content: center;
        user-select: none;
        touch-action: none;
    }
    .pad button {
        font-size: 1.3rem;
        border: none;
        border-radius: 6px;
        background: #1f3b5c;
        color: #fff;
        cursor: pointer;
    }
    .pad button:disabled { opacity: 0.35; cursor: not-allowed; }
    .pad button.active { background: #2e86de; }
    .pad button.stop { background: #c0392b; font-size: 0.9rem; font-weight: bold; }
    .poses { display: flex; gap: 8px; justify-content: center; margin-top: 10px; }
    .poses button {
        padding: 6px 18px; border: none; border-radius: 6px; background: #1f3b5c; color: #fff; cursor: pointer;
    }
    .poses button:disabled { opacity: 0.35; cursor: not-allowed; }
    .hint { font-size: 0.8rem; opacity: 0.7; text-align: center; margin: 8px 0 4px; }
    .error { color: #ff6b6b; font-size: 0.85rem; margin: 4px 0; }
    .robot-log {
        font-family: monospace; font-size: 0.75rem; opacity: 0.8;
        max-height: 110px; overflow-y: auto; margin-top: 6px;
    }
</style>
