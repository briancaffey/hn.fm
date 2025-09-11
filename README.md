# hn.fm

Transform Hacker News into AI-powered podcasts using content scraping, AI processing, text-to-speech, and audio enhancement.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd hn.fm
```

## Getting started

### Inference Services

- Download and install InvokeAI and download the Flux starter models, including the Flux Krea models
- Download and install the studio-voice NVIDIA NIM service
- Set up gpt-oss-20b with a sufficiently large context window (e.g. 32539)
- Set up the `dia` and `whisperx` services (see the `services/` directory)
- update the `.env` file to make sure that the ports and addresses are correct if running services across different machines

### Start the backend

Run `docker compose up`

### Start the frontend

Run `cd frontend && yarn && yarn dev`

## Queue Hacker News items

## Run the pipeline

On the item detail page click the `Single Task Pipeline` button.

## Monitor task status in Celery Flower

## View results on Segment detail page

## What It Does

1. **Scrapes Hacker News** articles for content
2. **Processes content** using AI to extract key points
3. **Generates scripts** with conversational dialogue between two hosts
4. **Creates audio** using text-to-speech with voice cloning
5. **Enhances audio** using Studio Voice for professional quality
6. **Generates images** for visual content
7. **Creates videos** combining audio and images
