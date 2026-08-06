import './style.css';
import { SanctuaryApp } from './ui/app';

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

async function boot() {
  const sanctuary = new SanctuaryApp(app!);
  try {
    await sanctuary.start();
  } finally {
    hideSplash();
  }
}

boot();
