# Survey of AI podcast software

Various projects involving automated media generation from Hacker News Content

---

Podcastfy.ai (https://news.ycombinator.com/item?id=41852401)

An Open Source Python alternative to NotebookLM's podcast feature: Transforming Multimodal Content into Captivating Multilingual Audio Conversations with GenAI

Podcastfy is an open-source Python package that transforms multi-modal content (text, images) into engaging, multi-lingual audio conversations using GenAI. Input content includes websites, PDFs, images, YouTube videos, as well as user provided topics.

Unlike closed-source UI-based tools focused primarily on research synthesis (e.g. NotebookLM ❤️), Podcastfy focuses on open source, programmatic and bespoke generation of engaging, conversational content from a multitude of multi-modal sources, enabling customization and scale.

---

TwoCast (https://github.com/panyanyany/Twocast, http://twocast.app/)

✨ Key Features
👥 Two-person Podcast
⏱️ Generate 3-5 minute podcasts with one click
🧠 Supports multiple generation methods: Topic, Link, Document (doc/pdf/txt), List Page (5-9 minutes)
🌍 Multi-language support
⬇️ Downloadable audio
📋 Podcast content includes: Audio, Outline, Script
🔌 Supports three major platforms: Fish Audio, Minimax, Google Gemini

Environment Variable Configuration
🔊 TTS API Configuration
🎏 Fish Audio
Register and get an API Key: Fish Audio, and enter it in FISH_AUDIO_TOKEN=
🦾 Minimax (Optional)
Get GroupID from Profile, and enter it in MINIMAX_GROUP_ID=
Get API Key from API keys, and enter it in MINIMAX_TOKEN=
Enable: MINIMAX_ENABLED=1
🌈 Google Gemini (Optional, more expensive)
Get API Key from Google AI Studio, and enter it in GEMINI_TOKEN=
Enable: GEMINI_ENABLED=1
🤖 LLM API Configuration
💬 Chat: Get API Key from OpenRouter, and enter it in LLM_API_KEY=
🔍 Search: Get API Key from x.ai, and enter it in LLM_SEARCH_API_KEY=

---

Hackercast (https://camrobjones.com/hackercast/)

About Hackercast

I made this as a fun side-project to try out summarization with langchain (and because I get the Hacker Newsletter every Friday and never get round to reading it).

It works by scraping the Hacker Newsletter, summarizing the individual articles using Langchain and GPT-4, and then converting the text to speech using AWS Polly.

I'm basically pretty impressed by the quality of the summaries, although there are definitiely still some issues. The summaries of github pages are often pretty weird, and sometimes the analyses are very repetitive. I'm planning to try to improve the prompt to deal with these issues. At the end of the day some of the articles just don't work well as audio summaries. It currently ignores forum posts and comments, which I might try to include, as well as video links, which I probably won't.

The project is not associated with Hacker News, Y Combinator, or the Hacker Newsletter.

---

Hacker News Recap (https://hackernewsrecap.buzzsprout.com/)

A podcast that recaps some of the top posts on Hacker News every day. This is a third-party project, independent from HN and YC. Text and audio generated using AI, by Wondercraft.ai. Create your own news rundown podcast at app.wondercraft.ai

---

A Personanlized News Podcast Generator (https://news.ycombinator.com/item, https://github.com/c0ld-w4ter/you-fm)


You need to set up the API keys to run it.
If you don't want to spend time setting it up and just want to hear the output; I've uploaded an example audio here - https://soundcloud.com/irish_coder/youfm-example

-------------------------------

Here's how the application works... 1. Gather info about the user's interests and quirks with the UI

2. Gather the latest news articles for today

3. Gather weather info for the user's location

4. Rank the news articles according to the users potential interest using Gemini flash 2.5

5. Create the custom podcast script using Gemini Pro 2.5 using all the info gathered.

6. Use ElevenLabs TTS to generate the audio.

The project is at an early stage. Cursor, Claude 4 and Gemini were used. It's still quite rough.

What I want to add next...

- CLI interface

- Ability to Schedule the Job

- More sources such as RSS, Reddit etc

- Improve UI

---

Hacker News to Video Content (https://n8n.io/workflows/2557-hacker-news-to-video-content/)

Hacker News to Video Content
Overview
This workflow converts trending articles from Hacker News into engaging video content. It integrates AI-based tools to analyze, summarize, and generate multimedia content, making it ideal for content creators, educators, and marketers.

Features
Article Retrieval:

Pulls trending articles from Hacker News.
Limits the number of articles to process (configurable).
Content Analysis:

Uses OpenAI's GPT model to:
Summarize articles.
Assess their relevance to specific topics like automation or AI.
Extract key image URLs.
Image and Video Generation:

Leonardo.ai: Creates stunning AI-generated images based on extracted prompts.
RunwayML: Converts images into high-quality videos.
Structured Content Creation:

Parses content into structured formats for easy reuse.
Generates newsletter-friendly blurbs and social media-ready captions.
Cloud Integration:

Uploads generated assets to:
Dropbox
Google Drive
Microsoft OneDrive
MinIO
Social Media Posting (Optional):

Supports posting to YouTube, X (Twitter), LinkedIn, and Instagram.
Workflow Steps
1. Trigger
Initiated manually via the "Test Workflow" button.
2. Fetch Articles
Retrieves articles from Hacker News.
Limits the results to avoid processing overload.
3. Content Filtering
Evaluates if articles are related to AI/Automation using OpenAI's language model.
4. Image and Video Generation
Generates:
AI-driven image prompts via Leonardo.ai.
Videos using RunwayML.
5. Asset Management
Saves the output to cloud storage services or uploads directly to social media platforms.
Prerequisites
API Keys:

Hacker News
OpenAI
Leonardo.ai
RunwayML
Creatomate
n8n Installation:
Ensure n8n is installed and configured locally or on a server.

Credentials:
Set up credentials in n8n for all external services used in the workflow.

Customization
Replace Hacker News with any other data source node if needed.
Configure the "Article Analysis" node for different topics.
Adjust the cloud storage services or add custom storage options.
Usage
Import this workflow into your n8n instance.
Configure your API credentials.
Trigger the workflow manually or schedule it as needed.
Check the outputs in your preferred cloud storage or social media platform.
Notes
Extend this workflow further by automating social media posting or newsletter integration.
For any questions, refer to the official documentation or reach out to the creator.
About the Creator
This workflow was built by AlexK1919, an AI-native workflow automation architect. Check out the overview video for a quick demo.

Tools Used
Leonardo.ai
RunwayML
Creatomate
Hacker News API
OpenAI GPT

---

Hacker News 每日播报 (https://hacker-news.agi.li, https://github.com/ccbikai/hacker-news)

主要特性
🤖 自动抓取 Hacker News 每日热门文章
🎯 使用 AI 智能总结文章内容和评论
🎙️ 通过 Edge TTS 生成中文播报
📱 支持网页和播客 App 收听
🔄 每日自动更新
📝 提供文章摘要和完整播报文本
技术栈
Next.js 应用框架
Cloudflare Workers 部署和运行环境
Edge TTS 语音合成
OpenAI API 内容生成
Tailwind CSS 样式处理
shadcn-ui 组件库
工作流程
定时抓取 Hacker News 热门文章
使用 AI 生成中文摘要和播报文稿
通过 TTS 转换为音频, 感谢 Minimax Audio 赞助 TTS 服务。
存储到 Cloudflare R2 和 KV
通过 RSS feed 和网页提供访问