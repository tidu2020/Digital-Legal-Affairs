from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.llm_client import LLMClient
from shared.file_processor import extract_text_from_file, extract_info_with_llm

router = APIRouter()
llm = LLMClient()

uploaded_files_store = {}

GLOSSARY = """
【术语表】
- "四位一体"：法务、合规、内控、风控融合管理
- "三个100%"：重大经营决策、规章制度、合同协议法律审核率均达100%
- "三道防线"：业务部门（第一道）→法律合规部门（第二道）→审计监督部门（第三道）
- "二审制"：案件管理二审把关机制
- "三张清单"：合规义务清单、合规风险清单、岗位合规职责清单
- "减存控增"：减少存量案件、控制新增案件
- "以案促管/以案促改/以案促鉴"：通过案件复盘推动管理改进
- "四个亲自"：重要工作亲自部署、重大问题亲自过问、重点环节亲自协调、重要案件亲自督办
"""

REPORT_TEMPLATES = {
    "法治建设总结": {
        "name": "法治建设（法务管理）工作总结报告",
        "default_sections": "一、法治建设责任落实情况\n二、法治工作组织体系建设情况\n三、法治建设工作开展情况\n四、合规、内控及风控工作开展情况\n五、法治建设工作年度亮点\n六、下一年度法治工作计划",
        "prompt": """撰写一份年度法治工作总结报告。

【框架要求】
一、法治建设责任落实情况
- 顶层设计与战略引领：公司主要负责人如何履行第一责任人职责，体现"四个亲自"
- 机构设置与资源保障：法治建设领导小组运行情况，总法律顾问/首席合规官履职情况
- 法治引领与文化建设：领导干部学法清单制度执行情况，"会前学法"机制落实

二、法治工作组织体系建设情况
- 领导决策机构运行有效（党委会/董事会/总办会法治议题审议次数）
- 法治工作机构设置健全
- "三道防线"责任体系清晰
- 法治工作队伍稳步加强

三、法治建设工作开展情况
- "三个100%"执行情况：重大经营决策法律审核率、规章制度法律审核率、合同协议法律审核率
- 案件管理情况：案件数量/类型/阶段/涉案金额 + "以案促改"措施，落实"二审制"
- 法治培训与宣传教育：培训次数、参训人次、形式
- 制度建设与合同管理

四、合规、内控及风控工作开展情况
- 合规体系建设（"三张清单"、专项指引、有效性评估）
- 内控管理工作（内控手册更新、自评价、缺陷整改）
- 风险管理工作（风险排查、重大风险识别）

五、法治建设工作年度亮点
采用"一是……二是……三是……"分点列举

六、下一年度法治工作计划"""
    },
    "合规管理报告": {
        "name": "合规管理工作报告",
        "default_sections": "一、企业合规管理总体情况\n二、合规组织架构建设情况\n三、合规制度体系建设情况\n四、重点领域合规管理工作\n五、合规管理机制运行情况\n六、合规管理保障情况\n七、合规培训与合规文化建设情况\n八、合规管理亮点及典型案例\n九、存在的不足和下一步措施",
        "prompt": """撰写一份合规管理工作报告。

【框架要求】
一、企业合规管理总体情况
- 合规管理工作整体开展情况及成效

二、合规组织架构建设情况
- 合规治理结构职责、合规管理机构设置及职责
- 合规管理联席会议、合规管理人员配备

三、合规制度体系建设情况
- 合规行为准则、合规基本管理制度、合规专项管理制度
- 合规指引、流程或表单

四、重点领域合规管理工作
- 采购领域、反垄断领域、境外投融资经营领域等
- 以案促管工作

五、合规管理机制运行情况
- 合规风险识别评估、合规管控措施嵌入制度与流程
- 合规审查咨询、合规风险应对及报告

六、合规管理保障情况
- 第一责任人职责履行、合规考核评价
- 合规人才队伍建设、合规信息化建设

七、合规培训与合规文化建设情况

八、合规管理亮点及典型案例

九、存在的不足和下一步措施"""
    },
    "内控管理报告": {
        "name": "内控体系工作报告",
        "default_sections": "一、汇报背景说明\n二、内控体系建设情况\n三、内控体系监督评价工作情况\n四、内控缺陷整改落实情况\n五、内控工作取得的成效和亮点\n六、下一步工作安排\n七、附件",
        "prompt": """撰写一份内控体系工作报告（向董事会提交）。

【框架要求】
一、汇报背景说明
- 编制依据（市国资委文件号）、审批流程、提请对象

二、内控体系建设情况
1. 内控工作领导体制建设
2. 内控工作组织架构及履职情况
3. 内控体系建设与执行（制度流程更新、子企业制度对标、专项治理）
4. 信息化管控情况

三、内控体系监督评价工作情况
- 评价机制、自评价情况、发现问题、结果运用

四、内控缺陷整改落实情况
- 缺陷总数及分类（重大/重要/一般、设计缺陷/执行缺陷）
- 整改措施及完成情况

五、内控工作取得的成效和亮点

六、下一步工作安排

七、附件"""
    },
    "风险报告": {
        "name": "风险管理工作年度报告",
        "default_sections": "一、风险管理整体情况\n二、统筹推进'四位一体'综合风险防控体系建设情况\n三、上一年度重大风险化解情况\n四、全面风险管理评估工作情况\n五、本年度重大风险解决方案\n六、下一年度风险管理工作计划",
        "prompt": """撰写一份风险管理工作年度报告（向董事会提交）。

【框架要求】
一、风险管理整体情况
- 总体风险战略与偏好、风险管理治理机制运行情况

二、统筹推进"四位一体"综合风险防控体系建设情况
1. 法律审核关口前移
2. 推动风险内控协同
3. 案件管理减存控增
4. 铺开合规体系建设

三、上一年度重大风险化解情况

四、全面风险管理评估工作情况

五、本年度重大风险解决方案
每项重大风险按"风险名称+风险现状+化解措施（明确主责单位）"格式

六、下一年度风险管理工作计划"""
    },
    "律师管理报告": {
        "name": "律师（外聘法律顾问）管理报告",
        "default_sections": "一、律师选聘与合同情况\n二、律师日常管理与服务情况\n三、律师服务考核评价\n四、存在的问题与不足\n五、下一步管理计划",
        "prompt": """撰写一份律师（外聘法律顾问）管理情况报告。

【框架要求】
一、律师选聘与合同情况（律所名称、服务期限、选聘方式、服务范围）

二、律师日常管理与服务情况
- 服务工作量统计（咨询次数、审核份数、意见书份数、谈判次数、培训次数）
- 响应时效、紧急事项保障、过程监督

三、律师服务考核评价（考核维度、评分结果、结果运用）

四、存在的问题与不足

五、下一步管理计划"""
    }
}


