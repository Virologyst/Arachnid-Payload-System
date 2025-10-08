import devtoolsJson from 'vite-plugin-devtools-json';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit(), devtoolsJson()]
});

// export default defineConfig({
//   plugins: [svelte()],
//   server: {
//     proxy: {
//       '/enviro': 'http://localhost:8080',
//       '/logs': 'http://localhost:8080',
//       '/images': 'http://localhost:8080',
//       '/targets': 'http://localhost:8080',
//       '/update': 'http://localhost:8080'
//     }
//   }
// });
