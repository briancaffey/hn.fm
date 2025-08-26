# Survey of AI-Generated Podcasts from Hacker News Content

Over the past year, developers have experimented with turning Hacker News content into podcasts using a mix of open-source tools, commercial APIs, and automation workflows. The resulting projects range from polished daily shows to early-stage prototypes, each exploring a different corner of AI media generation.

---

### **Podcastfy.ai**

[HN thread](https://news.ycombinator.com/item?id=41852401)

Podcastfy positions itself as an open-source alternative to Google’s NotebookLM podcast feature. Built as a Python package, it transforms multi-modal sources—websites, PDFs, YouTube videos, and even images—into conversational, multilingual audio. Unlike commercial SaaS tools, Podcastfy emphasizes customization and programmatic generation. Its open-source model makes it appealing for developers who want flexibility without being locked into a cloud provider.

---

### **TwoCast**

[GitHub](https://github.com/panyanyany/Twocast) · [App](http://twocast.app/)

TwoCast focuses on generating short, two-person podcasts (3–9 minutes). The platform is cloud-centric, leaning heavily on external services for both language models and speech synthesis. It integrates Fish Audio, Minimax, and Google Gemini for TTS, while OpenRouter and x.ai provide LLM and search APIs. This reliance on commercial APIs makes setup more complex but enables users to tap into high-quality voices and multiple languages. TwoCast is open source, but the heavy dependency on paid keys means practical usage depends on cloud accounts.

---

### **Hackercast**

[Project site](https://camrobjones.com/hackercast/)

Hackercast is a hobby project that uses **LangChain**, **GPT-4**, and **AWS Polly** to summarize articles from the weekly *Hacker Newsletter*. The result is a podcast that feels closer to an automated reading assistant than a slick news show. It deliberately avoids forum posts, comments, and videos, focusing instead on newsletter links. As a side project, Hackercast is less about distribution polish and more about testing whether HN summaries “work” as audio content.

---

### **Hacker News Recap**

[Podcast feed](https://hackernewsrecap.buzzsprout.com/)

Unlike the DIY experiments above, Hacker News Recap is a public-facing, daily show built with **Wondercraft.ai**. Each episode recaps top HN posts, turning them into audio news summaries. This is more of a hosted service than an open-source tool: the podcast itself is independent from Hacker News, but the underlying tech depends entirely on Wondercraft’s proprietary platform.

---

### **A Personalized News Podcast Generator (You-FM)**

[GitHub](https://github.com/c0ld-w4ter/you-fm)

You-FM is still early-stage but ambitious. It personalizes podcasts by combining daily news, weather, and user interests, then ranking articles with **Google Gemini Flash**, drafting scripts with **Gemini Pro**, and voicing them with **ElevenLabs**. The project is open source but cloud-dependent: every run requires multiple API keys, and the current prototype is rough around the edges. Planned improvements include scheduling, more sources (like Reddit), and a CLI option.

---

### **Hacker News to Video Content (n8n Workflow)**

[n8n workflow](https://n8n.io/workflows/2557-hacker-news-to-video-content/)

This project expands beyond podcasts into **video generation**. Using **n8n**, it pulls trending HN articles, summarizes them with OpenAI GPT, then generates visuals via Leonardo.ai and RunwayML. The workflow includes cloud storage integrations (Dropbox, Google Drive, OneDrive, MinIO) and optional social media posting to YouTube, X, LinkedIn, and Instagram. Unlike smaller projects, this one positions itself as a tool for creators and marketers, not just HN enthusiasts. It’s not a podcast in the traditional sense, but it shows how HN content can seed automated multimedia pipelines.

---

### **Hacker News 每日播报**

[Site](https://hacker-news.agi.li) · [GitHub](https://github.com/ccbikai/hacker-news)

A fully localized spin: Hacker News Daily Broadcast delivers Chinese-language audio recaps of trending HN posts. Built with **Next.js** and deployed on **Cloudflare Workers**, it uses **OpenAI** for summarization and **Edge TTS** (via Minimax sponsorship) for voice generation. The project automatically updates daily, stores content in Cloudflare R2/KV, and distributes via RSS and podcast apps. It’s a polished example of regional adaptation—taking global HN content and tailoring it for a non-English audience.

---

## **Takeaways**

* **Open Source vs. SaaS**: Projects like Podcastfy, TwoCast, and You-FM open their codebases, while Hacker News Recap leans on hosted platforms.
* **Cloud Reliance**: Most rely on commercial APIs—OpenAI, Gemini, ElevenLabs, AWS Polly—making full self-hosting difficult. Hacker News 每日播报 is notable for its serverless Cloudflare deployment.
* **Format Diversity**: Some stick to podcasts (Hackercast, Recap), others extend to personalized news (You-FM), multilingual conversations (Podcastfy), or even video workflows (n8n).
* **Community vs. Production**: Hackercast and Podcastfy reflect developer tinkering, while Hacker News Recap and 每日播报 show how far polish can go when distribution is the focus.

Together, these projects illustrate the range of ways developers and creators are experimenting with transforming Hacker News content into AI-generated media—from playful side projects to production-ready daily shows.

| Project                                   | Open Source | Cloud / API Dependencies                             | Format            | Notable Features |
|-------------------------------------------|-------------|------------------------------------------------------|-------------------|------------------|
| [Podcastfy.ai](https://news.ycombinator.com/item?id=41852401) | ✅ Yes      | None required; customizable locally                  | Podcast (multi-modal) | Multi-lingual, multimodal input (web, PDFs, YouTube, images) |
| [TwoCast](https://github.com/panyanyany/Twocast) | ✅ Yes      | Fish Audio, Minimax, Google Gemini, OpenRouter, x.ai | Podcast (2-person) | Short conversational shows, multi-language, scripts & outlines |
| [Hackercast](https://camrobjones.com/hackercast/) | ❌ No       | OpenAI GPT-4, AWS Polly                              | Podcast (summaries) | Based on Hacker Newsletter, experimental hobby project |
| [Hacker News Recap](https://hackernewsrecap.buzzsprout.com/) | ❌ No       | Wondercraft.ai                                       | Daily podcast     | Polished distribution, recap of top posts |
| [You-FM](https://github.com/c0ld-w4ter/you-fm) | ✅ Yes      | Google Gemini, ElevenLabs                            | Personalized podcast | News + weather + user interests, early-stage |
| [HN to Video (n8n)](https://n8n.io/workflows/2557-hacker-news-to-video-content/) | ⚠️ Partial | OpenAI, Leonardo.ai, RunwayML, Dropbox, Google Drive | Video + audio     | Multimedia workflow, integrates with social platforms |
| [Hacker News 每日播报](https://hacker-news.agi.li) | ✅ Yes      | OpenAI, Edge TTS (Minimax), Cloudflare Workers/R2    | Daily Chinese podcast | Full Chinese summaries, Cloudflare-native deployment |
