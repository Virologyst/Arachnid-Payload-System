<script>
    import { onMount } from 'svelte';

    let thumbnails = [];
    let contextMenuVisible = false;
    let contextMenuX = 0;
    let contextMenuY = 0;
    let selectedImage = null;
    let modalImage = null;

    async function fetchThumbnails() {
        const res = await fetch('/images');
        const data = await res.json();
        thumbnails = data.images || [];
    }

    function openModal(filename) {
		modalImage = `/images/${filename}`;
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

    	.modal {
		position: fixed;
		top: 50px; left: 0;
		width: 100%; height: 100%;
		background: rgba(0, 0, 0, 0.8);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}
	.modal-content {
		background: #1d2e5a;
		padding: 20px;
		border-radius: 12px;
		max-width: 80%;
		max-height: 80%;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.modal-content img {
		max-width: 100%;
		max-height: 70vh;
	}
	.delete-btn, .close-btn {
		margin: 10px;
		padding: 10px 15px;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		color: white;
	}
	.delete-btn { background: #cc0000; }
	.close-btn { background: #555; }
	.delete-btn:hover { background: #ff3333; }
	.close-btn:hover { background: #777; }
</style>

<h1 style="text-align: center; margin-top: 20px;">Image Gallery</h1>

<div class="gallery">
    {#each thumbnails as img}
        <img
            src={`/images/${img}`}
            alt={img}
            class="thumb"
            on:click={() => openModal(img)}
            on:contextmenu={(e) => openContextMenu(e, img)}
        />
    {/each}
</div>

<!-- Modal -->
{#if modalImage}
	<div class="modal">
		<div class="modal-content">
			<img src={modalImage} alt="Full Image">
			<div>
				<button class="delete-btn" on:click={() => deleteImage(modalImage.split('/').pop())}>🗑 Delete</button>
				<button class="close-btn" on:click={() => modalImage = null}>Close</button>
			</div>
		</div>
	</div>
{/if}

{#if contextMenuVisible}
    <div
        class="context-menu"
        style="top: {contextMenuY}px; left: {contextMenuX}px;"
    >
        <button on:click={() => deleteImage(selectedImage)}>🗑 Delete</button>
    </div>
{/if}
