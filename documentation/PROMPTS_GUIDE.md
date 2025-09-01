# Prompts Guide

Customize AI prompts for podcast script generation.

## Quick Start

Edit the prompts template:

```bash
nano prompts_template.json
```

## LLM Integration

The system uses language models to generate podcast scripts:

- **Real AI-generated content**: Each script is unique based on article content
- **Natural conversation flow**: Creates genuine dialogue between hosts
- **Context-aware responses**: Scripts adapt to specific content

## Prompt Structure

### System Prompt
Defines overall writing style and rules:

```json
"system_prompt": "You are a professional podcast script writer for a tech news show called \"hn.fm\". Your job is to convert technical articles into engaging, conversational podcast scripts.

IMPORTANT RULES:
1. ALWAYS prefix each line with speaker tags: [S1] for Host 1, [S2] for Host 2
2. Keep lines short and natural for speaking (max 2-3 sentences per line)
3. Make technical content accessible to a general tech audience
4. Include natural conversation flow between hosts
5. Add humor and personality where appropriate
6. Structure as a conversation, not a monologue
7. Include transitions and segues between topics
8. End with a call to action or thought-provoking question"
```

### Content Prompt
Converts technical content into podcast scripts:

```json
"content_prompt": "Convert the following technical content into an engaging podcast script.

CONTENT TITLE: {title}
SOURCE URL: {url}
KEY POINTS: {key_points}

REQUIREMENTS:
- Start with an engaging hook
- Break down complex concepts into digestible explanations
- Include both hosts' perspectives and reactions
- Add relevant examples or analogies
- Keep the energy high and engaging
- End with actionable insights or takeaways

Remember: Every line must start with [S1] or [S2] for the TTS system."
```

## Configuration

Set your API keys in `.env`:

```bash
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

## Customization

Modify prompts for your desired:
- **Podcast style** (formal, casual, humorous, technical)
- **Host personalities** (S1 and S2 characteristics)
- **Content focus** (beginner-friendly, expert-level)
- **Episode length** (short, medium, long)

## Speaker Tags

Every line must start with:
- `[S1]` for Host 1
- `[S2]` for Host 2

This ensures proper TTS voice assignment and conversation flow.
