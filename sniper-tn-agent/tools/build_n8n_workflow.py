#!/usr/bin/env python3
"""Build the importable n8n workflow from the approved week-one content file."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "sniper-tn-agent/content/week-01/content.json"
OUTPUT = ROOT / "sniper-tn-agent/n8n/sniper-tn-telegram-approval.json"
NAMESPACE = uuid.UUID("f2f4e176-5be9-4dc5-a877-68d62eab3529")


def uid(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))


def node(name: str, node_type: str, version: float, position: list[int], parameters: dict, **extra) -> dict:
    value = {
        "parameters": parameters,
        "id": uid(f"node:{name}"),
        "name": name,
        "type": node_type,
        "typeVersion": version,
        "position": position,
    }
    value.update(extra)
    return value


def edge(target: str, index: int = 0) -> dict:
    return {"node": target, "type": "main", "index": index}


def build() -> dict:
    source = json.loads(CONTENT.read_text(encoding="utf-8"))
    posts = []
    for post in source["posts"]:
        posts.append(
            {
                "id": post["id"],
                "sequence": post["sequence"],
                "pillar": post["pillar"],
                "title": post["title"],
                "hook": post["hook"],
                "narration": post["narration"],
                "caption": post["caption"],
                "pinnedComment": post["pinned_comment"],
                "hashtags": post["hashtags"],
                "durationSeconds": post["duration_seconds"],
            }
        )

    posts_json = json.dumps(posts, ensure_ascii=False, separators=(",", ":"))
    load_code = f"""const config = $input.first().json;
const posts = {posts_json};
const state = $getWorkflowStaticData('global');
if (!Number.isInteger(state.nextIndex) || state.nextIndex < 0 || state.nextIndex >= posts.length) {{
  state.nextIndex = 0;
}}
const post = posts[state.nextIndex];
const day = String(post.sequence).padStart(2, '0');
const hashtagsText = post.hashtags.join(' ');
const videoUrl = `${{config.assetBaseUrl}}/day-${{day}}/reel.mp4`;
const thumbnailUrl = `${{config.assetBaseUrl}}/day-${{day}}/thumbnail.jpg`;
const approvalMessage = [
  `مراجعة المحتوى ${{post.id}}`,
  `العنوان: ${{post.title}}`,
  `المحور: ${{post.pillar}}`,
  '',
  'نص التعليق الصوتي:',
  post.narration,
  '',
  'نص منشور فيسبوك:',
  `${{post.caption}}\\n\\n${{hashtagsText}}`,
  '',
  `التعليق المثبّت: ${{post.pinnedComment}}`,
  '',
  config.facebookAutoPublish
    ? 'بالضغط على اعتماد، توافق على نشر هذا الـReel علنًا على صفحة Facebook.'
    : 'النشر الآلي معطّل حاليًا؛ الاعتماد سينقله إلى قائمة الجاهز للنشر.'
].join('\\n');
return [{{ json: {{ ...config, ...post, hashtagsText, videoUrl, thumbnailUrl, approvalMessage, queueIndex: state.nextIndex }} }}];"""

    advance_code = """const content = $('Load Next Content').item.json;
const state = $getWorkflowStaticData('global');
const current = Number.isInteger(content.queueIndex) ? content.queueIndex : 0;
state.nextIndex = (current + 1) % 7;
state.lastApproved = {
  id: content.id,
  approvedAt: new Date().toISOString(),
  facebookAutoPublish: content.facebookAutoPublish,
};
return [{ json: { ...content, status: 'approved', nextQueueIndex: state.nextIndex, metaResult: $input.first().json } }];"""

    revision_code = """const content = $('Load Next Content').item.json;
const response = $input.first().json.data || {};
const state = $getWorkflowStaticData('global');
state.lastRevision = {
  id: content.id,
  notes: response.text || 'لم تُكتب ملاحظات',
  requestedAt: new Date().toISOString(),
};
return [{ json: { ...content, status: 'revision_requested', revisionNotes: state.lastRevision.notes } }];"""

    validate_code = """const item = $input.first().json;
