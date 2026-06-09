# Tasks: 借鉴 Legal-Skills-Chinese 完善国企法务系统

- [x] Task 1: 创建技能模块目录和基础框架
  - [x] 在 `backend/` 下创建 `skills/` 目录
  - [x] 创建 `backend/skills/__init__.py`，定义技能基类和调度器接口
  - [x] 创建 `backend/skills/skill_loader.py`，实现技能加载与意图匹配

- [x] Task 2: 实现技能化 System Prompt 体系
  - [x] 创建 `backend/skills/contract_review.py`（合同审核技能模块），包含争议与履约风险识别框架、条款审查清单、风险评级矩阵
  - [x] 创建 `backend/skills/compliance_review.py`（合规审查技能模块），包含内部合规风险识别框架、制度完整性审查维度
  - [x] 创建 `backend/skills/regulation_review.py`（制度法律审核技能模块），包含合法性、合规性、风险可控性、体系兼容性审查维度
  - [x] 创建 `backend/skills/litigation_management.py`（诉讼案件管理技能模块），包含案件分类、时限管理、重大案件标准
  - [x] 创建 `backend/skills/document_writing.py`（公文写作技能模块），包含7类国企法务公文模板
  - [x] 修改 `backend/llm_client.py` 中的 `build_legal_system_prompt`，支持根据用户意图动态组合技能模块

- [x] Task 3: 实现结构化风险评级体系
  - [x] 在 `backend/` 中实现统一的风险评级矩阵（发生概率 × 影响程度 → 高/中/低）
  - [x] 实现风险输出统一格式：风险等级（🔴/🟡/🟢）、风险类型、关联条款、风险描述、法律依据、应对建议
  - [x] 在合同审核技能中嵌入风险评级逻辑
  - [x] 在合规审查技能中嵌入风险评级逻辑（含 G/P/D 问题编号前缀）

- [x] Task 4: 实现置信度标注体系
  - [x] 定义三级置信度标准：高（权威数据源核验通过）、中（合理推理）、低（信息不足）
  - [x] 修改 `backend/app.py` 的对话接口，在响应中附加置信度信息
  - [x] 修改 `frontend/index.html`，在消息展示中渲染置信度标注

- [x] Task 5: 增强法条校验能力（三维度）
  - [x] 修改 `backend/law_validator.py`，在现有时效性校验基础上增加层级效力检查维度
  - [x] 在法条校验报告中增加冲突检查提示（纵向冲突/横向冲突）
  - [x] 在校验报告中增加优先适用规则建议（上位法优先/特别法优先/新法优先）

- [x] Task 6: 实现争议焦点识别
  - [x] 在合同审核技能中实现争议焦点自动提取（将争议表述为法律问题）
  - [x] 实现争议焦点影响权重标注（高/中/低）
  - [x] 在案件分析场景中集成争议焦点识别

- [x] Task 7: 实现结构化输出模板
  - [x] 创建制度审核报告模板（基本信息、四维审查、总体结论、整改建议）
  - [x] 创建合同风险报告模板（风险总览、风险清单、关键建议摘要、分析局限性）
  - [x] 创建合规审查报告模板（审查结论摘要、重大/重要/一般风险清单、整改建议汇总）
  - [x] 在系统提示词中嵌入模板格式要求

- [x] Task 8: 前端展示优化
  - [x] 在 `frontend/index.html` 中增加风险等级视觉样式（🔴红色边框/🟡黄色边框/🟢绿色边框）
  - [x] 增加置信度标注的视觉展示
  - [x] 增加结构化报告面板的折叠/展开交互

# Task Dependencies
- Task 2 依赖 Task 1
- Task 3 依赖 Task 1、Task 2
- Task 4 依赖 Task 1
- Task 5 可独立进行（与 Task 1-4 并行）
- Task 6 依赖 Task 2
- Task 7 依赖 Task 1、Task 2
- Task 8 依赖 Task 3、Task 4、Task 7