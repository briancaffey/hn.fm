"""LLM-powered image prompt generator for hn.fm."""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from .llm_service import LLMService
from ..utils.config import config_manager

logger = logging.getLogger(__name__)


class ImagePromptGenerator:
    """Generates image prompts using LLM service."""

    def __init__(self):
        """Initialize the image prompt generator."""
        self.llm_service = LLMService()
        self.default_style = config_manager.get("image_generation.default_style", "detailed cartoon style")

    def generate_image_prompts_for_narration(
        self,
        narration_groups: List[Dict[str, Any]],
        full_script: str,
        style: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate image prompts for narration groups using LLM.

        Args:
            narration_groups: List of narration groups with lines
            full_script: Full script text for context
            style: Image style override

        Returns:
            List of image prompts with group_id
        """
        try:
            style = style or self.default_style
            image_prompts = []
            total_groups = len(narration_groups)

            logger.info(f"🎨 Starting image prompt generation for {total_groups} narration groups")
            logger.debug(f"🎭 Style: {style}")

            for group in narration_groups:
                group_id = group["group_id"]
                group_lines = group["lines"]

                logger.debug(f"📝 Generating prompt for group {group_id} ({len(group_lines)} lines)")

                # Show preview of the lines being processed
                lines_preview = "; ".join([line[:40] + "..." if len(line) > 40 else line for line in group_lines[:2]])
                if len(group_lines) > 2:
                    lines_preview += f" (+{len(group_lines) - 2} more lines)"
                logger.debug(f"   📖 Content: {lines_preview}")

                # Generate prompt for this group
                prompt = self._generate_single_image_prompt(
                    group_lines, full_script, style, group_id
                )

                image_prompts.append({
                    "group_id": group_id,
                    "lines": group_lines,
                    "prompt": prompt,
                    "style": style
                })

                # Show the generated prompt
                prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
                logger.debug(f"✅ Generated prompt for group {group_id}: {prompt_preview}")

            logger.info(f"🎉 Image prompt generation complete! Generated {len(image_prompts)} prompts")
            return image_prompts

        except Exception as e:
            logger.error(f"❌ Failed to generate image prompts: {e}")
            raise RuntimeError(f"Image prompt generation failed: {e}")

    def _generate_single_image_prompt(
        self,
        group_lines: List[str],
        full_script: str,
        style: str,
        group_id: int
    ) -> str:
        """Generate a single image prompt for a narration group.

        Args:
            group_lines: Lines for this narration group
            full_script: Full script for context
            style: Image style
            group_id: Group identifier

        Returns:
            Generated image prompt
        """
        try:
            # Create the system prompt
            system_prompt = self._create_system_prompt(style)

            # Create the user prompt
            user_prompt = self._create_user_prompt(group_lines, full_script, group_id)

            # Generate the prompt using LLM
            # Combine system and user prompts
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.llm_service.generate_content(combined_prompt)

            if not response:
                logger.warning(f"LLM returned empty response for group {group_id}, using fallback")
                return self._create_fallback_prompt(group_lines, style)

            # Clean up the response
            prompt = response.strip()
            if prompt.startswith('"') and prompt.endswith('"'):
                prompt = prompt[1:-1]

            return prompt

        except Exception as e:
            logger.error(f"Failed to generate prompt for group {group_id}: {e}")
            return self._create_fallback_prompt(group_lines, style)

    def _create_system_prompt(self, style: str) -> str:
        """Create the system prompt for image prompt generation.

        Args:
            style: Image style specification

        Returns:
            System prompt string
        """
        return f"""You are an expert image prompt engineer specializing in creating detailed, vivid descriptions for AI image generation.

Your task is to analyze script text and create compelling image prompts that will generate high-quality, relevant images.

IMPORTANT INSTRUCTIONS:
- Reasoning: high
- Focus on creating visual, descriptive prompts that capture the essence of the text
- Ensure prompts are simple and specific enough for consistent image generation
- Maintain visual coherence and storytelling flow
- As much as possible, come up with an image description that would complement the spoken lines

OUTPUT FORMAT:
- Return ONLY the image prompt text
- Keep prompts concise but descriptive (1-2 sentences)
- Focus on visual elements, mood, and composition
- Do not include technical specifications or meta-commentary

STYLE GUIDELINES:
- Be simple and specific about visual elements (lighting, composition, colors, etc.)
- Include relevant objects, people, environments
- Consider the emotional tone and atmosphere"""

    def _create_user_prompt(
        self,
        group_lines: List[str],
        full_script: str,
        group_id: int
    ) -> str:
        """Create the user prompt for image prompt generation.

        Args:
            group_lines: Lines for this narration group
            full_script: Full script for context
            group_id: Group identifier

        Returns:
            User prompt string
        """
        # Format the group lines for clarity
        lines_text = "\n".join([f"[S{i+1}] {line}" for i, line in enumerate(group_lines)])

        return f"""CONTEXT - Full Script:
{full_script[:1000]}{"..." if len(full_script) > 1000 else ""}

NARRATION GROUP {group_id} - Generate image prompt appropriate for an image to be shown on screen for these lines:

{lines_text}

Create an image prompt that best captures the visual essence of these specific narration lines. The image should represent what a viewer would see when hearing these words.

Consider:
- What visual scene would best represent these lines?
- What objects, people, or environments are mentioned or implied?
- What mood or atmosphere should the image convey?
- How can this image contribute to the overall story flow?

Generate a compelling image prompt:"""

    def _create_fallback_prompt(self, group_lines: List[str], style: str) -> str:
        """Create a fallback prompt if LLM generation fails.

        Args:
            group_lines: Lines for this narration group
            style: Image style

        Returns:
            Fallback prompt string
        """
        # Simple fallback that combines the lines
        combined_text = " ".join(group_lines)

        # Clean up the text
        cleaned_text = combined_text.replace("\n", " ").strip()
        if len(cleaned_text) > 100:
            cleaned_text = cleaned_text[:100] + "..."

        return f"a {style} image representing: {cleaned_text}"

    def batch_generate_prompts(
        self,
        content_data: Dict[str, Any],
        style: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate image prompts for all pending images in content data.

        Args:
            content_data: Content data from main.yaml
            style: Image style override

        Returns:
            List of image prompts with group_id
        """
        try:
            narration_groups = content_data.get("narration", [])
            full_script = content_data.get("script", {}).get("full_text", "")

            if not narration_groups:
                logger.warning("No narration groups found in content data")
                return []

            if not full_script:
                logger.warning("No full script found in content data")
                return []

            logger.info(f"Batch generating prompts for {len(narration_groups)} narration groups")

            return self.generate_image_prompts_for_narration(
                narration_groups, full_script, style
            )

        except Exception as e:
            logger.error(f"Failed to batch generate prompts: {e}")
            raise RuntimeError(f"Batch prompt generation failed: {e}")
