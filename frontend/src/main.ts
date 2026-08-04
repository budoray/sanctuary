import './style.css';
import { GameScene } from './game/GameScene';
import { CharacterCreator } from './ui/CharacterCreator';
import { createCharacter, listCharacters } from './net/api';
import { CharacterInfo } from './ui/HUD';

const app = document.getElementById('app');
if (!app) {
  throw new Error('Missing #app container');
}

async function init() {
  // Check for an existing character first.
  try {
    const { characters } = await listCharacters();
    if (characters && characters.length > 0) {
      startGame(characters[0] as CharacterInfo);
      return;
    }
  } catch (e) {
    // If unauthenticated, the API will redirect.
  }

  // Show character creator.
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
