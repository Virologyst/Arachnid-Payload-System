<script>
	import favicon from '$lib/assets/favicon.svg';
	let mobileMenuOpen = false;
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Project Arachnid: Huntsman PL01</title>
</svelte:head>

<header class="navbar">
	<div class="logo-container">
		<a href="/" class="logo-link">
			<img src="/logo.png" alt="V-Source Development" class="logo" />
		</a>
		<h1 style="margin-left: 25px">Project Arachnid: Huntsman PL01</h1>
	</div>

	<nav class="nav">
		<a href="/" class="nav-btn">Dashboard</a>
		<a href="/images" class="nav-btn">Images</a>
<!--		<a href="/graph" class="nav-btn">Graph</a>-->
	</nav>

	<div class="hamburger" on:click={() => mobileMenuOpen = !mobileMenuOpen}>☰</div>

</header>

<div class={`mobile-menu ${mobileMenuOpen ? 'open' : ''}`}>
	<a href="/" on:click={() => mobileMenuOpen = false}>Dashboard</a>
	<a href="/images" on:click={() => mobileMenuOpen = false}>Images</a>
	<a href="/panel" on:click={() => mobileMenuOpen = false}>Data</a>
<!--	<a href="/graph" on:click={() => mobileMenuOpen = false}>Graph</a>-->
</div>

<slot />
