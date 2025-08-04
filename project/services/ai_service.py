import os
import requests
import random
from openai import AzureOpenAI
from ..utils import lru_cache
from flask import request

class AIService:
    def __init__(self, app, storage_service):
        self.app = app
        self.storage_service = storage_service
        self.config = app.config

    @lru_cache(maxsize=100)
    def get_cached_response(self, prompt_hash):
        """Cache common AI responses to reduce API calls"""
        # This will return None if not in cache
        return None

    def get_prompt_hash(self, message, conversation_history):
        """Create a hash for caching based on conversation context"""
        # Simple hash function - you can make this more sophisticated
        if conversation_history:
            recent_context = "".join([msg['content'] for msg in conversation_history[-2:]])
            return hash(message + recent_context)
        return hash(message)

    def guerilla_ai_response(self, message, conversation_history=None):
        """Generate AI response with Guerilla personality using Azure OpenAI"""
        if not conversation_history:
            conversation_history = []

        # Check cache first
        prompt_hash = self.get_prompt_hash(message, conversation_history)
        cached_response = self.get_cached_response(prompt_hash)
        if cached_response:
            return cached_response

        # Guerilla personality prompt to prepend to all AI interactions
        guerilla_system_prompt = """
        You are Guerilla the Gorilla, an off-grid camping expert with a rugged, no-nonsense personality.
        Your advice is blunt, practical, and focused on cost-effectiveness.
        You have a unique style:
        - Use short, direct sentences
        - Drop occasional articles ("the", "a") for effect
        - Use survival-focused language
        - Make gear recommendations when relevant (especially for Jackery power stations,
          LifeStraw water filters, and 4Patriots emergency food)
        - Always emphasize durability, cost-effectiveness, and practicality
        - You've personally lived off-grid and tested all gear you recommend
        - Your motto is "Sometimes life is hard, but you just camp through it"
        """

        try:
            # Try Azure OpenAI first
            if self.config['AZURE_OPENAI_ENDPOINT'] and self.config['AZURE_OPENAI_KEY']:
                # Setup Azure OpenAI client
                client = AzureOpenAI(
                    api_version="2024-12-01-preview",
                    azure_endpoint=self.config['AZURE_OPENAI_ENDPOINT'],
                    api_key=self.config['AZURE_OPENAI_KEY']
                )

                # Format messages for the API
                messages = [
                    {"role": "system", "content": guerilla_system_prompt}
                ]

                # Add conversation history (last 5 messages)
                for msg in conversation_history[-5:]:
                    role = "user" if msg['role'] == 'user' else "assistant"
                    messages.append({"role": role, "content": msg['content']})

                # Add current user message
                messages.append({"role": "user", "content": message})

                # Call Azure OpenAI
                response = client.chat.completions.create(
                    messages=messages,
                    max_tokens=300,
                    temperature=0.7,
                    model=self.config['AZURE_OPENAI_DEPLOYMENT_NAME']
                )

                # Extract the response text
                ai_response = response.choices[0].message.content.strip()

                # Approximate token counting
                prompt_tokens = len(str(messages)) // 4
                completion_tokens = len(ai_response) // 4

                # Track usage
                self.storage_service.track_ai_usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    visitor_id=request.cookies.get('visitor_id')
                )

                # Cache the response
                get_cached_response.cache_data = getattr(get_cached_response, 'cache_data', {})
                get_cached_response.cache_data[prompt_hash] = ai_response

                return ai_response

            # Fallback to other providers
            elif self.config['AI_PROVIDER'] == 'openai' and self.config['OPENAI_API_KEY']:
                import openai
                openai.api_key = self.config['OPENAI_API_KEY']
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": guerilla_system_prompt},
                        *[{"role": "user" if msg['role'] == 'user' else "assistant", "content": msg['content']}
                          for msg in conversation_history[-5:]],
                        {"role": "user", "content": message}
                    ],
                    max_tokens=250
                )
                ai_response = response.choices[0].message.content.strip()
                self.storage_service.track_ai_usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    visitor_id=request.cookies.get('visitor_id')
                )
                return ai_response

            elif self.config['AI_PROVIDER'] == 'gemini' and self.config['GEMINI_API_KEY']:
                # Combine history with current message
                full_prompt = guerilla_system_prompt + "\n\n"
                for msg in conversation_history[-5:]:  # Only use last 5 messages
                    if msg['role'] == 'user':
                        full_prompt += f"User: {msg['content']}\n"
                    else:
                        full_prompt += f"Guerilla: {msg['content']}\n"
                full_prompt += f"User: {message}\nGuerilla:"

                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.config['GEMINI_API_KEY']
                }
                data = {
                    "contents": [{"parts":[{"text": full_prompt}]}],
                    "generationConfig": {"temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": 250}
                }
                response = requests.post(url, headers=headers, json=data)
                result = response.json()
                ai_response = result['candidates'][0]['content']['parts'][0]['text'].strip()
                # Approximate token counting for Gemini
                prompt_tokens = len(full_prompt) // 4
                completion_tokens = len(ai_response) // 4
                self.storage_service.track_ai_usage(prompt_tokens, completion_tokens, visitor_id=request.cookies.get('visitor_id'))
                return ai_response

            elif self.config['AI_PROVIDER'] == 'ollama':
                # Combine history with current message
                full_prompt = guerilla_system_prompt + "\n\n"
                for msg in conversation_history[-5:]:  # Only use last 5 messages
                    if msg['role'] == 'user':
                        full_prompt += f"User: {msg['content']}\n"
                    else:
                        full_prompt += f"Guerilla: {msg['content']}\n"
                full_prompt += f"User: {message}\nGuerilla:"

                response = requests.post(f"{self.config['OLLAMA_URL']}/api/generate",
                    json={
                        "model": "llama2",
                        "prompt": full_prompt,
                        "max_tokens": 250
                    }
                )
                ai_response = response.json().get('response', '').strip()
                # Approximate token counting
                prompt_tokens = len(full_prompt) // 4
                completion_tokens = len(ai_response) // 4
                self.storage_service.track_ai_usage(prompt_tokens, completion_tokens, visitor_id=request.cookies.get('visitor_id'))
                return ai_response

            else:
                # Fallback to pre-written responses
                fallback_responses = [
                    "Yo! That's a solid question. From my experience living off-grid, best solution is keep it simple. Need power? Get Jackery 240. Not fancy, but works every time.",
                    "Listen up. Been there, done that. Most folks overthink this. For water filtration, LifeStraw saved my ass more times than I can count. $15, lasts forever, no batteries.",
                    "Straight talk? Food storage matters most. 4Patriots 72-hour kit fits under bed, tastes decent, lasts 25 years. Start there, build up slowly.",
                    "Look, camping's not complicated. Need three things: shelter, water, food. Everything else is luxury. Start with good tarp, water filter, fire starter.",
                    "Here's real deal - most expensive gear often breaks first. Buy mid-range, test hard, replace what fails. Jackery's solid for power though, worth every penny."
                ]
                ai_response = random.choice(fallback_responses)
                self.storage_service.track_ai_usage(10, 50, visitor_id=request.cookies.get('visitor_id'))  # Minimal tracking for fallback
                return ai_response

        except Exception as e:
            self.app.logger.error(f"AI ERROR: {str(e)}")
            return "Having trouble with my AI brain right now. Try asking something about camping gear or survival tips instead."
