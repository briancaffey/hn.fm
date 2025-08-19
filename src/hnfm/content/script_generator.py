"""Script generator for hn.fm that creates podcast scripts from processed content."""

import json
import os
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """Generates podcast scripts from processed content."""

    def __init__(self, prompts_file: Optional[str] = None, llm_provider: Optional[str] = None):
        """Initialize the script generator.

        Args:
            prompts_file: Path to custom prompts file (optional)
            llm_provider: LLM provider to use ("openai", "anthropic", or "local")
        """
        self.prompts = self._load_prompts(prompts_file)
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)

        # Determine LLM provider from environment or parameter
        if llm_provider is None:
            llm_provider = os.getenv("LLM_PROVIDER", "openai")

        # Initialize LLM service
        try:
            self.llm_service = LLMService(provider=llm_provider)
            logger.info(f"LLM service initialized with provider: {llm_provider}")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM service: {e}")
            self.llm_service = None

    def _load_prompts(self, prompts_file: Optional[str] = None) -> Dict[str, str]:
        """Load prompts from file or use defaults.

        Args:
            prompts_file: Path to custom prompts file

        Returns:
            Dictionary of prompts
        """
        if prompts_file and os.path.exists(prompts_file):
            try:
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load custom prompts: {e}")

        # Default prompts - easy to customize
        return {
            "system_prompt": """You are a professional podcast script writer for a tech news show called "hn.fm".
Your job is to convert technical articles into engaging, conversational podcast scripts.

IMPORTANT RULES:
1. ALWAYS prefix each line with speaker tags: [S1] for Host 1, [S2] for Host 2
2. Keep lines short and natural for speaking (max 2-3 sentences per line)
3. Make technical content accessible to a general tech audience
4. Include natural conversation flow between hosts
5. Add humor and personality where appropriate
6. Structure as a conversation, not a monologue
7. Include transitions and segues between topics
8. End with a call to action or thought-provoking question

Example format:
[S1] Welcome to hn.fm, where we turn the best of Hacker News into your daily tech podcast!
[S2] That's right! Today we're diving into something really interesting...
[S1] Absolutely! And here's what caught my attention...""",

            "content_prompt": """Convert the following technical article into a focused, conversational podcast discussion.

ARTICLE TITLE: {title}
ARTICLE CONTENT:
{meaningful_paragraphs}

REQUIREMENTS:
- Jump straight into discussing the article content - NO intro fluff
- Create natural conversation between two hosts about the actual article content
- Each host should discuss specific points from the article
- Include reactions, insights, and practical perspectives
- Make it sound like two developers discussing something they just read
- Keep it focused and meaningful - every line should add value
- NO wrap-up or conclusion - just end when the content is covered

Remember: Every line must start with [S1] or [S2] for the TTS system.""",

            "intro_prompt": """Create a compelling podcast intro for this episode.

TITLE: {title}
TOPIC: {topic}

Make it engaging, mention the source, and set up what listeners will learn.""",

            "outro_prompt": """Create a podcast outro that wraps up the episode.

TITLE: {title}
KEY TAKEAWAYS: {takeaways}

Include a call to action, mention the source, and encourage engagement."""
        }

    def generate_script(self, processed_content: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a podcast script from processed content.

        Args:
            processed_content: Processed content dictionary

        Returns:
            Generated script dictionary
        """
        try:
            # Generate only the main content - no intro/outro fluff
            main_content = self._generate_main_content(processed_content)

            # Create script object
            script = {
                'title': processed_content.get('title', 'Unknown'),
                'url': processed_content.get('url', ''),
                'main_content': main_content,
                'full_script': main_content,
                'speaker_lines': self._extract_speaker_lines(main_content),
                'total_lines': len(self._extract_speaker_lines(main_content))
            }

            # Save the script
            self._save_script(script, processed_content)

            logger.info(f"Generated script with {script['total_lines']} speaker lines")
            return script

        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return {}

    def _generate_intro(self, content: Dict[str, Any]) -> str:
        """Generate podcast intro using LLM.

        Args:
            content: Processed content

        Returns:
            Generated intro text
        """
        user_prompt = self.prompts["intro_prompt"].format(
            title=content.get('title', 'Unknown'),
            topic=self._extract_topic(content.get('cleaned_text', ''))
        )

        # Require LLM service for intro generation
        if not self.llm_service:
            raise RuntimeError("LLM service is required for intro generation")

        try:
            intro = self.llm_service.generate_script(
                system_prompt=self.prompts["system_prompt"],
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=500
            )
            return intro
        except Exception as e:
            logger.error(f"LLM intro generation failed: {e}")
            raise RuntimeError(f"Failed to generate intro: {e}")

    def _generate_main_content(self, content: Dict[str, Any]) -> str:
        """Generate main content script from meaningful paragraphs using LLM.

        Args:
            content: Processed content

        Returns:
            Generated main content script
        """
        meaningful_paragraphs = content.get('meaningful_paragraphs', [])

        if not meaningful_paragraphs:
            raise ValueError("No meaningful paragraphs found in content")

        # Format the prompt with article content
        user_prompt = self.prompts["content_prompt"].format(
            title=content.get('title', 'Unknown'),
            meaningful_paragraphs='\n\n'.join(meaningful_paragraphs)
        )

        # Require LLM service for script generation
        if not self.llm_service:
            raise RuntimeError("LLM service is required for script generation")

        try:
            logger.info("Generating script using LLM service...")
            script = self.llm_service.generate_script(
                system_prompt=self.prompts["system_prompt"],
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=2000
            )
            logger.info("Script generated successfully using LLM")
            return script
        except Exception as e:
            logger.error(f"LLM script generation failed: {e}")
            raise RuntimeError(f"Failed to generate script: {e}")

    def _generate_outro(self, content: Dict[str, Any]) -> str:
        """Generate podcast outro using LLM.

        Args:
            content: Processed content

        Returns:
            Generated outro text
        """
        user_prompt = self.prompts["outro_prompt"].format(
            title=content.get('title', 'Unknown'),
            takeaways="the practical insights from this article"
        )

        # Require LLM service for outro generation
        if not self.llm_service:
            raise RuntimeError("LLM service is required for outro generation")

        try:
            outro = self.llm_service.generate_script(
                system_prompt=self.prompts["system_prompt"],
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=500
            )
            return outro
        except Exception as e:
            logger.error(f"LLM outro generation failed: {e}")
            raise RuntimeError(f"Failed to generate outro: {e}")

    def _combine_script_parts(self, intro: str, main: str, outro: str) -> str:
        """Combine script parts into full script.

        Args:
            intro: Intro text
            main: Main content text
            outro: Outro text

        Returns:
            Combined full script
        """
        return f"{intro}\n\n{main}\n\n{outro}"

    def _extract_speaker_lines(self, script: str) -> List[str]:
        """Extract individual speaker lines from script.

        Args:
            script: Full script text

        Returns:
            List of speaker lines
        """
        lines = [line.strip() for line in script.split('\n') if line.strip()]
        speaker_lines = [line for line in lines if line.startswith('[S1]') or line.startswith('[S2]')]
        return speaker_lines

    def _extract_topic(self, text: str) -> str:
        """Extract main topic from text.

        Args:
            text: Cleaned text content

        Returns:
            Extracted topic
        """
        # Simple topic extraction - first few words
        words = text.split()[:10]
        return ' '.join(words) + '...'

    def _save_script(self, script: Dict[str, Any], content: Dict[str, Any]) -> None:
        """Save generated script to files.

        Args:
            script: Generated script dictionary
            content: Original processed content
        """
        # Save full script
        script_file = self.output_dir / f"script_{content.get('title', 'unknown').replace(' ', '_')[:30]}.txt"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(f"# Podcast Script: {script['title']}\n")
            f.write(f"Source: {script['url']}\n")
            f.write(f"Generated: {len(script['speaker_lines'])} speaker lines\n\n")
            f.write(script['full_script'])

        # Save speaker lines for TTS
        tts_file = self.output_dir / f"tts_lines_{content.get('title', 'unknown').replace(' ', '_')[:30]}.txt"
        with open(tts_file, 'w', encoding='utf-8') as f:
            for line in script['speaker_lines']:
                f.write(f"{line}\n")

        # Save metadata
        meta_file = self.output_dir / f"script_meta_{content.get('title', 'unknown').replace(' ', '_')[:30]}.json"
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(script, f, indent=2, ensure_ascii=False)

        logger.info(f"Script saved to: {script_file}")
        logger.info(f"TTS lines saved to: {tts_file}")
        logger.info(f"Metadata saved to: {meta_file}")

    def save_prompts_template(self, filename: str = "prompts_template.json") -> bool:
        """Save prompts template for customization.

        Args:
            filename: Output filename

        Returns:
            True if successful
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, indent=2, ensure_ascii=False)

            logger.info(f"Prompts template saved to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving prompts template: {e}")
            return False
