"""
国企法务助手 - 技能模块基础框架
"""
from typing import List


class BaseSkill:
    """技能基类，所有法律咨询技能均继承此类"""

    def __init__(self):
        self.name: str = ""
        self.description: str = ""
        self.keywords: List[str] = []

    def get_system_prompt(self) -> str:
        """返回该技能的 system prompt 片段"""
        return ""


class SkillScheduler:
    """技能调度器，负责技能的注册、匹配与 prompt 组装"""

    def __init__(self):
        self._registry: List[BaseSkill] = []

    def register(self, skill: BaseSkill) -> None:
        """注册一个技能实例"""
        self._registry.append(skill)

    def match(self, user_message: str) -> List[BaseSkill]:
        """根据用户消息匹配技能（关键词大小写不敏感）"""
        if not user_message:
            return []
        message_lower = user_message.lower()
        matched = []
        for skill in self._registry:
            for kw in skill.keywords:
                if kw.lower() in message_lower:
                    matched.append(skill)
                    break
        return matched

    def build_system_prompt(self, user_message: str, base_prompt: str = "") -> str:
        """组合基础 prompt 与匹配到的技能 prompt"""
        parts = []
        if base_prompt:
            parts.append(base_prompt)

        matched_skills = self.match(user_message)
        if matched_skills:
            skill_prompts = []
            for skill in matched_skills:
                sp = skill.get_system_prompt()
                if sp:
                    skill_prompts.append(sp)
            if skill_prompts:
                parts.append(
                    "══════════ 专项技能指引 ══════════\n"
                    + "\n---\n".join(skill_prompts)
                    + "\n══════════════════════════════════"
                )

        return "\n\n".join(parts)