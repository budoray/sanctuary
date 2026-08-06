import './style.css';

const app = document.getElementById('app');
if (!app) {
  throw new Error('Missing #app container');
}

function hideSplash() {
  const splash = document.getElementById('splash');
  if (!splash) return;
  splash.classList.add('hidden');
  setTimeout(() => splash.remove(), 600);
}

function showPlaceholder() {
  const panel = document.createElement('div');
  panel.className = 'placeholder-panel';
  panel.innerHTML = `
    <h1>Sanctuary</h1>
    <p>The realm is being rebuilt from the ground up.</p>
    <p class="muted">Top-down OSRIC tactical RPG · solo & party play · human or engine DM</p>
    <footer class="licence">
      Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License
      and is not affiliated with Mythmere Games LLC.
    </footer>
  `;
  app!.appendChild(panel);
}

showPlaceholder();
hideSplash();
