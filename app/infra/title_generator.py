from openai import OpenAI

from app.config import config
from app.db.models import Video
from app.google_export.export import PromptService


class TitleGenerator:
    def __init__(self):
        self._client = OpenAI(
            base_url="https://api.x.ai/v1",
            api_key=config.GROK_API_KEY,
        )
        self._prompt = PromptService().get_prompt()

    async def generate(self, video: Video) -> str | None:
        await video.fetch_link(Video.actresses)
        await video.fetch_link(Video.tags)

        actresses = [m.name for m in video.actresses][:2] if video.actresses else []
        tags = [t.name for t in video.tags][:2] if video.tags else []

        content = f"""Video code: {video.jav_code}
Original title: {video.title}
Actresses: {', '.join(actresses) if actresses else 'N/A'}
Tags: {', '.join(tags) if tags else 'N/A'}
"""

        messages = [
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": content},
        ]

        completion = self._client.chat.completions.create(
            model="grok-3-mini-beta",
            messages=messages,
            temperature=0.7,
        )
        return completion.choices[0].message.content.strip()
