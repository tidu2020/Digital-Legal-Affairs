"""
国企法务助手 - 技能加载器
"""
import importlib
import os
import sys
from typing import List

from . import BaseSkill, SkillScheduler


class SkillLoader:
    """技能加载器，负责发现并加载所有技能模块"""

    def __init__(self):
        self._skills_dir = os.path.dirname(os.path.abspath(__file__))

    def load_all_skills(self) -> SkillScheduler:
        """导入所有技能模块并注册到 SkillScheduler"""
        scheduler = SkillScheduler()
        skill_modules = self._discover_skill_modules()

        for module_name in skill_modules:
            try:
                mod = importlib.import_module(
                    f".{module_name}", package="skills"
                )
                # 查找模块中所有 BaseSkill 子类实例
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill
                    ):
                        try:
                            instance = attr()
                            scheduler.register(instance)
                            print(f"[SkillLoader] 已加载技能: {instance.name}")
                        except Exception as e:
                            print(f"[SkillLoader] 实例化技能 {attr_name} 失败: {e}")
            except Exception as e:
                print(f"[SkillLoader] 导入模块 {module_name} 失败: {e}")

        print(f"[SkillLoader] 共加载 {len(scheduler._registry)} 个技能")
        return scheduler

    def _discover_skill_modules(self) -> List[str]:
        """发现 skills 目录下所有技能模块（排除私有模块和 skill_loader 自身）"""
        modules = []
        for filename in os.listdir(self._skills_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                if module_name != "skill_loader":
                    modules.append(module_name)
        return modules


# 全局单例
skill_loader = SkillLoader()