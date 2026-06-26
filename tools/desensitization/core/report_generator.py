"""
脱敏报告生成器
为每批次任务生成一份详细的《脱敏操作报告》，包含：
- 批次概览（文件数、成功数、替换总数）
- 逐文件明细：原始内容、执行动作、替换值、实体类型、原因
- 全部替换对照表

输出为自包含的 HTML 报告（便于打印/归档）+ JSON（便于程序读取）。
"""
import json
import os
from datetime import datetime
from typing import List

from jinja2 import Template

from processors.base import ProcessResult


REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>脱敏操作报告 - {{ batch_id }}</title>
<style>
  body { font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
         margin: 40px; color: #222; line-height: 1.6; }
  h1 { color: #1a5276; border-bottom: 3px solid #1a5276; padding-bottom: 10px; }
  h2 { color: #2874a6; margin-top: 32px; border-left: 4px solid #2874a6; padding-left: 10px; }
  h3 { color: #2e86c1; }
  .meta { background: #f4f6f7; padding: 15px 20px; border-radius: 6px; margin-bottom: 20px; }
  .meta span { margin-right: 30px; }
  .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0; }
  .card { background: #eaf2f8; padding: 18px; border-radius: 8px; text-align: center; }
  .card .num { font-size: 28px; font-weight: bold; color: #1a5276; }
  .card .label { color: #566; font-size: 13px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }
  th, td { border: 1px solid #ccd; padding: 8px 10px; text-align: left; vertical-align: top; }
  th { background: #d6eaf8; color: #1a5276; }
  tr:nth-child(even) { background: #f8f9fa; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
  .tag-replace { background: #d5f5e3; color: #1e8449; }
  .tag-delete { background: #fadbd8; color: #c0392b; }
  .tag-fail { background: #fadbd8; color: #c0392b; }
  .tag-ok { background: #d5f5e3; color: #1e8449; }
  .tag-high { background: #fadbd8; color: #c0392b; font-weight: bold; }
  .tag-medium { background: #fef9e7; color: #b7950b; }
  .tag-low { background: #eaf2f8; color: #2874a6; }
  .file-block { background: #fdfefe; border: 1px solid #d5dbdb; border-radius: 8px;
                padding: 16px 20px; margin-bottom: 20px; }
  .empty { color: #999; font-style: italic; }
  .footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd;
            color: #888; font-size: 12px; text-align: center; }
  code { background: #f0f3f4; padding: 1px 4px; border-radius: 3px; }
</style>
</head>
<body>
<h1>脱敏操作报告</h1>
<div class="meta">
  <span><b>批次编号：</b>{{ batch_id }}</span>
  <span><b>生成时间：</b>{{ generated_at }}</span>
  <span><b>操作员：</b>LLM 智能脱敏系统</span>
</div>

<div class="summary-grid">
  <div class="card"><div class="num">{{ total_files }}</div><div class="label">处理文件总数</div></div>
  <div class="card"><div class="num">{{ success_files }}</div><div class="label">成功脱敏文件</div></div>
  <div class="card"><div class="num">{{ total_replacements }}</div><div class="label">脱敏替换总数</div></div>
</div>

<h2>一、文件处理概览</h2>
<table>
  <tr>
    <th>序号</th><th>源文件</th><th>输出文件</th><th>类型</th>
    <th>状态</th><th>替换数</th><th>错误信息</th>
  </tr>
  {% for r in results %}
  <tr>
    <td>{{ loop.index }}</td>
    <td>{{ r.source_filename }}</td>
    <td>{{ r.output_filename }}</td>
    <td>{{ r.file_type }}</td>
    <td>
      {% if r.success %}<span class="tag tag-ok">成功</span>
      {% else %}<span class="tag tag-fail">失败</span>{% endif %}
    </td>
    <td>{{ r.replacement_count }}</td>
    <td>{{ r.error or '-' }}</td>
  </tr>
  {% endfor %}
</table>

<h2>二、逐文件脱敏明细</h2>
{% for r in results %}
<div class="file-block">
  <h3>{{ loop.index }}. {{ r.source_filename }}
      {% if r.success %}<span class="tag tag-ok">成功</span>
      {% else %}<span class="tag tag-fail">失败</span>{% endif %}
  </h3>
  <p><b>输出文件：</b>{{ r.output_filename }}<br>
     <b>文件类型：</b>{{ r.file_type }}<br>
     <b>替换数量：</b>{{ r.replacement_count }} 处</p>

  {% if r.replacements %}
  <table>
    <tr>
      <th style="width:4%">#</th>
      <th style="width:20%">原始内容</th>
      <th style="width:7%">动作</th>
      <th style="width:20%">替换后内容</th>
      <th style="width:11%">敏感类别</th>
      <th style="width:7%">敏感等级</th>
      <th>判断依据</th>
    </tr>
    {% for rep in r.replacements %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><code>{{ rep.original }}</code></td>
      <td>
        {% if rep.action == 'replace' %}
          <span class="tag tag-replace">替换</span>
        {% else %}
          <span class="tag tag-delete">删除</span>
        {% endif %}
      </td>
      <td><code>{{ rep.replacement or '（已删除）' }}</code></td>
      <td>{{ rep.entity_type }}</td>
      <td>
        {% if rep.sensitivity == 'high' %}
          <span class="tag tag-high">高</span>
        {% elif rep.sensitivity == 'medium' %}
          <span class="tag tag-medium">中</span>
        {% elif rep.sensitivity == 'low' %}
          <span class="tag tag-low">低</span>
        {% else %}
          -
        {% endif %}
      </td>
      <td>{{ rep.reason }}</td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p class="empty">未识别到敏感信息，无需脱敏。</p>
  {% endif %}
</div>
{% endfor %}

<h2>三、全批次替换对照表</h2>
{% if all_replacements %}
<table>
  <tr>
    <th style="width:4%">#</th>
    <th style="width:13%">来源文件</th>
    <th style="width:20%">原始内容</th>
    <th style="width:7%">动作</th>
    <th style="width:20%">替换后内容</th>
    <th style="width:10%">敏感类别</th>
    <th style="width:6%">等级</th>
    <th>判断依据</th>
  </tr>
  {% for rep in all_replacements %}
  <tr>
    <td>{{ loop.index }}</td>
    <td>{{ rep.source_filename }}</td>
    <td><code>{{ rep.original }}</code></td>
    <td>
      {% if rep.action == 'replace' %}
        <span class="tag tag-replace">替换</span>
      {% else %}
        <span class="tag tag-delete">删除</span>
      {% endif %}
    </td>
    <td><code>{{ rep.replacement or '（已删除）' }}</code></td>
    <td>{{ rep.entity_type }}</td>
    <td>
      {% if rep.sensitivity == 'high' %}
        <span class="tag tag-high">高</span>
      {% elif rep.sensitivity == 'medium' %}
        <span class="tag tag-medium">中</span>
      {% elif rep.sensitivity == 'low' %}
        <span class="tag tag-low">低</span>
      {% else %}
        -
      {% endif %}
    </td>
    <td>{{ rep.reason }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p class="empty">本批次未执行任何脱敏替换。</p>
{% endif %}

<div class="footer">
  本报告由 LLM 智能脱敏系统自动生成 · 仅供审核与备案使用 · {{ generated_at }}
</div>
</body>
</html>"""


class ReportGenerator:
    """脱敏报告生成器"""

    def generate(
        self,
        results: List[ProcessResult],
        output_dir: str,
        batch_id: str = None,
    ) -> str:
        """
        生成脱敏报告，返回 HTML 报告文件路径。
        同时输出 JSON 版本。
        """
        batch_id = batch_id or datetime.now().strftime("BATCH_%Y%m%d_%H%M%S")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 准备模板数据
        total_files = len(results)
        success_files = sum(1 for r in results if r.success)
        total_replacements = sum(len(r.replacements) for r in results)

        # 逐文件结果（带文件名）
        results_data = []
        all_replacements = []
        for r in results:
            src_name = os.path.basename(r.source_path)
            out_name = os.path.basename(r.output_path) if r.output_path else "-"
            item = {
                "source_path": r.source_path,
                "output_path": r.output_path,
                "source_filename": src_name,
                "output_filename": out_name,
                "file_type": r.file_type,
                "success": r.success,
                "error": r.error,
                "replacement_count": len(r.replacements),
                "replacements": [rep.to_dict() for rep in r.replacements],
            }
            results_data.append(item)
            for rep in r.replacements:
                all_replacements.append({
                    **rep.to_dict(),
                    "source_filename": src_name,
                })

        # 渲染 HTML
        template = Template(REPORT_TEMPLATE)
        html = template.render(
            batch_id=batch_id,
            generated_at=generated_at,
            total_files=total_files,
            success_files=success_files,
            total_replacements=total_replacements,
            results=results_data,
            all_replacements=all_replacements,
        )

        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, f"脱敏报告_{batch_id}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # 输出 JSON 版本
        json_path = os.path.join(output_dir, f"脱敏报告_{batch_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "batch_id": batch_id,
                    "generated_at": generated_at,
                    "summary": {
                        "total_files": total_files,
                        "success_files": success_files,
                        "total_replacements": total_replacements,
                    },
                    "results": results_data,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return html_path
