/*
 * Sniper-Tn Telegram content manager — Google Apps Script edition.
 *
 * Secrets are read from Script Properties. Never paste BOT_TOKEN into this file.
 * Run setupSniperTn() once after adding the required Script Properties.
 */

const SNIPER = Object.freeze({
  TIMEZONE: 'Africa/Tunis',
  SEND_HOUR: 16,
  POLL_MINUTES: 1,
  DEFAULT_START_DAY: 2,
  TRIGGER_FUNCTION: 'sniperTick',
  CONTENT_URL:
    'https://raw.githubusercontent.com/saaidiaa/n8n-docs/30b1e2ae167652087bfd1ab054cc2142cefcf405/sniper-tn-agent/content/week-01/content.json',
  ASSET_BASE_URL:
    'https://raw.githubusercontent.com/saaidiaa/n8n-docs/30b1e2ae167652087bfd1ab054cc2142cefcf405/sniper-tn-agent/content/week-01/assets',
});

const STATE = Object.freeze({
  QUEUE_INDEX: 'QUEUE_INDEX',
  UPDATE_OFFSET: 'UPDATE_OFFSET',
  PENDING_POST_ID: 'PENDING_POST_ID',
  AWAITING_REVISION_ID: 'AWAITING_REVISION_ID',
  NEEDS_REVISION_ID: 'NEEDS_REVISION_ID',
  LAST_SENT_DATE: 'LAST_SENT_DATE',
  LAST_APPROVED_ID: 'LAST_APPROVED_ID',
  WEEK_COMPLETE_NOTIFIED: 'WEEK_COMPLETE_NOTIFIED',
  LAST_ERROR_KEY: 'LAST_ERROR_KEY',
  LAST_ERROR_AT: 'LAST_ERROR_AT',
});

/**
 * One-time setup. Before running this function:
 * 1. Unpublish the old n8n workflow.
 * 2. Add BOT_TOKEN, TELEGRAM_CHAT_ID, and APPROVER_USER_ID to Script Properties.
 */
function setupSniperTn() {
  const config = getConfig_();
  const properties = PropertiesService.getScriptProperties();

  const me = telegramApi_('getMe', {}, config.botToken).result;

  // Telegram supports either webhooks or getUpdates polling, never both.
  // The old n8n webhook is removed before this script starts polling.
  telegramApi_(
    'deleteWebhook',
    { drop_pending_updates: true },
    config.botToken
  );

  removeSniperTriggers_();
  ScriptApp.newTrigger(SNIPER.TRIGGER_FUNCTION)
    .timeBased()
    .everyMinutes(SNIPER.POLL_MINUTES)
    .create();

  if (properties.getProperty(STATE.QUEUE_INDEX) === null) {
    properties.setProperty(
      STATE.QUEUE_INDEX,
      String(SNIPER.DEFAULT_START_DAY - 1)
    );
  }
  properties.setProperty(STATE.UPDATE_OFFSET, '0');
  properties.deleteProperty(STATE.PENDING_POST_ID);
  properties.deleteProperty(STATE.AWAITING_REVISION_ID);
  properties.deleteProperty(STATE.NEEDS_REVISION_ID);
  properties.deleteProperty(STATE.LAST_SENT_DATE);
  properties.deleteProperty(STATE.WEEK_COMPLETE_NOTIFIED);

  setBotCommands_(config);
  sendText_(
    config,
    [
      '✅ تم تشغيل مدير Sniper-Tn المجاني.',
      '',
      'سيصل المحتوى يوميًا قرابة الساعة 16:00 بتوقيت تونس.',
      'استعمل /next لإرسال المحتوى التالي الآن، و/status لمعرفة حالة الطابور.',
      '',
      'لن يُنشر شيء على Facebook تلقائيًا في هذه المرحلة.',
    ].join('\n')
  );

  return {
    ok: true,
    bot: '@' + (me.username || me.first_name),
    nextDay: getCurrentDayNumber_(),
    triggerEveryMinutes: SNIPER.POLL_MINUTES,
  };
}

/** Run automatically every minute. */
function sniperTick() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return;

  try {
    processTelegramUpdates_();
    maybeSendScheduledContent_();
  } catch (error) {
    console.error(error && error.stack ? error.stack : error);
    notifyErrorOnce_(error);
  } finally {
    lock.releaseLock();
  }
}

/** Send the current queued video immediately. Useful for the first test. */
function sendNextContentNow() {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const config = getConfig_();
    return sendCurrentContent_(config, 'manual');
  } finally {
    lock.releaseLock();
  }
}

