<!--<script>-->
<!--	import favicon from '$lib/assets/favicon.svg';-->

<!--	let { children } = $props();-->
<!--</script>-->

<!--<svelte:head>-->
<!--	<link rel="icon" href={favicon} />-->
<!--</svelte:head>-->

<!--{@render children?.()}-->




<!--<script>-->
<!--	import favicon from '$lib/assets/favicon.svg';-->
<!--	let { children } = $props();-->
<!--</script>-->

<!--<svelte:head>-->
<!--	<link rel="icon" href={favicon} />-->
<!--</svelte:head>-->

<!--<header class="navbar">-->
<!--	<div class="logo-container">-->
<!--		<a href="/" class="logo-link">-->
<!--			<img src="/images/logo.png" alt="Home" class="logo" />-->
<!--		</a>-->
<!--		<h1>EGH455: Advanced System Design - Group 5</h1>-->
<!--	</div>-->

<!--	<nav class="nav">-->
<!--		<a href="/" class="nav-btn">Dashboard</a>-->
<!--		<a href="/images" class="nav-btn">Images</a>-->
<!--	</nav>-->

<!--	<div class="hamburger" on:click={() => mobileMenuOpen = !mobileMenuOpen}>☰</div>-->
<!--</header>-->

<!--&lt;!&ndash; Mobile nav &ndash;&gt;-->
<!--<div class={`mobile-menu ${mobileMenuOpen ? 'open' : ''}`}>-->
<!--	<a href="/" on:click={() => mobileMenuOpen = false}>📊 Dashboard</a>-->
<!--	<a href="/images" on:click={() => mobileMenuOpen = false}>📸 Images</a>-->
<!--</div>-->

<!--{@render children?.()}-->

<!-- src/routes/+layout.svelte -->
<script>
	import favicon from '$lib/assets/favicon.svg';
	let mobileMenuOpen = false;
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<header class="navbar">
	<div class="logo-container">
		<a href="/" class="logo-link">
			<img src="/logo.png" alt="Home" class="logo" />
		</a>
		<h1>EGH455: Advanced System Design - Group 5</h1>
	</div>

	<nav class="nav">
		<a href="/" class="nav-btn">Dashboard</a>
		<a href="/images" class="nav-btn">Images</a>
	</nav>

	<div class="hamburger" on:click={() => mobileMenuOpen = !mobileMenuOpen}>☰</div>
</header>

<div class={`mobile-menu ${mobileMenuOpen ? 'open' : ''}`}>
	<a href="/" on:click={() => mobileMenuOpen = false}>📊 Dashboard</a>
	<a href="/images" on:click={() => mobileMenuOpen = false}>📸 Images</a>
</div>

<slot />
