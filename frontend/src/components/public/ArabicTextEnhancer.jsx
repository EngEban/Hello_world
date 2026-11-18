import { useEffect } from 'react';

const ARABIC_TEXT_PATTERN = /[\u0600-\u06FF]/;
const SKIPPED_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT']);

function enhanceArabicText(root) {
  if (!root) return;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !ARABIC_TEXT_PATTERN.test(node.nodeValue)) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if (!parent || SKIPPED_TAGS.has(parent.tagName)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  const targets = new Set();
  while (walker.nextNode()) {
    const parent = walker.currentNode.parentElement;
    if (parent) targets.add(parent);
  }

  targets.forEach(element => {
    element.classList.add('has-arabic-text');
    if (!element.getAttribute('lang')) element.setAttribute('lang', 'ar');
    if (!element.getAttribute('dir')) element.setAttribute('dir', 'auto');
  });
}

export default function ArabicTextEnhancer() {
  useEffect(() => {
    const root = document.querySelector('main');
    enhanceArabicText(root);

    const observer = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.TEXT_NODE) {
            enhanceArabicText(node.parentElement);
            return;
          }
          if (node.nodeType === Node.ELEMENT_NODE) enhanceArabicText(node);
        });
      });
    });

    if (root) observer.observe(root, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, []);

  return null;
}