/** Check Telegram credentials without changing the queue. */
function testTelegramConnection() {
  const config = getConfig_();
  const me = telegramApi_('getMe', {}, config.botToken).result;
  sendText_(
    config,
    '✅ الاتصال ناجح مع البوت @' + (me.username || me.first_name) + '.'
  );
  return { ok: true, username: me.username || '', botId: String(me.id) };
}

/** Stop only this Apps Script automation. */
function stopSniperTn() {
  removeSniperTriggers_();
  const config = getConfig_();
  sendText_(config, '⏸ تم إيقاف الإرسال التلقائي من Google Apps Script.');
  return { ok: true };
}

/** Reset the queue to a 1-based day number, for example resetQueueToDay(2). */
function resetQueueToDay(dayNumber) {
  const content = loadContent_();
  const day = Number(dayNumber);
  if (!Number.isInteger(day) || day < 1 || day > content.posts.length) {
    throw new Error('رقم اليوم يجب أن يكون بين 1 و' + content.posts.length + '.');
  }

  const properties = PropertiesService.getScriptProperties();
  properties.setProperty(STATE.QUEUE_INDEX, String(day - 1));
  properties.deleteProperty(STATE.PENDING_POST_ID);
  properties.deleteProperty(STATE.AWAITING_REVISION_ID);
  properties.deleteProperty(STATE.NEEDS_REVISION_ID);
  properties.deleteProperty(STATE.LAST_SENT_DATE);
  properties.deleteProperty(STATE.WEEK_COMPLETE_NOTIFIED);
  return { ok: true, nextDay: day };
}

/** Return and send a readable queue status. */
function showSniperStatus() {
  const config = getConfig_();
  const text = buildStatusText_();
  sendText_(config, text);
  return { ok: true, status: text };
}

function processTelegramUpdates_() {
  const config = getConfig_();
  const properties = PropertiesService.getScriptProperties();
  const offset = Number(properties.getProperty(STATE.UPDATE_OFFSET) || '0');
  const response = telegramApi_(
    'getUpdates',
    {
      offset: offset,
      limit: 100,
      timeout: 0,
      allowed_updates: JSON.stringify(['message', 'callback_query']),
    },
    config.botToken
  );

  response.result.forEach(function (update) {
    try {
      if (update.callback_query) {
        handleCallback_(config, update.callback_query);
      } else if (update.message) {
        handleMessage_(config, update.message);
      }
    } catch (error) {
      console.error('Update ' + update.update_id + ': ' + error);
      sendText_(config, '⚠️ تعذّرت معالجة الرسالة: ' + safeErrorMessage_(error));
    } finally {
      properties.setProperty(
        STATE.UPDATE_OFFSET,
        String(Number(update.update_id) + 1)
      );
    }
  });
}

function handleCallback_(config, callback) {
  const callbackId = callback.id;
  const fromId = String(callback.from && callback.from.id);
  const chatId = String(
    callback.message && callback.message.chat && callback.message.chat.id
  );

  if (
    fromId !== config.approverUserId ||
    chatId !== config.telegramChatId
  ) {
    telegramApi_(
      'answerCallbackQuery',
      {
        callback_query_id: callbackId,
        text: 'هذا الحساب غير مخوّل لاتخاذ القرار.',
        show_alert: true,
      },
      config.botToken
    );
    return;
  }

  const parts = String(callback.data || '').split('|');
  const action = parts[0];
  const postId = parts[1] || '';
  const properties = PropertiesService.getScriptProperties();
  const pendingId = properties.getProperty(STATE.PENDING_POST_ID) || '';

  if (!postId || postId !== pendingId) {
    telegramApi_(
      'answerCallbackQuery',
      {
        callback_query_id: callbackId,
        text: 'هذا القرار قديم أو تمت معالجته مسبقًا.',
        show_alert: true,
      },
      config.botToken
    );
    return;
  }

  removeInlineButtons_(config, callback.message);

  if (action === 'approve') {
    telegramApi_(
      'answerCallbackQuery',
      { callback_query_id: callbackId, text: 'تم الاعتماد ✅' },
      config.botToken
    );
    approvePost_(config, postId);
    return;
  }

  if (action === 'revise') {
    telegramApi_(
      'answerCallbackQuery',
      { callback_query_id: callbackId, text: 'اكتب التعديل المطلوب ✏️' },
      config.botToken
    );
    properties.setProperty(STATE.AWAITING_REVISION_ID, postId);
    sendText_(
      config,
      '✏️ اكتب الآن التعديل المطلوب للمحتوى ' +
        postId +
        ' في رسالة واحدة.\nمثال: غيّر الصوت أو اختصر النص.'
    );
    return;
  }

  telegramApi_(
    'answerCallbackQuery',
    { callback_query_id: callbackId, text: 'أمر غير معروف.', show_alert: true },
    config.botToken
  );
}

