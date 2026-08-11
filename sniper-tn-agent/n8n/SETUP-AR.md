# إعداد Telegram وn8n لصفحة Sniper‑Tn

هذا الدليل يشغّل Workflow الموافقة اليومية أولًا، ثم يشرح ربط Meta للنشر. **ابدأ و`facebookAutoPublish` معطّل**، ولا تضع أي Token داخل Workflow أو في المحادثة.

## المتطلبات

- حساب Telegram.
- حساب n8n Cloud بإصدار 2.33.7 أو أحدث. يمكن استعمال استضافة ذاتية، لكن يلزم عنوان HTTPS عام حتى تعمل أزرار الموافقة داخل Telegram.
- لإضافة النشر لاحقًا: حساب Meta for Developers وصفحة Facebook تملك عليها مهمة `CREATE_CONTENT`.

الملف القابل للاستيراد:

[`sniper-tn-telegram-approval.json`](sniper-tn-telegram-approval.json)

---

## 1. إنشاء Bot في Telegram

1. افتح المحادثة الرسمية مع [BotFather](https://telegram.me/BotFather).
2. أرسل الأمر `/newbot`.
3. اختر اسمًا مثل `Sniper‑Tn Manager`.
4. اختر Username ينتهي بـ`bot`، مثل `SniperTnManagerBot` إن كان متاحًا.
5. يرسل BotFather **Bot Token**. احتفظ به سرًا.
6. افتح محادثة البوت الجديد واضغط **Start** أو أرسل `/start`.

> لا ترسل الـToken هنا، ولا تضعه داخل JSON أو Git. إذا كُشف بالخطأ، استعمل BotFather لإلغائه وتوليد Token جديد.

## 2. إنشاء n8n وربط Telegram

1. أنشئ مساحة عمل على [n8n Cloud](https://n8n.io/cloud/).
2. من **Credentials** اختر **Telegram API**.
3. الصق Bot Token داخل خانة Access Token واحفظ Credential باسم `Sniper-Tn Telegram Bot`.
4. لمعرفة رقم المحادثة ورقم حسابك بطريقة لا تكشف الـToken:
   1. أنشئ Workflow مؤقتًا.
   2. أضف **Telegram Trigger** واختر حدث **Message**.
   3. اختر Credential الذي أنشأته، ثم شغّل الاختبار.
   4. أرسل أي رسالة إلى البوت.
   5. من Output انسخ:
      - `message.chat.id` ← هذا هو `telegramChatId`.
      - `message.from.id` ← هذا هو `approverTelegramUserId`.
   6. أوقف أو احذف Workflow المؤقت بعد الحصول على الرقمين.

## 3. استيراد Workflow

1. نزّل أو افتح ملف [`sniper-tn-telegram-approval.json`](sniper-tn-telegram-approval.json).
2. في n8n اختر **Import from File** واستورد الملف.
3. افتح عقدة **Configuration** واستبدل:
   - `REPLACE_WITH_TELEGRAM_CHAT_ID` برقم `message.chat.id`.
   - `REPLACE_WITH_TELEGRAM_USER_ID` برقم `message.from.id`.
4. اترك:
   - `facebookAutoPublish = false`.
   - `facebookPageId` كما هو في هذه المرحلة.
5. افتح عقد Telegram الست واختر Credential نفسه:
   - Send Video Preview
   - Approve or Request Changes
   - Telegram Published Confirmation
   - Telegram Ready Confirmation
   - Collect Revision Notes
   - Telegram Revision Confirmation
6. احفظ Workflow.

## 4. الاختبار الآمن

1. تأكد مرة أخرى أن `facebookAutoPublish` يساوي `false`.
2. اضغط **Manual Test**.
3. يجب أن يصلك فيديو اليوم الأول في Telegram، ثم رسالة المراجعة.
4. جرّب **طلب تعديل** واكتب ملاحظة اختبارية؛ بهذه الطريقة لا يتقدم الطابور ويبقى اليوم الأول جاهزًا للاختبار الحقيقي.
5. نفّذ الاختبار ثانية واضغط **اعتماد** عندما تريد نقل اليوم الأول إلى الجاهز للنشر.

عند الرفض، يحفظ Workflow ملاحظة التعديل ولا يزيد رقم الطابور. عند الاعتماد، يزيد الرقم وينتظر المحتوى التالي.

## 5. تفعيل الجدول

- Workflow مضبوط على المنطقة الزمنية `Africa/Tunis`.
- يرسل طلب المراجعة يوميًا الساعة **16:00**.
- نافذة النشر المقترحة كبداية هي **20:00 بتوقيت تونس**، لكن النشر الآلي—عند تفعيله—يحدث مباشرة بعد اعتمادك. لذلك اعتمد الفيديو قرب وقت النشر المرغوب.
- فعّل Workflow فقط بعد نجاح الاختبار اليدوي.

---

# ربط Meta للنشر الآلي — مرحلة ثانية

## 6. إنشاء Meta App وصلاحيات الصفحة

بحسب دليل Meta الحالي، نشر Reel على صفحة يتطلب:

- Page Access Token لشخص يستطيع تنفيذ مهمة `CREATE_CONTENT` على الصفحة.
- الصلاحيات:
  - `pages_show_list`
  - `pages_read_engagement`
  - `pages_manage_posts`

الخطوات العامة:

1. افتح [Meta App Dashboard](https://developers.facebook.com/apps/) وأنشئ تطبيق Business.
2. أضف Facebook Login أو Facebook Login for Business بحسب إعدادك.
3. من [Graph API Explorer](https://developers.facebook.com/tools/explorer/) اطلب الصلاحيات السابقة للحساب الذي يدير الصفحة.
4. استعمل `/me/accounts?fields=name,id,access_token,tasks` لاختيار الصفحة والحصول على Page ID وPage Access Token المناسبين.
5. للإنتاج المستمر، أكمِل دورة Token طويلة العمر ومراجعة التطبيق المطلوبة في Meta؛ لا تعتمد على Token مؤقت دون متابعة تاريخ انتهائه.

لا ترسل Page Access Token في المحادثة ولا تحفظه في الملفات.

## 7. تخزين Page Token داخل n8n

1. من n8n افتح **Credentials**.
2. أنشئ **HTTP Header Auth** Credential.
3. أدخل:
   - **Name:** `Authorization`
   - **Value:** `OAuth PAGE_ACCESS_TOKEN`
4. احفظه باسم `Sniper-Tn Meta Page Token`.
5. اختر هذا Credential داخل عقد Meta الثلاث:
   - Start Facebook Reel Upload
   - Upload Hosted Reel
   - Publish Facebook Reel
6. في **Configuration** استبدل `REPLACE_WITH_FACEBOOK_PAGE_ID` بالـPage ID.

## 8. أول نشر عبر Meta

1. أبقِ Workflow غير نشط وابدأ بـ**Manual Test**.
2. تأكد أن الفيديو والنص الظاهرين في Telegram هما المطلوبان للنشر العام.
3. غيّر `facebookAutoPublish` إلى `true` فقط عندما تكون مستعدًا فعلًا؛ الضغط على **اعتماد** سيبدأ النشر العام مباشرة.
4. اضغط **اعتماد** من حساب Telegram المصرّح له.
5. راقب عقد Meta الثلاث. نجاح العقدة الأخيرة يعيد `success: true`، ثم يصلك تأكيد Telegram.
6. افتح الصفحة وتحقق بصريًا من الـReel والوصف قبل تفعيل الجدول اليومي.

> طلب الموافقة يوضح أن الاعتماد يعني نشر Reel عام. هذا يبقي القرار بيدك، ولا يسمح للنظام بالنشر الصامت.

## 9. ماذا يفعل مسار Meta؟

1. `POST /v26.0/{page-id}/video_reels` مع `upload_phase=start`.
2. يرسل رابط MP4 العام إلى `rupload.facebook.com` في Header باسم `file_url`.
3. `POST /v26.0/{page-id}/video_reels` مع `upload_phase=finish` و`video_state=PUBLISHED`.

الفيديوهات في هذه الحزمة عمودية 1080×1920، H.264، 30fps، AAC‑LC ستيريو 48kHz وبمعدل مستهدف 128kbps، ومدتها أقل من 90 ثانية.

## 10. الأمان والتشغيل

- اترك `approverTelegramUserId` مملوءًا حتى لا يعتمد المحتوى شخص آخر.
- لا تفعّل النشر قبل مراجعة الفيديو والصوت والنص والحقوق.
- ملفات الفيديو مستضافة مؤقتًا كرابط GitHub عام لتسهيل أول اختبار. انقلها لاحقًا إلى تخزين/CDN تملكه، ويجب أن يسمح للمستخدم `facebookexternalhit` بجلب الملف وألا يمنعه `robots.txt`.
- لا تستعمل موسيقى أو صورًا لا تملك حق نشرها.
- إذا فشل الرفع، لا تعاود الضغط مرات كثيرة؛ راجع تفاصيل الخطأ وتأكد من صلاحية Token ومواصفات الملف والرابط العام.
- دورة هذا النظام هي فيديو واحد يوميًا، وهي أقل بكثير من حد Meta الحالي البالغ 30 منشور API خلال 24 ساعة.

## روابط رسمية

- [n8n — Telegram credentials](https://docs.n8n.io/integrations/builtin/credentials/telegram/)
- [n8n — Telegram Send and Wait for Response](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/message-operations/)
- [n8n — Import and export workflows](https://docs.n8n.io/workflows/export-import/)
- [Meta — Reels Publishing API](https://developers.facebook.com/documentation/video-api/guides/reels-publishing)
- [Meta — Pages API getting started](https://developers.facebook.com/docs/pages-api/getting-started/)
