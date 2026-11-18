import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import test from 'node:test';
import { createDevApiProxy } from '../vite.config.js';

function forwardedOrigin(origin, host = '192.168.70.107:5188') {
  const proxy = new EventEmitter();
  createDevApiProxy('http://127.0.0.1:8011').configure(proxy);
  const headers = {};
  proxy.emit('proxyReq', { setHeader: (key, value) => { headers[key] = value; } }, { headers: { origin, host }, socket: {} });
  return headers.Origin;
}
test('same-origin LAN and localhost requests retain CSRF through the dev proxy', () => {
  assert.equal(forwardedOrigin('http://192.168.70.107:5188'), 'http://127.0.0.1:8011');
  assert.equal(forwardedOrigin('http://localhost:5173', 'localhost:5173'), 'http://127.0.0.1:8011');
});
test('foreign, malformed, opaque and different-scheme origins are never trusted', () => {
  for (const origin of ['https://evil.example', 'null', 'broken', 'https://192.168.70.107:5188', undefined]) {
    assert.equal(forwardedOrigin(origin), undefined);
  }
});
