# 🎙️ hn.fm Prompts Guide

This guide explains how to customize and use the AI prompts in your hn.fm project to create personalized podcast content.

## 📋 Overview

The hn.fm system uses a series of carefully crafted prompts to:
1. **Process scraped content** from Hacker News articles
2. **Generate engaging podcast scripts** with proper speaker tags
3. **Create conversational dialogue** between two hosts
4. **Maintain consistent style and tone** across episodes

## 🔧 How to Customize Prompts

### 1. **LLM Integration**

The hn.fm system now uses actual language models (OpenAI GPT-4 or Anthropic Claude) to generate podcast scripts instead of hardcoded templates. This means:

- **Real AI-generated content**: Each script is uniquely created based on the article content
- **Natural conversation flow**: The LLM creates genuine dialogue between hosts
- **Context-aware responses**: Scripts adapt to the specific content being discussed
- **LLM required**: The system requires a working LLM service - no fallback templates are used

### 2. **Edit the Prompts Template**

The system automatically generates a `prompts_template.json` file that you can customize:

```bash
# Edit the prompts template
nano prompts_template.json
```

### 2. **Configure LLM Provider**

Choose your preferred language model provider:

```python
# Use OpenAI GPT-4 (default)
generator = ScriptGenerator(llm_provider="openai")

# Use Anthropic Claude
generator = ScriptGenerator(llm_provider="anthropic")
```

Set your API keys in the `.env` file:
```bash
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### 3. **Customize for Your Use Case**

Modify the prompts to match your desired:
- **Podcast style** (formal, casual, humorous, technical)
- **Host personalities** (S1 and S2 characteristics)
- **Content focus** (beginner-friendly, expert-level, etc.)
- **Episode length** (short, medium, long)

## 📝 Prompt Structure

### **System Prompt**
The foundation prompt that defines the overall writing style and rules:

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

### **Content Prompt**
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

### **Intro Prompt**
Creates compelling episode introductions:

```json
"intro_prompt": "Create a compelling podcast intro for this episode.

TITLE: {title}
TOPIC: {topic}

Make it engaging, mention the source, and set up what listeners will learn."
```

### **Outro Prompt**
Wraps up episodes effectively:

```json
"outro_prompt": "Create a podcast outro that wraps up the episode.

TITLE: {title}
KEY TAKEAWAYS: {takeaways}

Include a call to action, mention the source, and encourage engagement."
```

## 🎭 Customizing Host Personalities

### **Host 1 (S1) - The Guide**
- **Role**: Main narrator, explains concepts
- **Personality**: Knowledgeable, enthusiastic, teacher-like
- **Example**: "[S1] Welcome to hn.fm! Today we're diving into something really exciting..."

### **Host 2 (S2) - The Reactor**
- **Role**: Asks questions, shows reactions, provides perspective
- **Personality**: Curious, supportive, adds humor
- **Example**: "[S2] That's fascinating! I never thought about it that way..."

## 🎯 Content Style Examples

### **Beginner-Friendly Style**
```json
"content_prompt": "Convert the following technical content into a beginner-friendly podcast script.

REQUIREMENTS:
- Explain technical concepts in simple terms
- Use analogies and real-world examples
- Avoid jargon without explanation
- Encourage questions and curiosity
- Make complex topics feel approachable"
```

### **Expert-Level Style**
```json
"content_prompt": "Convert the following technical content into an expert-level podcast script.

REQUIREMENTS:
- Dive deep into technical details
- Assume advanced knowledge
- Discuss implementation strategies
- Explore edge cases and optimizations
- Focus on practical applications"
```

### **Humorous Style**
```json
"content_prompt": "Convert the following technical content into a humorous podcast script.

REQUIREMENTS:
- Add witty observations and jokes
- Use playful analogies
- Include tech humor and memes
- Keep it entertaining while informative
- Balance fun with educational value"
```

## 🔄 Using Custom Prompts

### **Method 1: Edit Template File**
1. Modify `prompts_template.json`
2. Restart the script generation
3. New prompts will be used automatically

### **Method 2: Create Custom Prompts File**
```bash
# Create your custom prompts
cp prompts_template.json my_custom_prompts.json
# Edit my_custom_prompts.json
# Use in script generation
```

### **Method 3: Programmatic Customization**
```python
from hnfm.content.script_generator import ScriptGenerator

# Use custom prompts file
generator = ScriptGenerator("my_custom_prompts.json")
script = generator.generate_script(processed_content)
```

## 📊 Prompt Variables

The system automatically fills in these variables:

- `{title}` - Article title
- `{url}` - Source URL
- `{key_points}` - Extracted key points
- `{topic}` - Main topic summary
- `{takeaways}` - Key insights

## 🎨 Advanced Customization

### **Adding New Prompt Types**
```json
{
  "transition_prompt": "Create smooth transitions between topics...",
  "qa_prompt": "Generate Q&A segments...",
  "summary_prompt": "Create episode summaries..."
}
```

### **Conditional Prompts**
```python
# In your custom script generator
if content.get('complexity') == 'high':
    prompt = self.prompts["expert_content_prompt"]
else:
    prompt = self.prompts["beginner_content_prompt"]
```

### **Multi-Language Support**
```json
{
  "system_prompt_en": "English system prompt...",
  "system_prompt_es": "Spanish system prompt...",
  "system_prompt_fr": "French system prompt..."
}
```

## 🧪 Testing Your Prompts

### **Quick Test**
```bash
# Run the full pipeline with your custom prompts
uv run python test_full_pipeline.py
```

### **Validate Output**
Check the generated scripts in the `outputs/` directory:
- `script_*.txt` - Full script
- `tts_lines_*.txt` - Speaker-tagged lines for TTS
- `script_meta_*.json` - Metadata and statistics

## 📚 Best Practices

### **Do's**
- ✅ Keep speaker tags consistent: `[S1]` and `[S2]`
- ✅ Make lines natural for speaking (2-3 sentences max)
- ✅ Include both hosts in conversations
- ✅ Add personality and humor
- ✅ End with clear takeaways

### **Don'ts**
- ❌ Don't create monologues
- ❌ Don't forget speaker tags
- ❌ Don't make lines too long
- ❌ Don't lose the conversational flow
- ❌ Don't ignore the target audience

## 🔧 Troubleshooting

### **Common Issues**

**Problem**: Scripts are too formal
**Solution**: Add more casual language and humor to prompts

**Problem**: Only one host speaks
**Solution**: Emphasize conversation flow in content prompts

**Problem**: Lines are too long
**Solution**: Add length constraints to prompts

**Problem**: Content is too technical
**Solution**: Use beginner-friendly language in prompts

## 🚀 Next Steps

1. **Customize your prompts** using the template
2. **Test different styles** for various content types
3. **Iterate and refine** based on output quality
4. **Create multiple prompt sets** for different audiences
5. **Integrate with your LLM** for dynamic generation

## 📞 Getting Help

- Check the generated `prompts_template.json` for examples
- Review the `outputs/` directory for sample scripts
- Modify prompts and test with `test_full_pipeline.py`
- Use the development setup guide in `DEVELOPMENT.md`

---

**Happy podcasting! 🎙️✨**
