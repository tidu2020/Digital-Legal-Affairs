import os
from openai import OpenAI
from typing import Optional, Iterator

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.base_url = os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://chatai.bii.com.cn/open-api/llm/k8s/qwen/v1"))
        # Remove trailing /chat/completions if present
        if self.base_url.endswith("/chat/completions"):
            self.base_url = self.base_url[:-len("/chat/completions")]
        self.model = os.getenv("LLM_MODEL", "qwen")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120.0)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=8192
        )
        return response.choices[0].message.content or ""

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
        import json
        json_system = system_prompt + "\n\n【必须严格遵守】只输出纯 JSON 对象，以 { 开头、} 结尾。不要用 ```json 包裹，不要加任何解释文字。"
        raw = self.chat(json_system, user_prompt, temperature)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end+1])
                except json.JSONDecodeError:
                    pass
            return {"error": "JSON解析失败", "raw": raw[:500]}

    def chat_stream(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> Iterator[str]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=8192,
            stream=True
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def chat_messages(self, messages: list, temperature: float = 0.3) -> str:
        """使用messages数组格式调用LLM，支持真正的多轮对话"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=8192
        )
        return response.choices[0].message.content or ""

    def chat_messages_stream(self, messages: list, temperature: float = 0.3) -> Iterator[str]:
        """使用messages数组格式流式调用LLM"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=8192,
            stream=True
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
