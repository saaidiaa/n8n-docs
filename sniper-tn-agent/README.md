# Sniper‑Tn — عميل إدارة محتوى Facebook

حزمة تشغيل أولية لصفحة **Sniper‑Tn | القنّاص** تشمل سبعة Reels جاهزة، رزنامة الأسبوع الأول، ومخطط n8n يرسل المحتوى إلى Telegram للموافقة قبل تمريره إلى النشر.

## ما تم تجهيزه

- 7 فيديوهات عمودية جاهزة بصيغة MP4.
- 7 أغلفة، تعليقات صوتية وخلفيات قابلة لإعادة الاستخدام.
- نص المنشور والتعليق المثبّت والوسوم لكل يوم.
- [رزنامة الأسبوع الأول](content/week-01/calendar.md).
- [بيانات المحتوى بصيغة JSON](content/week-01/content.json) و[CSV](content/week-01/content.csv).
- [Workflow n8n قابل للاستيراد](n8n/sniper-tn-telegram-approval.json).
- موافقة أو رفض من داخل Telegram، مع نموذج لإرسال ملاحظات التعديل.
- طابور يحافظ على ترتيب المحتوى ولا يتقدّم عند طلب تعديل.
- مسار نشر Reels عبر Meta API، **معطّل افتراضيًا للأمان**.

## سلوك النظام

1. يشغّل n8n الطابور يوميًا الساعة 16:00 بتوقيت تونس.
2. يرسل الفيديو إلى محادثة Telegram المحددة.
3. يرسل السكريبت ونص منشور Facebook والتعليق المثبّت.
4. ينتظر قرار المستخدم:
   - **اعتماد:** ينتقل المحتوى إلى «جاهز للنشر»؛ وإذا فُعّل Meta لاحقًا يُنشر كـReel عام.
   - **طلب تعديل:** يفتح نموذجًا لجمع الملاحظة، ولا ينتقل الطابور إلى الفيديو التالي.
5. يمنع `approverTelegramUserId` أي حساب آخر من اتخاذ القرار.

## البدء

اتبع [دليل الإعداد خطوة بخطوة](n8n/SETUP-AR.md). لا تضع Bot Token أو Page Access Token في ملف، في Workflow، أو في المحادثة؛ خزّنهما داخل **Credentials** في n8n فقط.

## المحتوى

| اليوم | الموضوع | الملف |
|---:|---|---|
| 1 | تقديم الصفحة | [Reel](content/week-01/assets/day-01/reel.mp4) |
| 2 | قاعدة Prompt من ثلاثة أجزاء | [Reel](content/week-01/assets/day-02/reel.mp4) |
| 3 | ثلاث مهام يومية للـAI | [Reel](content/week-01/assets/day-03/reel.mp4) |
| 4 | التحقق من إجابات AI | [Reel](content/week-01/assets/day-04/reel.mp4) |
| 5 | الخصوصية قبل رفع الملفات | [Reel](content/week-01/assets/day-05/reel.mp4) |
| 6 | تحويل AI إلى مدرّب | [Reel](content/week-01/assets/day-06/reel.mp4) |
| 7 | تحدّي القنّاص الأول | [Reel](content/week-01/assets/day-07/reel.mp4) |

## مواصفات الفيديو

الفيديوهات مضبوطة على:

- MP4 / H.264 High Profile، مسح تدريجي و`yuv420p`.
- نسبة 9:16 ودقة 1080×1920.
- 30 إطارًا في الثانية.
- AAC‑LC، ستيريو، 48 kHz، بمعدل مستهدف 128 kbps.
- مدة كل فيديو بين 35 و47 ثانية.
- Keyframe كل ثلاث ثوانٍ تقريبًا وClosed GOP.

هذه الإعدادات تتوافق مع المواصفات الموصى بها في دليل Meta الحالي لنشر Reels.

## إعادة التوليد

بعد تثبيت FFmpeg أو السماح للأداة بتنزيل نسخته، يمكن إعادة إخراج الأيام 2–7:

```bash
python3 -m venv .venv-media
.venv-media/bin/pip install -r sniper-tn-agent/tools/requirements.txt
.venv-media/bin/python sniper-tn-agent/tools/render_reels.py
python3 sniper-tn-agent/tools/build_n8n_workflow.py
```

لا تُرفع `.venv-media` إلى Git.
