# Git-Synced Maker Blog

This repository hosts a lightweight blog that reads posts from a separate public git repository, pulls updates on a schedule, and republishes them as a self-hosted website.

The design goal is low complexity:

- one small Python app
- one nginx reverse proxy
- optional Certbot for HTTPS
- no GitHub authentication needed for public repositories

## How it works

The `blog` container clones the configured repository, hard-resets to the selected branch on each sync, parses markdown posts, copies assets, and serves the rendered site.

The sync logic uses plain `git clone` and `git fetch` over HTTPS, so public GitHub repositories work without tokens or SSH keys.

Markdown rendering is handled through Python markdown libraries rather than ad-hoc string conversion. The app currently supports standard Markdown plus tables, fenced code blocks, task lists, footnotes, and Obsidian-style image embeds.

## Supported diary format

The source repository can be any git repository as long as it follows this shape:

1. Posts are markdown files under `POSTS_PATH` (default: repository root).
2. Posts can include YAML front matter.
3. `created` is used as the post date when present.
4. `tags` can be a list or a string.
5. `title` is optional. If omitted, the filename becomes the title.
6. Obsidian image embeds in the form `![[file-name.png]]` are supported.
7. Assets are copied from the directories listed in `ASSET_DIRECTORIES` (default: `pasted images`).

Example:

```md
---
created: 2026-03-21
tags:
  - diary
  - electronics
title: keypad part 1
---
Today I worked on a keypad.

![[Pasted image 20260321111618.png]]
```

## Local HTTP setup

1. Copy `.env.example` to `.env`.
2. Set `DIARY_REPOSITORY_URL` to the public git repository you want to publish.
3. Start the stack:

```sh
docker compose up --build -d
```

The blog will be available through nginx on `http://localhost` or the host and port you mapped with `HTTP_PORT`.

## HTTPS with Certbot

This repository includes an nginx + Certbot deployment path for Let's Encrypt certificates.

1. Set `DOMAIN` and `LETSENCRYPT_EMAIL` in `.env`.
2. Make sure your domain already points to the host running Docker.
3. Request the first certificate:

```sh
sh deploy/init-letsencrypt.sh
```

4. From then on, run the HTTPS stack with:

```sh
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```

The Certbot container renews certificates every 12 hours and nginx serves both HTTP and HTTPS.

## Configuration

Environment variables:

- `SITE_TITLE`: site name shown in the UI.
- `SITE_DESCRIPTION`: subtitle used in the UI and metadata.
- `DIARY_REPOSITORY_URL`: public git clone URL for the diary repository.
- `DIARY_BRANCH`: branch to publish.
- `POSTS_PATH`: folder inside the repository containing markdown posts.
- `ASSET_DIRECTORIES`: comma-separated directories to copy as assets.
- `SYNC_INTERVAL_SECONDS`: how often the app refreshes the source repository.
- `HTTP_PORT`: host port for nginx HTTP.
- `HTTPS_PORT`: host port for nginx HTTPS.

## Notes

- The source repository stays separate from this deployment repository.
- The app currently targets public repositories only.
- Embedded wiki-links other than images are not converted.
- Parts of this repository were produced with heavy LLM assistance during implementation. Review the code and deployment configuration yourself before using it in production.