const missing = [];
for (const key of ['telegramChatId', 'approverTelegramUserId', 'assetBaseUrl']) {
  if (!item[key] || String(item[key]).includes('REPLACE_WITH')) missing.push(key);
}
if (missing.length) {
  throw new Error(`أكمل القيم التالية داخل عقدة Configuration قبل التشغيل: ${missing.join(', ')}`);
}
if (item.facebookAutoPublish && (!item.facebookPageId || String(item.facebookPageId).includes('REPLACE_WITH'))) {
  throw new Error('أدخل facebookPageId أو عطّل Facebook Auto-Publish.');
}
return [{ json: item }];"""

    nodes = [
        node(
            "Daily at 16:00 Tunis",
            "n8n-nodes-base.scheduleTrigger",
            1.3,
            [-1280, -40],
            {
                "rule": {
                    "interval": [
                        {"field": "days", "daysInterval": 1, "triggerAtHour": 16, "triggerAtMinute": 0}
                    ]
                }
            },
        ),
        node("Manual Test", "n8n-nodes-base.manualTrigger", 1, [-1280, 120], {}),
        node(
            "Configuration",
            "n8n-nodes-base.set",
            3.4,
            [-1040, 40],
            {
                "mode": "manual",
                "assignments": {
                    "assignments": [
                        {
                            "id": uid("field:telegramChatId"),
                            "name": "telegramChatId",
                            "value": "REPLACE_WITH_TELEGRAM_CHAT_ID",
                            "type": "string",
                        },
                        {
                            "id": uid("field:approverTelegramUserId"),
                            "name": "approverTelegramUserId",
                            "value": "REPLACE_WITH_TELEGRAM_USER_ID",
                            "type": "string",
                        },
                        {
                            "id": uid("field:assetBaseUrl"),
                            "name": "assetBaseUrl",
                            "value": "https://raw.githubusercontent.com/saaidiaa/n8n-docs/refs/heads/arena/019fee1e-n8n-docs/sniper-tn-agent/content/week-01/assets",
                            "type": "string",
                        },
                        {
                            "id": uid("field:facebookPageId"),
                            "name": "facebookPageId",
                            "value": "REPLACE_WITH_FACEBOOK_PAGE_ID",
                            "type": "string",
                        },
                        {
                            "id": uid("field:facebookAutoPublish"),
                            "name": "facebookAutoPublish",
                            "value": False,
                            "type": "boolean",
                        },
                    ]
                },
                "includeOtherFields": False,
                "options": {},
            },
        ),
        node("Validate Configuration", "n8n-nodes-base.code", 2, [-800, 40], {"jsCode": validate_code}),
        node("Load Next Content", "n8n-nodes-base.code", 2, [-560, 40], {"jsCode": load_code}),
        node(
            "Send Video Preview",
            "n8n-nodes-base.telegram",
            1.2,
            [-320, 40],
            {
                "resource": "message",
                "operation": "sendVideo",
                "chatId": "={{ $('Load Next Content').item.json.telegramChatId }}",
                "binaryData": False,
                "file": "={{ $('Load Next Content').item.json.videoUrl }}",
                "replyMarkup": "none",
                "additionalFields": {
                    "caption": "=🎬 {{ $('Load Next Content').item.json.id }} — {{ $('Load Next Content').item.json.title }}\n\n{{ $('Load Next Content').item.json.hook }}",
                    "parse_mode": "HTML",
                    "duration": "={{ $('Load Next Content').item.json.durationSeconds }}",
                    "width": 1080,
                    "height": 1920,
                },
            },
        ),
        node(
            "Approve or Request Changes",
            "n8n-nodes-base.telegram",
            1.2,
            [-60, 40],
            {
                "resource": "message",
                "operation": "sendAndWait",
                "chatId": "={{ $('Load Next Content').item.json.telegramChatId }}",
                "message": "={{ $('Load Next Content').item.json.approvalMessage }}",
                "responseType": "approval",
                "approvalOptions": {
                    "values": {
                        "approvalType": "double",
                        "approveLabel": "✅ اعتماد",
                        "disapproveLabel": "✏️ طلب تعديل",
                    }
                },
                "chatApproval": True,
                "approverIds": "={{ $('Load Next Content').item.json.approverTelegramUserId }}",
                "unauthorizedReplyText": "هذا الحساب غير مخوّل لاتخاذ القرار.",
                "postDecisionBehavior": "showOutcome",
                "options": {
                    "appendAttribution": False,
                    "limitWaitTime": {
                        "values": {"limitType": "afterTimeInterval", "resumeAmount": 20, "resumeUnit": "hours"}
                    },
                },
            },
            webhookId=uid("webhook:approval"),
        ),
        node(
            "Approved?",
            "n8n-nodes-base.if",
            2.2,
            [200, 40],
            {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict",
                        "version": 2,
                    },
                    "conditions": [
                        {
                            "id": uid("condition:approved"),
                            "leftValue": "={{ $json.data.approved }}",
                            "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                    "combinator": "and",
                },
                "options": {},
            },
        ),
        node(
            "Facebook Auto-Publish?",
            "n8n-nodes-base.if",
            2.2,
            [700, -100],
            {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict",
                        "version": 2,
                    },
                    "conditions": [
                        {
                            "id": uid("condition:autoPublish"),
                            "leftValue": "={{ $json.facebookAutoPublish }}",
                            "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                    "combinator": "and",
                },
                "options": {},
            },
        ),
        node(
            "Prepare Approved Content",
            "n8n-nodes-base.code",
            2,
            [460, -100],
            {
                "jsCode": "const content = $('Load Next Content').item.json;\nreturn [{ json: { ...content, approvedAt: new Date().toISOString() } }];"
            },
        ),
        node(
            "Start Facebook Reel Upload",
            "n8n-nodes-base.httpRequest",
            4.2,
            [940, -220],
            {
                "method": "POST",
                "url": "=https://graph.facebook.com/v26.0/{{ $('Prepare Approved Content').item.json.facebookPageId }}/video_reels",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": '={"upload_phase":"start"}',
                "options": {},
            },
        ),
        node(
            "Upload Hosted Reel",
            "n8n-nodes-base.httpRequest",
            4.2,
            [1180, -220],
            {
                "method": "POST",
                "url": "={{ $json.upload_url }}",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {
                            "name": "file_url",
                            "value": "={{ $('Prepare Approved Content').item.json.videoUrl }}",
                        }
                    ]
                },
                "options": {},
            },
        ),
        node(
            "Publish Facebook Reel",
            "n8n-nodes-base.httpRequest",
            4.2,
            [1420, -220],
            {
                "method": "POST",
                "url": "=https://graph.facebook.com/v26.0/{{ $('Prepare Approved Content').item.json.facebookPageId }}/video_reels",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ { upload_phase: 'finish', video_id: $('Start Facebook Reel Upload').item.json.video_id, video_state: 'PUBLISHED', title: $('Prepare Approved Content').item.json.title, description: $('Prepare Approved Content').item.json.caption + '\\n\\n' + $('Prepare Approved Content').item.json.hashtagsText } }}",
                "options": {},
            },
        ),
        node("Advance Queue", "n8n-nodes-base.code", 2, [1660, -60], {"jsCode": advance_code}),
        node(
            "Published on Facebook?",
            "n8n-nodes-base.if",
            2.2,
            [1900, -60],
            {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict",
                        "version": 2,
                    },
                    "conditions": [
                        {
                            "id": uid("condition:published"),
                            "leftValue": "={{ $json.facebookAutoPublish }}",
                            "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                    "combinator": "and",
                },
                "options": {},
            },
        ),
        node(
            "Telegram Published Confirmation",
            "n8n-nodes-base.telegram",
            1.2,
            [2160, -160],
            {
                "resource": "message",
                "operation": "sendMessage",
                "chatId": "={{ $json.telegramChatId }}",
                "text": "=✅ تم اعتماد ونشر {{ $json.id }} على صفحة Facebook.\n\nالعنوان: {{ $json.title }}\nالمحتوى التالي في الطابور: {{ $json.nextQueueIndex + 1 }} من 7.",
                "additionalFields": {"appendAttribution": False, "disable_web_page_preview": True},
            },
        ),
        node(
            "Telegram Ready Confirmation",
            "n8n-nodes-base.telegram",
            1.2,
            [2160, 40],
            {
                "resource": "message",
                "operation": "sendMessage",
                "chatId": "={{ $json.telegramChatId }}",
                "text": "=✅ تم اعتماد {{ $json.id }} ووضعه في قائمة الجاهز للنشر.\n\nالنشر الآلي على Facebook ما زال معطّلًا للأمان. فعّله فقط بعد ربط Meta واختبار المسار يدويًا.",
                "additionalFields": {"appendAttribution": False, "disable_web_page_preview": True},
            },
        ),
        node(
            "Collect Revision Notes",
            "n8n-nodes-base.telegram",
            1.2,
            [460, 240],
            {
                "resource": "message",
                "operation": "sendAndWait",
                "chatId": "={{ $('Load Next Content').item.json.telegramChatId }}",
                "message": "=✏️ اكتب التعديلات المطلوبة للمحتوى {{ $('Load Next Content').item.json.id }}.",
                "responseType": "freeText",
                "options": {
                    "messageButtonLabel": "إرسال التعديلات",
                    "responseFormTitle": "تعديلات محتوى Sniper-Tn",
                    "responseFormDescription": "اكتب التغيير المطلوب في النص أو الصوت أو التصميم.",
                    "responseFormButtonLabel": "إرسال",
                    "appendAttribution": False,
                    "limitWaitTime": {
                        "values": {"limitType": "afterTimeInterval", "resumeAmount": 20, "resumeUnit": "hours"}
                    },
                },
            },
            webhookId=uid("webhook:revision"),
        ),
        node("Record Revision", "n8n-nodes-base.code", 2, [700, 240], {"jsCode": revision_code}),
        node(
            "Telegram Revision Confirmation",
            "n8n-nodes-base.telegram",
            1.2,
            [940, 240],
            {
                "resource": "message",
                "operation": "sendMessage",
                "chatId": "={{ $json.telegramChatId }}",
                "text": "=📝 تم تسجيل تعديل {{ $json.id }}:\n\n{{ $json.revisionNotes }}\n\nلن ينتقل الطابور إلى المحتوى التالي حتى يُعتمد هذا المحتوى.",
                "additionalFields": {"appendAttribution": False, "disable_web_page_preview": True},
            },
        ),
        node(
            "Setup — required before activation",
            "n8n-nodes-base.stickyNote",
            1,
            [-1090, -330],
            {
                "content": "## الإعداد الإلزامي\n1. عدّل قيم **Configuration**.\n2. اختر Telegram credential في جميع عقد Telegram.\n3. نفّذ **Manual Test** قبل تفعيل الجدول.\n4. اترك Facebook Auto-Publish = false في البداية.",
                "height": 250,
                "width": 460,
                "color": 5,
            },
        ),
        node(
            "Meta publishing safety",
            "n8n-nodes-base.stickyNote",
            1,
            [900, -520],
            {
                "content": "## نشر Meta — معطّل افتراضيًا\nأنشئ HTTP Header Auth credential:\n- Name: `Authorization`\n- Value: `OAuth PAGE_ACCESS_TOKEN`\nثم اختره في عقد Meta الثلاث واختبر يدويًا قبل تفعيل النشر.",
                "height": 250,
                "width": 520,
                "color": 4,
            },
        ),
    ]

    connections = {
        "Daily at 16:00 Tunis": {"main": [[edge("Configuration")]]},
        "Manual Test": {"main": [[edge("Configuration")]]},
        "Configuration": {"main": [[edge("Validate Configuration")]]},
        "Validate Configuration": {"main": [[edge("Load Next Content")]]},
        "Load Next Content": {"main": [[edge("Send Video Preview")]]},
        "Send Video Preview": {"main": [[edge("Approve or Request Changes")]]},
        "Approve or Request Changes": {"main": [[edge("Approved?")]]},
        "Approved?": {
            "main": [
                [edge("Prepare Approved Content")],
                [edge("Collect Revision Notes")],
            ]
        },
        "Prepare Approved Content": {"main": [[edge("Facebook Auto-Publish?")]]},
        "Facebook Auto-Publish?": {
            "main": [
                [edge("Start Facebook Reel Upload")],
                [edge("Advance Queue")],
            ]
        },
        "Start Facebook Reel Upload": {"main": [[edge("Upload Hosted Reel")]]},
        "Upload Hosted Reel": {"main": [[edge("Publish Facebook Reel")]]},
        "Publish Facebook Reel": {"main": [[edge("Advance Queue")]]},
        "Advance Queue": {"main": [[edge("Published on Facebook?")]]},
        "Published on Facebook?": {
            "main": [
                [edge("Telegram Published Confirmation")],
                [edge("Telegram Ready Confirmation")],
            ]
        },
        "Collect Revision Notes": {"main": [[edge("Record Revision")]]},
        "Record Revision": {"main": [[edge("Telegram Revision Confirmation")]]},
    }

    return {
        "name": "Sniper-Tn — Telegram Approval and Facebook Reels",
        "nodes": nodes,
        "pinData": {},
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "timezone": "Africa/Tunis",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "availableInMCP": False,
        },
        "versionId": uid("workflow:version"),
        "meta": {"templateCredsSetupCompleted": False},
        "tags": [],
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