function handleMessage_(config, message) {
  const fromId = String(message.from && message.from.id);
  const chatId = String(message.chat && message.chat.id);
  if (
    fromId !== config.approverUserId ||
    chatId !== config.telegramChatId ||
    !message.text
  ) {
    return;
  }

  const text = String(message.text).trim();
  const command = text.split(/\s+/)[0].toLowerCase().split('@')[0];

  if (command === '/start' || command === '/help') {
    sendHelp_(config);
    return;
  }
  if (command === '/status') {
    sendText_(config, buildStatusText_());
    return;
  }
  if (command === '/next') {
    sendCurrentContent_(config, 'command');
    return;
  }

  const properties = PropertiesService.getScriptProperties();
  const revisionId = properties.getProperty(STATE.AWAITING_REVISION_ID);
  if (revisionId) {
    properties.setProperty('REVISION_NOTES_' + revisionId, text.slice(0, 8000));
    properties.setProperty(STATE.NEEDS_REVISION_ID, revisionId);
    properties.deleteProperty(STATE.AWAITING_REVISION_ID);
    properties.deleteProperty(STATE.PENDING_POST_ID);
    sendText_(
      config,
      [
        '📝 تم حفظ تعديل ' + revisionId + ':',
        '',
        text,
        '',
        'لن ينتقل الطابور إلى الفيديو التالي حتى يتم تنفيذ التعديل.',
      ].join('\n')
    );
    return;
  }

  sendText_(
    config,
    'استعمل أزرار اعتماد/تعديل تحت المحتوى، أو أرسل /help لعرض الأوامر.'
  );
}

function maybeSendScheduledContent_() {
  const config = getConfig_();
  const properties = PropertiesService.getScriptProperties();
  const now = new Date();
  const dateKey = Utilities.formatDate(now, SNIPER.TIMEZONE, 'yyyy-MM-dd');
  const hour = Number(Utilities.formatDate(now, SNIPER.TIMEZONE, 'H'));

  if (hour !== SNIPER.SEND_HOUR) return;
  if (properties.getProperty(STATE.LAST_SENT_DATE) === dateKey) return;

  properties.setProperty(STATE.LAST_SENT_DATE, dateKey);

  const pendingId = properties.getProperty(STATE.PENDING_POST_ID);
  if (pendingId) {
    sendText_(
      config,
      '⏳ المحتوى ' + pendingId + ' ما زال ينتظر قرارك، لذلك لم أرسل فيديو مكررًا.'
    );
    return;
  }

  const needsRevisionId = properties.getProperty(STATE.NEEDS_REVISION_ID);
  if (needsRevisionId) {
    sendText_(
      config,
      '🛠 المحتوى ' +
        needsRevisionId +
        ' ينتظر تنفيذ التعديل المسجّل، لذلك أوقفت الطابور مؤقتًا.'
    );
    return;
  }

  sendCurrentContent_(config, 'schedule');
}

function sendCurrentContent_(config, source) {
  const properties = PropertiesService.getScriptProperties();
  const content = loadContent_();
  const index = Number(properties.getProperty(STATE.QUEUE_INDEX) || '0');

  const pendingId = properties.getProperty(STATE.PENDING_POST_ID);
  if (pendingId) {
    sendText_(config, '⏳ المحتوى ' + pendingId + ' ينتظر قرارك بالفعل.');
    return { ok: false, reason: 'pending', postId: pendingId };
  }

  const needsRevisionId = properties.getProperty(STATE.NEEDS_REVISION_ID);
  if (needsRevisionId) {
    sendText_(
      config,
      '🛠 المحتوى ' + needsRevisionId + ' ينتظر تنفيذ التعديل قبل المتابعة.'
    );
    return { ok: false, reason: 'needs_revision', postId: needsRevisionId };
  }

  if (index >= content.posts.length) {
    if (properties.getProperty(STATE.WEEK_COMPLETE_NOTIFIED) !== 'true') {
      sendText_(
        config,
        '🏁 اكتمل محتوى الأسبوع الأول. لن أعيد الفيديوهات القديمة. أضف الأسبوع الثاني ثم تابع الطابور.'
      );
      properties.setProperty(STATE.WEEK_COMPLETE_NOTIFIED, 'true');
    }
    return { ok: false, reason: 'week_complete' };
  }

  const post = content.posts[index];
  const day = String(post.sequence).padStart(2, '0');
  const videoUrl = SNIPER.ASSET_BASE_URL + '/day-' + day + '/reel.mp4';

  telegramApi_(
    'sendVideo',
    {
      chat_id: config.telegramChatId,
      video: videoUrl,
      supports_streaming: true,
      caption:
        '🎬 ' + post.id + ' — ' + post.title + '\n\n' + post.hook,
    },
    config.botToken
  );

  const reviewText = [
    'مراجعة ' + post.id,
    '',
    'العنوان: ' + post.title,
    'المحور: ' + post.pillar,
    '',
    'نص Facebook:',
    post.caption,
    '',
    post.hashtags.join(' '),
    '',
    'التعليق المثبّت:',
    post.pinned_comment,
    '',
    'هل تعتمد هذا المحتوى؟',
  ].join('\n');

  telegramApi_(
    'sendMessage',
    {
      chat_id: config.telegramChatId,
      text: reviewText,
      disable_web_page_preview: true,
      reply_markup: JSON.stringify({
        inline_keyboard: [
          [
            { text: '✅ اعتماد', callback_data: 'approve|' + post.id },
            { text: '✏️ طلب تعديل', callback_data: 'revise|' + post.id },
          ],
        ],
      }),
    },
    config.botToken
  );

  properties.setProperty(STATE.PENDING_POST_ID, post.id);
  console.log('Sent ' + post.id + ' from ' + source);
  return { ok: true, postId: post.id, source: source };
}