class ReportRequest(BaseModel):
    report_type: str
    period: str = ""
    content: str = ""
    custom_sections: str = ""
    requirements: str = ""
    attachments: Optional[List[str]] = None
    stream: bool = True

@router.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    try:
        results = []
        for file in files:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            info = extract_info_with_llm(llm, text, "报告资料")
            file_id = f"report_{hash(file.filename)}_{len(uploaded_files_store)}"
            uploaded_files_store[file_id] = {
                "filename": file.filename, "text": text, "info": info, "size": len(content)
            }
            results.append({
                "success": True, "file_id": file_id, "filename": file.filename,
                "text_preview": text[:300] + "..." if len(text) > 300 else text, "info": info
            })
        return {"success": True, "files": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/templates")
async def get_templates():
    templates = []
    for key, tmpl in REPORT_TEMPLATES.items():
        templates.append({
            "key": key,
            "name": tmpl["name"],
            "default_sections": tmpl["default_sections"]
        })
    return {"templates": templates}


def _build_report_prompt(request: ReportRequest) -> tuple:
    template = REPORT_TEMPLATES.get(request.report_type)
    
    # 用户自定义结构或使用默认结构
    sections = request.custom_sections.strip() if request.custom_sections.strip() else (template["default_sections"] if template else "")
    
    # 收集所有上传材料的完整内容
    material_texts = []
    if request.attachments:
        for file_id in request.attachments:
            if file_id in uploaded_files_store:
                fd = uploaded_files_store[file_id]
                material_texts.append(f"【文件：{fd['filename']}】\n{fd['text'][:8000]}")
    
    material_content = "\n\n".join(material_texts) if material_texts else ""
    
    system_prompt = f"""你是一位拥有10年经验的央企/国企法务合规部门资深专家，熟悉"四位一体"（法务、合规、内控、风控）融合管理体系。

你的任务是撰写一份{template['name'] if template else request.report_type}。

{template['prompt'] if template else ''}

{GLOSSARY}

【核心要求 - 极其重要】
1. 必须从用户上传的材料中提取真实数据（具体数字、日期、名称、金额等），填充到报告的各个章节中
2. 不要编造数据，如果材料中没有某个数据，用"[待补充：xxx]"标注
3. 报告中的每个结论都必须有数据支撑，不能空泛描述
4. 案件、合同、培训等具体事项要引用材料中的真实案例

【报告结构】
{sections}

【写作规范】
- 正式公文风格，数据说话
- 使用国企标准术语
- 每个章节下提供2-4个二级要点，包含具体数据和案例

【重要】输出要求：不要使用markdown格式符号，直接输出纯文本格式的报告。"""
    
    context_parts = []
    if request.period:
        context_parts.append(f"报告期间：{request.period}")
    
    if material_content:
        context_parts.append(f"【以下是从上传材料中提取的内容，请务必从中提取真实数据填充报告】\n\n{material_content}")
    
    if request.content:
        context_parts.append(f"用户补充的报告内容要点：\n{request.content}")
    
    if request.requirements:
        context_parts.append(f"特殊要求：{request.requirements}")
    
    user_prompt = "\n\n".join(context_parts) if context_parts else "请根据上传材料生成报告"
    
    return system_prompt, user_prompt


@router.post("/api/generate")
async def generate_report(request: ReportRequest):
    try:
        system_prompt, user_prompt = _build_report_prompt(request)
        response = llm.chat(system_prompt, user_prompt)
        return {"response": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/generate/stream")
async def generate_report_stream(request: ReportRequest):
    try:
        system_prompt, user_prompt = _build_report_prompt(request)
        
        def generate():
            for chunk in llm.chat_stream(system_prompt, user_prompt):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
