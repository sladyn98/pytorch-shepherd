"""Claude API client for the PyTorch Issue Fixing Agent."""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional

import anthropic
from anthropic import AsyncAnthropic

from utils.config import ClaudeConfig
from .prompts import format_issue_analysis_prompt, format_pr_description_prompt


class ClaudeClient:
    """Minimal Claude API client for essential tasks only."""
    
    def __init__(self, config: ClaudeConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client = AsyncAnthropic(api_key=config.api_key)
        
    async def analyze_issue(self, issue_data: Dict[str, Any], comments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze a GitHub issue and extract key information."""
        try:
            prompt = format_issue_analysis_prompt(issue_data, comments)
            response = await self._make_request(
                prompt=prompt,
                system="You are an expert PyTorch contributor. Analyze GitHub issues and provide structured insights in JSON format."
            )
            
            analysis = self._parse_json_response(response)
            if not analysis:
                analysis = {
                    "category": "unknown",
                    "complexity": "medium",
                    "search_terms": []
                }
            
            self.logger.info(f"Issue analysis completed: {analysis.get('category', 'unknown')}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze issue: {e}")
            return {"category": "unknown", "complexity": "medium", "search_terms": []}
    
    
    async def generate_pr_description(
        self,
        issue_data: Dict[str, Any],
        fix_summary: Dict[str, Any],
        files_changed: List[str]
    ) -> Dict[str, str]:
        """Generate pull request title and description."""
        try:
            prompt = format_pr_description_prompt(issue_data, fix_summary, files_changed)
            response = await self._make_request(
                prompt=prompt,
                system="You are an expert at writing clear, comprehensive pull request descriptions for PyTorch contributions."
            )
            
            pr_data = self._parse_json_response(response)
            if not pr_data:
                pr_data = {
                    "title": f"Fix issue #{issue_data.get('number', 'unknown')}",
                    "body": "Automated fix for PyTorch issue."
                }
            
            return pr_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate PR description: {e}")
            return {
                "title": f"Fix issue #{issue_data.get('number', 'unknown')}",
                "body": "Automated fix for PyTorch issue."
            }
    
    
    
    async def _make_request(
        self,
        prompt: str,
        system: str = None,
        max_tokens: int = None,
        temperature: float = None
    ) -> str:
        """Make a request to Claude API with retry logic."""
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature or self.config.temperature
        
        for attempt in range(self.config.max_retries):
            try:
                messages = [{"role": "user", "content": prompt}]
                
                kwargs = {
                    "model": self.config.model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages
                }
                
                if system:
                    kwargs["system"] = system
                
                response = await self.client.messages.create(**kwargs)
                
                # Extract text content from response
                if response.content and len(response.content) > 0:
                    return response.content[0].text
                else:
                    raise ValueError("Empty response from Claude API")
                
            except anthropic.RateLimitError as e:
                self.logger.warning(f"Rate limit hit, attempt {attempt + 1}/{self.config.max_retries}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    raise
            except anthropic.APIError as e:
                self.logger.error(f"Claude API error: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise
            except anthropic.APIConnectionError as e:
                self.logger.error(f"Claude API connection error: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * 2)  # Longer wait for connection issues
                else:
                    raise
            except Exception as e:
                self.logger.error(f"Unexpected error in Claude request: {e}")
                self.logger.error(f"Error type: {type(e)}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise
        
        raise RuntimeError("Max retries exceeded for Claude API request")
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from Claude."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON-like content
            json_match = re.search(r'(\{.*\})', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            self.logger.warning("Failed to parse JSON response")
            return None
    
    async def health_check(self) -> bool:
        """Check if Claude API is accessible."""
        try:
            response = await self._make_request(
                prompt="Respond with 'OK' if you can read this message.",
                max_tokens=10
            )
            return "OK" in response.upper()
        except Exception as e:
            self.logger.error(f"Claude health check failed: {e}")
            return False