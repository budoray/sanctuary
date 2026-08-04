import './style.css';
import { GameScene } from './game/GameScene';

const app = document.getElementById('app');
if (!app) {
  throw new Error('Missing #app container');
}

const scene = new GameScene(app);

// Auto-create a session on first load for the solo vertical slice.
scene.newSession();
