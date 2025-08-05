import os

from weasyprint import HTML

from src.models.analysis import Analysis


def render_analysis_info(analysis: Analysis):
    return f"""
    <section>
      <div class="section-title">Analysis Metadata</div>
      <div class="feedback-block">
        <p><strong>Analysis ID:</strong> {analysis.id}</p>
        <p><strong>User ID:</strong> {analysis.user_id}</p>
        <p><strong>Session ID:</strong> {analysis.session_id}</p>
        <p><strong>Model Name:</strong> {analysis.model_name}</p>
        <p><strong>Status:</strong> {analysis.status}</p>
        <p><strong>Created At:</strong> {analysis.created_at}</p>
      </div>
    </section>
    <div class="page-break"></div>
    """


def render_entry(label, entry):
    blocks = []

    if "critique" in entry:
        blocks.append(f'<div class="label">{label}:</div>')
        blocks.append(f'<div class="critique">{entry["critique"]}</div>')

    if "commendation" in entry:
        blocks.append(f'<div class="label">{label}:</div>')
        blocks.append(f'<div class="commendation">{entry["commendation"]}</div>')

    if "suggestions" in entry:
        blocks.append(
            "<ul>" + "".join(f"<li>{s}</li>" for s in entry["suggestions"]) + "</ul>"
        )

    return "\n".join(blocks)


def render_section(title, view_data):
    section_html = [f'<section><div class="section-title">{title} View</div>']
    for key, entry in view_data.items():
        section_html.append('<div class="feedback-block">')
        section_html.append(render_entry(key.replace("_", " ").title(), entry))
        section_html.append("</div>")
    section_html.append("</section>")
    return "\n".join(section_html)


def generate_pdf_report(analysis: Analysis, feedback_data):
    html_sections = []

    html_sections.append(render_analysis_info(analysis))

    for view, view_data in feedback_data.items():
        html_sections.append(render_section(view.title(), view_data))
        html_sections.append('<div class="page-break"></div>')

    html_contents = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Posture Feedback Report</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      padding: 40px;
      color: #333;
      line-height: 1.6;
    }}
    h1 {{
      text-align: center;
      margin-bottom: 40px;
    }}
    .section-title {{
      background-color: #f0f0f0;
      padding: 10px;
      font-size: 22px;
      border-left: 6px solid #007BFF;
    }}
    .feedback-block {{
      margin: 15px 0;
      padding-left: 20px;
    }}
    .label {{
      font-weight: bold;
      font-size: 16px;
      margin-top: 10px;
    }}
    .commendation {{
      color: green;
    }}
    .critique {{
      color: #d9534f;
    }}
    ul {{
      margin-top: 5px;
    }}
    .page-break {{
      page-break-after: always;
    }}
  </style>
</head>
<body>
  <h1>Posture Feedback Report</h1>
  {''.join(html_sections)}
</body>
</html>
"""

    pdf_bytes = HTML(string=html_contents).write_pdf()

    return pdf_bytes