function approvePost_(config, postId) {
  const content = loadContent_();
  const properties = PropertiesService.getScriptProperties();
  const index = Number(properties.getProperty(STATE.QUEUE_INDEX) || '0');
  const post = content.posts[index];

  if (!post || post.id !== postId) {
    throw new Error('ترتيب الطابور لا يطابق المحتوى المعتمد.');
  }

  properties.setProperty(STATE.QUEUE_INDEX, String(index + 1));
  properties.setProperty(STATE.LAST_APPROVED_ID, postId);
  properties.deleteProperty(STATE.PENDING_POST_ID);
  properties.deleteProperty(STATE.AWAITING_REVISION_ID);
  properties.deleteProperty(STATE.NEEDS_REVISION_ID);
  properties.deleteProperty('REVISION_NOTES_' + postId);

  sendText_(
    config,
    [
      '✅ تم اعتماد ' + postId + ' وأصبح جاهزًا للنشر.',
      '',
      'انسخ هذا النص عند النشر على Facebook:',
      post.caption,
      '',
      post.hashtags.join(' '),
      '',
      'التعليق المثبّت:',
      post.pinned_comment,
      '',
      index + 1 < content.posts.length
        ? 'المحتوى التالي: اليوم ' + (index + 2) + ' من ' + content.posts.length + '.'
        : 'تم اعتماد آخر محتوى في الأسبوع الأول.',
    ].join('\n')
  );
}

function removeInlineButtons_(config, message) {
  if (!message || !message.chat || !message.message_id) return;
  try {
    telegramApi_(
      'editMessageReplyMarkup',
      {
        chat_id: String(message.chat.id),
        message_id: message.message_id,
        reply_markup: JSON.stringify({ inline_keyboard: [] }),
      },
      config.botToken
    );
  } catch (error) {
    console.warn('Could not remove buttons: ' + error);
  }
}

function sendHelp_(config) {
  sendText_(
    config,
    [
      '🎯 أوامر Sniper-Tn:',
      '',
      '/next — إرسال المحتوى التالي الآن',
      '/status — عرض حالة الطابور',
      '/help — عرض هذه التعليمات',
      '',
      'للاعتماد أو طلب تعديل، استعمل الأزرار الموجودة تحت رسالة المراجعة.',
    ].join('\n')
  );
}

function buildStatusText_() {
  const properties = PropertiesService.getScriptProperties();
  const content = loadContent_();
  const index = Number(properties.getProperty(STATE.QUEUE_INDEX) || '0');
  const pendingId = properties.getProperty(STATE.PENDING_POST_ID);
  const needsRevisionId = properties.getProperty(STATE.NEEDS_REVISION_ID);

  if (needsRevisionId) {
    return '🛠 المحتوى ' + needsRevisionId + ' ينتظر تنفيذ تعديل.';
  }
  if (pendingId) {
    return '⏳ المحتوى ' + pendingId + ' ينتظر قرار اعتماد أو تعديل.';
  }
  if (index >= content.posts.length) {
    return '🏁 اكتمل الأسبوع الأول ولا توجد فيديوهات ستتكرر.';
  }

  const post = content.posts[index];
  return [
    '📋 حالة Sniper-Tn',
    '',
    'المحتوى التالي: ' + post.id,
    'العنوان: ' + post.title,
    'موعد الإرسال: قرابة 16:00 بتوقيت تونس',
  ].join('\n');
}

