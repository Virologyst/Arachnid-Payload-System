<script>
    import { onMount } from 'svelte';

    let thumbnails = [];
    let contextMenuVisible = false;
    let contextMenuX = 0;
    let contextMenuY = 0;
    let selectedImage = null;

    async function fetchThumbnails() {
        const res = await fetch('/images');
        const data = await res.json();
        thumbnails = data.images || [];
    }

    async function deleteImage(filename) {
        await fetch(`/images/delete/${filename}`, { method: 'DELETE' });
        contextMenuVisible = false;
        await fetchThumbnails();
    }

    function openContextMenu(event, filename) {
        event.preventDefault();
        selectedImage = filename;
        contextMenuX = event.pageX;
        contextMenuY = event.pageY;
        contextMenuVisible = true;
    }

    function closeContextMenu() {
        contextMenuVisible = false;
    }

    onMount(() => {
        fetchThumbnails();
        document.addEventListener('click', closeContextMenu);
    });
</script>

<style>
    .gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        gap: 10px;
        padding: 20px;
        background: #0a0f1a;
        color: white;
    }

    .thumb {
        width: 100%;
        height: auto;
        border-radius: 8px;
        cursor: pointer;
        transition: transform 0.2s ease;
        object-fit: cover;
    }

    .thumb:hover {
        transform: scale(1.05);
    }

    .context-menu {
        position: absolute;
        top: 0;
        left: 0;
        background: rgba(30, 30, 30, 0.95);
        color: white;
        border: 1px solid #333;
        padding: 8px;
        border-radius: 6px;
        z-index: 1000;
    }

    .context-menu button {
        background: none;
        border: none;
        color: #f66;
        font-size: 14px;
        cursor: pointer;
        padding: 5px;
    }

    .context-menu button:hover {
        text-decoration: underline;
    }
</style>

<h1 style="text-align: center; margin-top: 20px;">Image Gallery</h1>

<div class="gallery">
    {#each thumbnails as img}
        <img
            src={`/images/${img}`}
            alt={img}
            class="thumb"
            on:contextmenu={(e) => openContextMenu(e, img)}
        />
    {/each}
</div>

{#if contextMenuVisible}
    <div
        class="context-menu"
        style="top: {contextMenuY}px; left: {contextMenuX}px;"
    >
        <button on:click={() => deleteImage(selectedImage)}>🗑 Delete</button>
    </div>
{/if}
