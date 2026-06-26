# 国企数字法务平台

国企法务合规智能助手，集成六大核心功能模块 + 实用小工具。

## 功能模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 法律合规咨询 | `/modules/consulting` | 多轮对话、文件上传、法条自动检索 |
| 合同审核 | `/modules/contract_review` | 合同文本审核、风险分析、报告生成 |
| 案件应对 | `/modules/case_management` | 案情梳理、法律文书撰写（起诉状/答辩状等） |
| 报告撰写 | `/modules/report_writing` | 法治建设总结、合规报告、风险报告等 |
| 经营决策审核 | `/modules/decision_review` | 上会议题、请示签报审核 |
| 制度审核 | `/modules/regulation_review` | 制度与法律/政策/公司制度冲突检查 |

## 小工具

| 工具 | 路径 | 说明 |
|------|------|------|
| 文件脱敏 | `/tools/desensitization` | AI识别并替换文档敏感信息 |
| 法条检索 | `/tools/law_search` | 跳转国家法律法规数据库 |

## 项目结构

```
Digital-Legal-Affairs/
├── main.py                    # 综合入口（FastAPI）
├── frontend/
│   └── index.html             # 首页（智能助手+模块导航+小工具）
├── shared/                    # 共享组件
│   ├── llm_client.py          # LLM客户端
│   ├── law_search.py          # 法条检索（flk.npc.gov.cn）
│   ├── law_validator.py       # 法条校验
│   └── file_processor.py      # 文件解析
├── modules/                   # 六大功能模块
│   ├── consulting/            # 法律合规咨询
│   ├── contract_review/       # 合同审核
│   ├── case_management/       # 案件应对
│   ├── report_writing/        # 报告撰写
│   ├── decision_review/       # 经营决策审核
│   └── regulation_review/     # 制度审核
└── tools/                     # 小工具
    ├── desensitization/       # 文件脱敏
    └── law_search/            # 法条检索
```

## 快速启动

```bash
# 安装依赖
pip install fastapi uvicorn openai python-dotenv python-docx PyPDF2 requests pycryptodome

# 启动服务
python main.py
```

访问 http://localhost:1824

## 技术栈

- **后端**：FastAPI + Python
- **LLM**：Qwen（私有化部署）
- **法条数据库**：国家法律法规数据库（flk.npc.gov.cn）
- **前端**：原生 HTML/CSS/JavaScript

## 配置

编辑 `.env` 文件：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-llm-endpoint/v1
LLM_MODEL=qwen
```
