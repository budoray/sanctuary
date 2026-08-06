export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, any> = {},
  ...children: (HTMLElement | string | number | null | undefined)[]
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    if (k === 'className') {
      element.className = String(v);
    } else if (k.startsWith('on') && k.length > 2 && typeof v === 'function') {
      const event = k.slice(2).toLowerCase();
      element.addEventListener(event, v as EventListener);
    } else {
      element.setAttribute(k, String(v));
    }
  });
  children.forEach((c) => {
    if (c === null || c === undefined) return;
    if (typeof c === 'string' || typeof c === 'number') {
      element.appendChild(document.createTextNode(String(c)));
    } else {
      element.appendChild(c);
    }
  });
  return element;
}

export function clear(container: HTMLElement) {
  while (container.firstChild) {
    container.removeChild(container.firstChild);
  }
}

export function formatAbility(name: string) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatModifier(value: number) {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value}`;
}

export function seededRandomSeed() {
  return Math.floor(Math.random() * 1_000_000_000);
}
