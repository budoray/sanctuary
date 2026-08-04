import { describe, it, expect } from 'vitest';

function greet(name: string) {
  return `Hello, ${name}!`;
}

describe('greet', () => {
  it('returns a greeting', () => {
    expect(greet('Sanctuary')).toBe('Hello, Sanctuary!');
  });
});