function getCurrentDayNumber_() {
  const index = Number(
    PropertiesService.getScriptProperties().getProperty(STATE.QUEUE_INDEX) || '0'
  );
  return index + 1;
}

function loadContent_() {
  const cache = CacheService.getScriptCache();
  const cached = cache.get('SNIPER_WEEK_01');
  if (cached) return JSON.parse(cached);

  const response = UrlFetchApp.fetch(SNIPER.CONTENT_URL, {
    method: 'get',
    muteHttpExceptions: true,
    followRedirects: true,
  });
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('تعذر تحميل المحتوى. HTTP ' + status);
  }

  const content = JSON.parse(response.getContentText('UTF-8'));
  if (!content.posts || !Array.isArray(content.posts)) {
    throw new Error('ملف المحتوى غير صالح.');
  }
  cache.put('SNIPER_WEEK_01', JSON.stringify(content), 1800);
  return content;
}

function getConfig_() {
  const properties = PropertiesService.getScriptProperties();
  const config = {
    botToken: String(properties.getProperty('BOT_TOKEN') || '').trim(),
    telegramChatId: String(
      properties.getProperty('TELEGRAM_CHAT_ID') || ''
    ).trim(),
    approverUserId: String(
      properties.getProperty('APPROVER_USER_ID') || ''
    ).trim(),
  };

  const missing = [];
  if (!config.botToken) missing.push('BOT_TOKEN');
  if (!config.telegramChatId) missing.push('TELEGRAM_CHAT_ID');
  if (!config.approverUserId) missing.push('APPROVER_USER_ID');
  if (missing.length) {
    throw new Error(
      'أضف القيم التالية داخل Script Properties: ' + missing.join(', ')
    );
  }
  return config;
}

function telegramApi_(method, payload, token) {
  const botToken = token || getConfig_().botToken;
  const response = UrlFetchApp.fetch(
    'https://api.telegram.org/bot' + botToken + '/' + method,
    {
      method: 'post',
      payload: payload || {},
      muteHttpExceptions: true,
      followRedirects: true,
    }
  );

  let body;
  try {
    body = JSON.parse(response.getContentText('UTF-8'));
  } catch (error) {
    throw new Error(
      'Telegram أعاد استجابة غير مفهومة. HTTP ' + response.getResponseCode()
    );
  }

  if (!body.ok) {
    throw new Error(
      'Telegram ' + method + ': ' + (body.description || 'خطأ غير معروف')
    );
  }
  return body;
}

function sendText_(config, text) {
  return telegramApi_(
    'sendMessage',
    {
      chat_id: config.telegramChatId,
      text: String(text).slice(0, 4096),
      disable_web_page_preview: true,
    },
    config.botToken
  );
}

function setBotCommands_(config) {
  telegramApi_(
    'setMyCommands',
    {
      commands: JSON.stringify([
        { command: 'next', description: 'إرسال المحتوى التالي الآن' },
        { command: 'status', description: 'عرض حالة طابور المحتوى' },
        { command: 'help', description: 'عرض تعليمات البوت' },
      ]),
    },
    config.botToken
  );
}

function removeSniperTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === SNIPER.TRIGGER_FUNCTION) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function notifyErrorOnce_(error) {
  try {
    const config = getConfig_();
    const properties = PropertiesService.getScriptProperties();
    const message = safeErrorMessage_(error);
    const key = Utilities.base64EncodeWebSafe(message).slice(0, 120);
    const now = Date.now();
    const previousKey = properties.getProperty(STATE.LAST_ERROR_KEY);
    const previousAt = Number(properties.getProperty(STATE.LAST_ERROR_AT) || '0');

    // Avoid sending the same error more than once every six hours.
    if (key === previousKey && now - previousAt < 6 * 60 * 60 * 1000) return;

    properties.setProperty(STATE.LAST_ERROR_KEY, key);
    properties.setProperty(STATE.LAST_ERROR_AT, String(now));
    sendText_(config, '⚠️ خطأ في مدير Sniper-Tn:\n' + message);
  } catch (notificationError) {
    console.error('Could not notify error: ' + notificationError);
  }
}

function safeErrorMessage_(error) {
  const text = error && error.message ? error.message : String(error);
  // Never leak a Telegram token if an upstream error happens to include a URL.
  return text.replace(/bot\d+:[A-Za-z0-9_-]+/g, 'bot[REDACTED]').slice(0, 1000);
}
