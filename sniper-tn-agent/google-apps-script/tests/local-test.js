#!/usr/bin/env node
/* Local smoke test for Code.gs. It mocks Google and Telegram services. */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const code = fs.readFileSync(path.join(__dirname, '../Code.gs'), 'utf8');
const content = fs.readFileSync(
  path.join(root, 'content/week-01/content.json'),
  'utf8',
);

const values = new Map([
  ['BOT_TOKEN', 'test-token-not-a-secret'],
  ['TELEGRAM_CHAT_ID', '111'],
  ['APPROVER_USER_ID', '222'],
]);
const calls = [];
let telegramUpdates = [];
const triggers = [];
const cache = new Map();

const properties = {
  getProperty: (key) => (values.has(key) ? values.get(key) : null),
  setProperty: (key, value) => values.set(key, String(value)),
  deleteProperty: (key) => values.delete(key),
};

class MockResponse {
  constructor(status, body) {
    this.status = status;
    this.body = typeof body === 'string' ? body : JSON.stringify(body);
  }
  getResponseCode() {
    return this.status;
  }
  getContentText() {
    return this.body;
  }
}

const context = {
  console,
  Date,
  JSON,
  Math,
  Number,
  String,
  Error,
  PropertiesService: { getScriptProperties: () => properties },
  CacheService: {
    getScriptCache: () => ({
      get: (key) => cache.get(key) || null,
      put: (key, value) => cache.set(key, value),
    }),
  },
  LockService: {
    getScriptLock: () => ({
      tryLock: () => true,
      waitLock: () => true,
      releaseLock: () => {},
    }),
  },
  Utilities: {
    formatDate: () => '2026-08-13',
    base64EncodeWebSafe: (value) => Buffer.from(value).toString('base64url'),
  },
  ScriptApp: {
    getProjectTriggers: () => triggers,
    deleteTrigger: (trigger) => {
      const index = triggers.indexOf(trigger);
      if (index >= 0) triggers.splice(index, 1);
    },
    newTrigger: (handler) => ({
      timeBased() {
        return this;
      },
      everyMinutes(minutes) {
        this.minutes = minutes;
        return this;
      },
      create() {
        triggers.push({
          handler,
          minutes: this.minutes,
          getHandlerFunction: () => handler,
        });
      },
    }),
  },
  UrlFetchApp: {
    fetch: (url, options = {}) => {
      if (url.includes('/content/week-01/content.json')) {
        return new MockResponse(200, content);
      }
      const match = url.match(/\/bot[^/]+\/([^/?]+)/);
      if (!match) throw new Error(`Unexpected URL: ${url}`);
      const method = match[1];
      calls.push({ method, payload: options.payload || {} });
      if (method === 'getMe') {
        return new MockResponse(200, {
          ok: true,
          result: { id: 999, username: 'SniperTestBot', first_name: 'Sniper' },
        });
      }
      if (method === 'getUpdates') {
        // Deliberately replay the same mock batch so Code.gs must deduplicate it.
        return new MockResponse(200, { ok: true, result: telegramUpdates });
      }
      return new MockResponse(200, { ok: true, result: true });
    },
  },
};

vm.createContext(context);
vm.runInContext(
  `${code}\n` +
    `globalThis.__test = {\n` +
    `  setupSniperTn, sendNextContentNow, resetQueueToDay,\n` +
    `  handleCallback_, getConfig_, sendCurrentContent_, processTelegramUpdates_\n` +
    `};`,
  context,
);

const api = context.__test;
const setup = api.setupSniperTn();
assert.equal(setup.ok, true);
assert.equal(setup.nextDay, 2);
assert.equal(triggers.length, 1);
assert.equal(triggers[0].minutes, 5);

// Telegram may replay a batch after a transient failure. It must be handled once.
telegramUpdates = [
  {
    update_id: 50,
    message: { from: { id: 222 }, chat: { id: 111 }, text: '/status' },
  },
];
const messagesBeforeReplay = calls.filter(
  (call) => call.method === 'sendMessage',
).length;
api.processTelegramUpdates_();
api.processTelegramUpdates_();
const messagesAfterReplay = calls.filter(
  (call) => call.method === 'sendMessage',
).length;
assert.equal(messagesAfterReplay - messagesBeforeReplay, 1);
assert.equal(values.get('UPDATE_OFFSET'), '51');
assert.equal(values.get('LAST_PROCESSED_UPDATE_ID'), '50');
telegramUpdates = [];

const sent = api.sendNextContentNow();
assert.equal(sent.ok, true);
assert.equal(sent.postId, 'W01-D02');
assert.equal(values.get('PENDING_POST_ID'), 'W01-D02');
assert.ok(calls.some((call) => call.method === 'sendVideo'));
assert.ok(calls.some((call) => call.method === 'sendMessage'));

api.handleCallback_(api.getConfig_(), {
  id: 'callback-1',
  from: { id: 222 },
  data: 'approve|W01-D02',
  message: { message_id: 10, chat: { id: 111 } },
});
assert.equal(values.get('QUEUE_INDEX'), '2');
assert.equal(values.has('PENDING_POST_ID'), false);
assert.equal(values.get('LAST_APPROVED_ID'), 'W01-D02');

api.resetQueueToDay(7);
const daySeven = api.sendNextContentNow();
assert.equal(daySeven.postId, 'W01-D07');
api.handleCallback_(api.getConfig_(), {
  id: 'callback-2',
  from: { id: 222 },
  data: 'approve|W01-D07',
  message: { message_id: 11, chat: { id: 111 } },
});
const videosBefore = calls.filter((call) => call.method === 'sendVideo').length;
const complete = api.sendNextContentNow();
const videosAfter = calls.filter((call) => call.method === 'sendVideo').length;
assert.equal(complete.reason, 'week_complete');
assert.equal(videosAfter, videosBefore, 'week one must not loop back to day one');

console.log('Google Apps Script smoke test: OK');
