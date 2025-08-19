# 🎙️ hn.fm 🟧

> **Transform Hacker News into Your Personalized AI-Powered Podcast**

[![OpenAI Hackathon](https://img.shields.io/badge/OpenAI-Hackathon-10A37F?style=for-the-badge&logo=openai)](https://hackathon.openai.com/)
[![GPT-OSS](https://img.shields.io/badge/GPT--OSS-20B-FF6B35?style=for-the-badge)](https://github.com/openai/gpt-oss)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

## 🚀 What is hn.fm?

**hn.fm** is an AI-powered content transformation engine that automatically converts the Hacker News feed into engaging, personalized podcast episodes with stunning visuals. Think of it as having your own AI news anchor that never sleeps, constantly curating and narrating the most interesting tech stories from the internet.

### ✨ Key Features

- 🎧 **AI-Generated Podcasts**: Transform HN threads into professional-quality audio content
- 🖼️ **Dynamic Visual Content**: AI-generated images and videos for multiple platforms
- 🎭 **Customizable Host Personas**: Configure your AI host's voice, style, and focus
- 🔄 **Quality Assurance**: Multi-stage validation ensures audio and content quality
- 📱 **Multi-Format Output**: Podcasts, short-form videos, and web content
- 🎵 **AI Music Generation**: Optional background music for enhanced listening experience

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Hacker News  │───▶│   AI Scraping   │───▶│  Content Agent  │
│     Feed       │    │   (Firecrawl)   │    │   Workflow      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   TTS Service  │◀───│  Script Chunks  │◀───│  Podcast Script │
│  (nari-labs)   │    │                 │    │   Generation    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Quality Check │───▶│  Studio Voice   │───▶│  Final Audio    │
│   (ASR + LLM)  │    │   Processing    │    │   Assembly      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Image Prompts  │───▶│ Flux Kontext    │───▶│ Video Assembly  │
│   Generation   │    │   NVIDIA NIM    │    │   & Export      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ Tech Stack

### 🤖 AI & Machine Learning
- **GPT-OSS 20B**: OpenAI's open-source model for content generation and quality control
- **Local TTS**: nari-labs/dia for high-quality text-to-speech
- **ASR Service**: NVIDIA Parakeet for speech-to-text validation
- **AI Scraping**: Firecrawl (self-hosted) powered by GPT-OSS

### 🎵 Audio & Video
- **Audio Processing**: Studio-quality voice enhancement
- **Image Generation**: Flux Kontext NVIDIA NIM for accelerated image creation
- **Video Production**: AI-driven video assembly from audio and images
- **Music Generation**: Local AI music generation services

### 🔧 Infrastructure
- **Content Pipeline**: Agentic workflow for intelligent content curation
- **Quality Assurance**: Multi-stage validation and regeneration
- **Multi-Format Export**: Podcast, video, and web content generation

## 🚀 Getting Started

### Prerequisites

- Modern PC/laptop capable of running GPT-OSS 20B
- Docker for containerized services
- NVIDIA GPU (optional, for accelerated image generation)
- Python 3.9+

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/hn.fm.git
cd hn.fm

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start the services
docker-compose up -d

# Run the main application
python main.py
```

### Configuration

Create a `config.yaml` file to customize your AI host:

```yaml
host:
  name: "TechNews AI"
  voice: "professional"
  style: "enthusiastic"
  focus: "startup culture and AI trends"

content:
  max_episode_length: "15 minutes"
  include_comments: true
  quality_threshold: 0.8

output:
  formats: ["podcast", "short_video", "web"]
  image_aspect_ratios: ["16:9", "9:16", "1:1"]
```

## 📖 How It Works

### 1. **Content Discovery**
- Scrapes Hacker News feed for trending stories
- Extracts URLs and HN comments
- Prioritizes content based on engagement and relevance

### 2. **Intelligent Processing**
- AI-powered content scraping with Firecrawl
- Agentic workflow generates podcast scripts
- Incorporates community insights from HN comments

### 3. **Audio Generation**
- Script chunking for optimal TTS processing
- Local TTS generation with nari-labs/dia
- Quality validation through ASR comparison
- Studio-quality voice enhancement

### 4. **Visual Creation**
- AI-generated image prompts based on content
- Accelerated image generation with Flux Kontext
- Multiple aspect ratios for different platforms

### 5. **Content Assembly**
- Automated video production
- Podcast episode compilation
- Web content generation
- Optional AI-generated background music

## 🎯 Use Cases

- **Content Creators**: Automate podcast and video production
- **News Enthusiasts**: Stay updated with AI-curated tech news
- **Developers**: Discover trending tech stories in audio format
- **Content Marketers**: Generate engaging social media content
- **Podcast Networks**: Scale content production with AI

## 🔮 Future Roadmap

- [ ] **Multi-Language Support**: Generate content in different languages
- [ ] **Custom RSS Feeds**: Subscribe to specific topics or sources
- [ ] **Interactive Elements**: Add Q&A segments and listener engagement
- [ ] **Advanced Analytics**: Track content performance and engagement
- [ ] **API Access**: Allow third-party integrations
- [ ] **Mobile App**: Native iOS and Android applications

## 🤝 Contributing

We're building something amazing together! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linting
flake8 src/
black src/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** for GPT-OSS and the hackathon opportunity
- **Hacker News** community for the amazing content
- **nari-labs** for the excellent TTS service
- **NVIDIA** for accelerated AI tools
- **Firecrawl** for intelligent web scraping

## 📞 Support & Community

- **Discord**: [Join our community](https://discord.gg/hnfm)
- **Twitter**: [@hnfm_ai](https://twitter.com/hnfm_ai)
- **Email**: hello@hn.fm
- **Issues**: [GitHub Issues](https://github.com/yourusername/hn.fm/issues)

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/hn.fm&type=Date)](https://star-history.com/#yourusername/hn.fm&Date)

---

**Made with ❤️ for the OpenAI Open Model Hackathon**

*Transform the way you consume tech news. One AI-powered podcast at a time.*
