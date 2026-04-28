import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)

# ── Color Palette ─────────────────────────────────────────────────────────────
PURPLE_DEEP    = HexColor("#4C1D95")
PURPLE_PRIMARY = HexColor("#7C3AED")
PURPLE_LIGHT   = HexColor("#EDE9FE")
PURPLE_FAINT   = HexColor("#F5F3FF")
GRAY_TEXT      = HexColor("#374151")
GRAY_MUTED     = HexColor("#6B7280")
GRAY_BORDER    = HexColor("#E5E7EB")
WHITE          = HexColor("#FFFFFF")
BLACK          = HexColor("#1A1A2E")


def build_styles():
    """Creates all paragraph styles for the document."""
    styles = getSampleStyleSheet()

    custom = {
        "DocTitle": ParagraphStyle(
            "DocTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "DocSubtitle": ParagraphStyle(
            "DocSubtitle",
            fontName="Helvetica",
            fontSize=11,
            textColor=HexColor("#DDD6FE"),
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "SectionHeader": ParagraphStyle(
            "SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=PURPLE_DEEP,
            spaceBefore=14,
            spaceAfter=4,
            letterSpacing=1,
        ),
        "ActivityTitle": ParagraphStyle(
            "ActivityTitle",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=WHITE,
            spaceAfter=2,
        ),
        "ActivityMeta": ParagraphStyle(
            "ActivityMeta",
            fontName="Helvetica",
            fontSize=9,
            textColor=HexColor("#DDD6FE"),
            spaceAfter=0,
        ),
        "Label": ParagraphStyle(
            "Label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=PURPLE_PRIMARY,
            spaceBefore=6,
            spaceAfter=2,
            letterSpacing=0.5,
        ),
        "Body": ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=9,
            textColor=GRAY_TEXT,
            spaceAfter=3,
            leading=14,
        ),
        "Step": ParagraphStyle(
            "Step",
            fontName="Helvetica",
            fontSize=9,
            textColor=GRAY_TEXT,
            spaceAfter=3,
            leading=14,
            leftIndent=10,
        ),
        "MaterialItem": ParagraphStyle(
            "MaterialItem",
            fontName="Helvetica",
            fontSize=9,
            textColor=GRAY_TEXT,
            spaceAfter=2,
            leftIndent=10,
        ),
        "Advisory": ParagraphStyle(
            "Advisory",
            fontName="Helvetica",
            fontSize=9,
            textColor=PURPLE_DEEP,
            spaceAfter=3,
            leftIndent=10,
            leading=13,
        ),
        "FixedSegBody": ParagraphStyle(
            "FixedSegBody",
            fontName="Helvetica",
            fontSize=9,
            textColor=GRAY_TEXT,
            spaceAfter=3,
            leading=14,
        ),
        "FooterText": ParagraphStyle(
            "FooterText",
            fontName="Helvetica",
            fontSize=8,
            textColor=GRAY_MUTED,
            alignment=TA_CENTER,
        ),
    }
    return custom


def add_header_footer(canvas, doc):
    """Draws header and footer on every page."""
    canvas.saveState()
    w, h = A4

    # Footer line
    canvas.setStrokeColor(GRAY_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(2*cm, 1.8*cm, w - 2*cm, 1.8*cm)

    # Footer text
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAY_MUTED)
    canvas.drawString(2*cm, 1.2*cm, "ScoutMind - Lebanese Scouts Association")
    canvas.drawRightString(w - 2*cm, 1.2*cm, f"Page {doc.page}")

    canvas.restoreState()


