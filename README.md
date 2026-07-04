# daily-crawl

Mini support-doc ingestion pipeline for an OptiBot-style assistant. This version uses **Gemini API File Search** so it can run on Google's free tier without OpenAI billing.

## Setup

```bash
cp .env.sample .env
# Add GEMINI_API_KEY from Google AI Studio.
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
python main.py
python ask_gemini.py "How do I add a YouTube video?"
```

First run creates a Gemini File Search Store and saves its resource name in `data/store.json`. Commit `data/store.json` so future daily runs reuse the same store.

## Run with Docker

```bash
docker build -t daily-crawl .
docker run --rm -e GEMINI_API_KEY="your-key" daily-crawl
```

## How it works

1. Fetches public Help Center articles from Zendesk's article API.
2. Converts article HTML bodies to clean Markdown files in `data/markdown`.
3. Hashes each Markdown file and compares it with `data/manifest.json`.
4. Uploads only added/updated Markdown files to Gemini File Search Store.
5. Logs `added`, `updated`, `skipped`, `uploaded_files`, and `estimated_chunks_embedded` in `logs/last_run.json`.

## Chunking

Gemini File Search performs the actual indexing. This project passes a whitespace chunking config:

- `MAX_TOKENS_PER_CHUNK=512`
- `MAX_OVERLAP_TOKENS=64`

The run log includes estimated chunk counts because the API handles the real chunking server-side.

## Daily job logs

This repo includes a free GitHub Actions cron job at `.github/workflows/daily.yml`.

Setup:

1. Push this repo to GitHub.
2. Add repo secret `GEMINI_API_KEY`.
3. Open **Actions → Daily KB Sync → Run workflow** once.
4. Use the GitHub Actions run URL as the daily job logs link.

## Screenshot

Ask this after the first successful upload:

```bash
python ask_gemini.py "How do I add a YouTube video?"
```

Take a screenshot of the answer showing cited `Article URL:` lines or Gemini file citations and place it in `screenshots/sample_answer.png`.
