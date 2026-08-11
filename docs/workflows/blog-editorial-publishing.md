---
title: Automate a professional blog editorial and publishing pipeline
description: Build a controlled content workflow that moves approved posts from a Google Sheets editorial calendar to WordPress and notifies your team.
contentType: [tutorial]
---

# Automate a professional blog editorial and publishing pipeline

Use the [downloadable workflow](/_workflows/blog/content-editorial-publishing.json) to manage a simple but reliable editorial process:

1. The workflow checks the content calendar every day at 08:00.
2. It selects only rows marked `Approved` whose `publish_at` has arrived.
3. It publishes the article to WordPress.
4. It writes the publication details back to the calendar.
5. It notifies the editorial team in Slack.

The workflow intentionally keeps the editorial approval step outside automation. This gives an editor a final review before anything becomes public.

/// warning | Review before activating
This template publishes directly to WordPress. Import it as inactive, test it with a draft WordPress site, and confirm your timezone and calendar column names before activating it.
///

## Prerequisites

You need:

* An n8n instance with permission to create workflows.
* A Google Sheets credential with access to the editorial calendar.
* A WordPress credential for a user allowed to create posts.
* A Slack credential and an editorial channel.

Create a sheet named `Content Calendar` with these columns (the spelling is significant):

| Column | Purpose |
| --- | --- |
| `title` | The final article title |
| `slug` | Optional WordPress slug |
| `content` | The final HTML or Markdown-compatible body |
| `publish_at` | An ISO 8601 date and time, such as `2026-08-15T08:00:00Z` |
| `status` | Use `Idea`, `Draft`, `In review`, `Approved`, or `Published` |
| `published_at` | Filled in by the workflow |
| `wordpress_id` | Filled in by the workflow |
| `url` | Filled in by the workflow |

For dependable row updates, enable the Google Sheets node's row-number output in your n8n version, or replace the matching field in **Mark as published** with the unique ID column used by your calendar.

## Configure the workflow

1. Import `content-editorial-publishing.json` from **Workflows > Import from File**.
2. Open **Read content calendar** and **Mark as published**, then select the same spreadsheet and `Content Calendar` sheet.
3. Open **Publish to WordPress** and select your WordPress credential.
4. Open **Notify editorial team** and select the Slack credential and channel.
5. Replace the placeholder document and channel IDs if your n8n version stores those fields as IDs.
6. Run the workflow manually with one test row. Confirm the WordPress result, the updated calendar row, and the Slack notification.
7. Activate the workflow only after testing with a non-public WordPress status or staging site.

## Editorial safeguards

* Treat `Approved` as the only status that can publish. Never use an empty status as a default.
* Keep credentials in n8n credentials; don't put passwords or tokens in the sheet.
* Use a staging site while testing and set the WordPress status to `draft` until the final review is complete.
* Add an error workflow that sends failed executions to the editorial team. Don't silently mark a row as `Published` if the WordPress step fails.
* Keep a unique content ID in the sheet and use it for matching. This prevents duplicate publications when a retry occurs.
* Set the n8n timezone to the timezone used by the editorial calendar, or store all dates in UTC.

## Extending the pipeline

After the publishing step, you can add separate branches for a newsletter, social posts, analytics tagging, or an internal archive. Keep those branches after the WordPress result so the canonical URL is available, and make each downstream action idempotent so retries don't send duplicate announcements.