def export_plan_to_pdf(plan: dict, output_path: str) -> str:
    """
    Exports a meeting plan dict to a professional PDF document.

    Args:
        plan:        Meeting plan dict from formatting agent
        output_path: Full path where PDF should be saved

    Returns:
        Path to the generated PDF file
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm,
    )

    styles  = build_styles()
    story   = []
    header  = plan.get("header", {})
    w, h    = A4
    usable_w = w - 4*cm

    # ── Cover Header Block ────────────────────────────────────────────────────
    header_data = [[
        Paragraph(header.get("title", "SCOUT MEETING PLAN"), styles["DocTitle"]),
    ]]
    header_table = Table(header_data, colWidths=[usable_w])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), PURPLE_DEEP),
        ("TOPPADDING",  (0,0), (-1,-1), 18),
        ("BOTTOMPADDING",(0,0),(-1,-1), 14),
        ("LEFTPADDING", (0,0), (-1,-1), 20),
        ("RIGHTPADDING",(0,0), (-1,-1), 20),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # ── Meta Info Table ───────────────────────────────────────────────────────
    meta_rows = [
        ["Unit",            header.get("unit", "") + f" ({header.get('age_range','')}, {header.get('gender','')})"],
        ["Theme",           header.get("theme", "")],
        ["Date",            header.get("date", "")],
        ["Total Duration",  header.get("total_duration", "")],
        ["Generated By",    header.get("generated_by", "")],
    ]
    meta_table = Table(
        [[Paragraph(k, styles["Label"]), Paragraph(v, styles["Body"])] for k, v in meta_rows],
        colWidths=[3.5*cm, usable_w - 3.5*cm],
    )
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), PURPLE_FAINT),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [WHITE, PURPLE_FAINT]),
        ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.3, GRAY_BORDER),
        ("ROUNDEDCORNERS",[4]),
    ]))
    story.append(meta_table)

    # ── Context Advisories ────────────────────────────────────────────────────
    advisories = plan.get("context_advisories", [])
    if advisories:
        story.append(Spacer(1, 10))
        story.append(Paragraph("CONTEXTUAL ADVISORIES", styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE_LIGHT))
        story.append(Spacer(1, 4))
        for advisory in advisories:
            story.append(Paragraph(f"• {advisory}", styles["Advisory"]))

    # ── Master Materials List ─────────────────────────────────────────────────
    materials = plan.get("master_materials_list", [])
    if materials:
        story.append(Spacer(1, 10))
        story.append(Paragraph("MATERIALS & PREPARATION LIST", styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE_LIGHT))
        story.append(Spacer(1, 4))

        # Split into two columns
        mid     = (len(materials) + 1) // 2
        col1    = materials[:mid]
        col2    = materials[mid:]
        max_len = max(len(col1), len(col2))

        mat_rows = []
        for i in range(max_len):
            c1 = Paragraph(f"• {col1[i]}" if i < len(col1) else "", styles["MaterialItem"])
            c2 = Paragraph(f"• {col2[i]}" if i < len(col2) else "", styles["MaterialItem"])
            mat_rows.append([c1, c2])

        mat_table = Table(mat_rows, colWidths=[usable_w/2, usable_w/2])
        mat_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), PURPLE_FAINT),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("RIGHTPADDING",  (0,0), (-1,-1), 8),
            ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, GRAY_BORDER),
        ]))
        story.append(mat_table)

    # ── Meeting Schedule ──────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(Paragraph("MEETING SCHEDULE", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PURPLE_PRIMARY))
    story.append(Spacer(1, 6))

    for segment in plan.get("schedule", []):
        seg_elements = []

        is_fixed = segment.get("segment_type") == "fixed"
        bg_color  = PURPLE_DEEP if is_fixed else PURPLE_PRIMARY

        # Segment header
        time_str  = f"{segment['time_start']} - {segment['time_end']}  |  {segment['duration']}"
        title_str = segment.get("segment_title", "")

        header_data = [[
            Paragraph(title_str, styles["ActivityTitle"]),
            Paragraph(time_str,  styles["ActivityMeta"]),
        ]]
        seg_header = Table(header_data, colWidths=[usable_w * 0.65, usable_w * 0.35])
        seg_header.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), bg_color),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (-1,-1), 12),
            ("RIGHTPADDING",  (0,0), (-1,-1), 12),
            ("ALIGN",         (1,0), (1,0), "RIGHT"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]))
        seg_elements.append(seg_header)

        # Segment body
        body_rows = []

        if is_fixed:
            body_rows.append([
                Paragraph("Description", styles["Label"]),
                Paragraph(segment.get("description", ""), styles["FixedSegBody"]),
            ])
            if segment.get("materials"):
                mat_text = "  •  ".join(segment["materials"])
                body_rows.append([
                    Paragraph("Materials", styles["Label"]),
                    Paragraph(mat_text, styles["FixedSegBody"]),
                ])
            if segment.get("leader_notes"):
                body_rows.append([
                    Paragraph("Leader Notes", styles["Label"]),
                    Paragraph(segment["leader_notes"], styles["FixedSegBody"]),
                ])
        else:
            # Activity type and energy
            type_str = f"{segment.get('segment_type','').replace('_',' ').title()}  |  Energy: {segment.get('energy_level','').capitalize()}"
            body_rows.append([
                Paragraph("Type", styles["Label"]),
                Paragraph(type_str, styles["Body"]),
            ])

            # Objective
            if segment.get("objective"):
                body_rows.append([
                    Paragraph("Objective", styles["Label"]),
                    Paragraph(segment["objective"], styles["Body"]),
                ])

            # Instructions
            if segment.get("instructions"):
                instructions = segment["instructions"]
                if isinstance(instructions, list):
                    instr_text = "<br/>".join(
                        f"{i+1}. {step}" for i, step in enumerate(instructions)
                    )
                else:
                    instr_text = str(instructions)
                body_rows.append([
                    Paragraph("Instructions", styles["Label"]),
                    Paragraph(instr_text, styles["Step"]),
                ])

            # Materials
            if segment.get("materials"):
                mat_text = "<br/>".join(f"• {m}" for m in segment["materials"])
                body_rows.append([
                    Paragraph("Materials", styles["Label"]),
                    Paragraph(mat_text, styles["MaterialItem"]),
                ])

            # Educational technique
            if segment.get("educational_technique"):
                body_rows.append([
                    Paragraph("Ed. Technique", styles["Label"]),
                    Paragraph(str(segment["educational_technique"]), styles["Body"]),
                ])

            # Leader tips
            if segment.get("leader_tips"):
                body_rows.append([
                    Paragraph("Leader Tips", styles["Label"]),
                    Paragraph(segment["leader_tips"], styles["Body"]),
                ])

            # Theme connection
            if segment.get("theme_connection"):
                body_rows.append([
                    Paragraph("Theme Link", styles["Label"]),
                    Paragraph(segment["theme_connection"], styles["Body"]),
                ])

        body_table = Table(
            body_rows,
            colWidths=[3*cm, usable_w - 3*cm],
        )
        body_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), WHITE),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("RIGHTPADDING",  (0,0), (-1,-1), 10),
            ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, GRAY_BORDER),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        seg_elements.append(body_table)
        seg_elements.append(Spacer(1, 8))

        story.append(KeepTogether(seg_elements))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_BORDER))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by ScoutMind on {header.get('generated_at', '')} - Lebanese Scouts Association",
        styles["FooterText"],
    ))

    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    return output_path


if __name__ == "__main__":
    # Quick test with dummy plan
    from agents.formatting import run_formatting_agent

    test_activities = [
        {
            "slot": 1, "activity_name": "Zip Zap Boing", "activity_type": "game",
            "duration_minutes": 10, "energy_level": "high",
            "objective": "Energise the group and build focus.",
            "instructions": ["Stand in a circle.", "Pass zip left, zap right, boing reflects.", "Eliminate hesitators."],
            "materials": ["None required"],
            "educational_technique": {"name": "Energiser Break", "application": "Resets attention before cognitive activities."},
            "leader_tips": "Keep energy high. Play 2-3 rounds.",
            "theme_connection": "Builds group cohesion central to friendship.",
        },
        {
            "slot": 2, "activity_name": "Friendship Web Discussion", "activity_type": "lecture",
            "duration_minutes": 20, "energy_level": "low",
            "objective": "Explore the qualities of true friendship using Think-Pair-Share.",
            "instructions": ["Open with a short story about scouts.", "Ask what the scouts did right.", "Think-Pair-Share on friendship values.", "Visual anchor: draw a friendship symbol."],
            "materials": ["Whiteboard", "Markers", "Notebooks and pens"],
            "educational_technique": {"name": "Think-Pair-Share", "application": "Used in discussion phase to include all voices."},
            "leader_tips": "Encourage quiet members to share with their partner first.",
            "theme_connection": "Directly explores the meeting theme of friendship.",
        },
    ]

    plan = run_formatting_agent(
        unit="Cubs",
        theme="Friendship",
        meeting_date="27/04/2026",
        activities=test_activities,
        master_materials=["Whiteboard", "Markers", "Notebooks and pens"],
    )

    output = export_plan_to_pdf(plan, "outputs/test_meeting_plan.pdf")
    print(f"PDF generated: {output}")