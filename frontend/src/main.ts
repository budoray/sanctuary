import './style.css';
import { GameScene } from './game/GameScene';
import { CharacterCreator } from './ui/CharacterCreator';
import { SessionSelect } from './ui/SessionSelect';
import { createCharacter, listCharacters, listSessions } from './net/api';
import { CharacterInfo } from './ui/HUD';

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

async function init() {
  let sessions: any[] = [];
  let characters: any[] = [];

  try {
    const sessionsData = await listSessions();
    sessions = sessionsData.sessions || [];
  } catch (e) {
    // Unauthenticated requests will redirect.
  }

  try {
    const charsData = await listCharacters();
    characters = charsData.characters || [];
  } catch (e) {
    // Unauthenticated requests will redirect.
  }

  if (sessions.length > 0) {
    showSessionSelect(sessions);
    hideSplash();
    return;
  }

  if (characters.length > 0) {
    startGame(characters[0] as CharacterInfo);
    hideSplash();
    return;
  }

  showCharacterCreator();
  hideSplash();
}

function showSessionSelect(sessions: any[]) {
  const select = new SessionSelect(sessions, app as HTMLElement);
  select.onResume = (sessionId) => {
    select.destroy();
    const scene = new GameScene(app as HTMLElement);
    scene.loadSession(sessionId);
  };
  select.onNew = () => {
    select.destroy();
    showCharacterCreatorOrStart();
  };
}

async function showCharacterCreatorOrStart() {
  try {
    const { characters } = await listCharacters();
    if (characters && characters.length > 0) {
      startGame(characters[0] as CharacterInfo);
      return;
    }
  } catch (e) {
    // ignore
  }
  showCharacterCreator();
}

function showCharacterCreator() {
  const creator = new CharacterCreator(app as HTMLElement);
  creator.onCreate = async (char) => {
    try {
      const { character } = await createCharacter(char);
      creator.destroy();
      startGame(character as CharacterInfo);
    } catch (e) {
      alert(`Failed to create character: ${e instanceof Error ? e.message : String(e)}`);
    }
  };
}

async function startGame(character: CharacterInfo) {
  const scene = new GameScene(app as HTMLElement, character);
  scene.newSession(character);
}

init();
