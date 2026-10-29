import io
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable
)

from backend.models.roadmap import InterviewAnalysisRoadmap
from backend.models.user import User

logger = logging.getLogger("uvicorn.error")


def _safe_escape(text: Any, default: str = "N/A") -> str:
    """Escapes XML entities so strings can safely be embedded in ReportLab Paragraphs."""
    if text is None:
        return default
    s = str(text).strip()
    if not s:
        return default
    return xml_escape(s)


def _safe_json_load(text_val: Any) -> List[Dict[str, Any]]:
    """Safely deserializes JSON lists from database text fields."""
    if not text_val:
        return []
    if isinstance(text_val, list):
        return text_val
    try:
        data = json.loads(text_val)
        return data if isinstance(data, list) else []
    except Exception:
        return []


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas that accumulates page states to print 'Page X of Y',
    running document headers, and professional footers on all pages.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running header on pages > 1
        if self._pageNumber > 1:
            self.drawString(36, 756, "InterviewAI  |  Personalized Preparation Roadmap & Diagnostic Analysis")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.6)
            self.line(36, 750, 576, 750)

        # Running footer on all pages
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.6)
        self.line(36, 40, 576, 40)

        footer_text = "InterviewAI  •  Confidential Candidate Intelligence & Preparation Roadmap"
        self.drawString(36, 28, footer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 28, page_str)

        self.restoreState()


class RoadmapPDFService:
    """Service to generate professional, multi-page PDF roadmap reports."""

    @classmethod
    def generate_roadmap_pdf(
        cls,
        roadmap: InterviewAnalysisRoadmap,
        user: Optional[User] = None
    ) -> bytes:
        """
        Builds a comprehensive, publication-quality PDF roadmap report
        based strictly on the authenticated user's saved roadmap record.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=46,
            bottomMargin=46
        )

        styles = getSampleStyleSheet()

        # Custom high-readability typography styles
        styles.add(ParagraphStyle(
            'DocTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1E3A8A"),
            spaceAfter=3
        ))
        styles.add(ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=10
        ))
        styles.add(ParagraphStyle(
            'SectionTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True
        ))
        styles.add(ParagraphStyle(
            'SubsectionTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#2563EB"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True
        ))
        styles.add(ParagraphStyle(
            'BodyRegular',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1E293B")
        ))
        styles.add(ParagraphStyle(
            'BodyMuted',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748B")
        ))
        styles.add(ParagraphStyle(
            'MetaLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#64748B")
        ))
        styles.add(ParagraphStyle(
            'MetaVal',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0F172A")
        ))
        styles.add(ParagraphStyle(
            'TableHead',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white
        ))
        styles.add(ParagraphStyle(
            'TableCellRegular',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1E293B")
        ))
        styles.add(ParagraphStyle(
            'TableCellBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#0F172A")
        ))
        styles.add(ParagraphStyle(
            'TableCellCode',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#1E293B")
        ))

        story = []
        usable_width = 540.0  # 612 - 36 - 36

        # ==========================================
        # 1. HEADER & BRANDING
        # ==========================================
        header_table_data = [
            [
                Paragraph("<b>INTERVIEWAI INTELLIGENCE REPORT</b>", ParagraphStyle(
                    'HeaderKicker', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor("#2563EB")
                )),
                Paragraph(f"<b>Generated:</b> {_safe_escape(datetime.utcnow().strftime('%B %d, %Y'))}", ParagraphStyle(
                    'HeaderDate', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor("#64748B"), alignment=2
                ))
            ],
            [
                Paragraph("Personalized Preparation Roadmap & Performance Analysis", styles['DocTitle']),
                Paragraph("CONFIDENTIAL", ParagraphStyle(
                    'ConfBadge', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor("#DC2626"), alignment=2
                ))
            ],
            [
                Paragraph("Comprehensive diagnostic findings, identified skill gaps, prioritized daily study tasks, and retest questions.", styles['DocSubtitle']),
                ""
            ]
        ]
        header_table = Table(header_table_data, colWidths=[420, 120])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('SPAN', (0, 2), (1, 2)),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceBefore=4, spaceAfter=10))

        # ==========================================
        # 2. CANDIDATE & INTERVIEW METADATA CARD
        # ==========================================
        candidate_name = (user.name if user and user.name else (user.email if user else "Authenticated Candidate"))
        candidate_email = (user.email if user and user.email else "Registered User")
        target_role = getattr(roadmap, 'target_role', 'Software Engineer') or 'Software Engineer'
        target_diff = getattr(roadmap, 'target_difficulty', 'Medium') or 'Medium'
        readiness_score = round(float(getattr(roadmap, 'readiness_score', 0.0) or 0.0), 1)
        readiness_level = getattr(roadmap, 'readiness_level', 'Needs Preparation') or 'Needs Preparation'
        daily_hours = round(float(getattr(roadmap, 'daily_study_hours', 2.0) or 2.0), 1)
        target_date_raw = getattr(roadmap, 'target_interview_date', None)
        target_date_formatted = target_date_raw if target_date_raw else "Flexible / Not Fixed"

        meta_col_w = usable_width / 4.0
        meta_table_data = [
            [
                Paragraph("CANDIDATE", styles['MetaLabel']),
                Paragraph("TARGET ROLE", styles['MetaLabel']),
                Paragraph("READINESS SCORE", styles['MetaLabel']),
                Paragraph("STUDY COMMITMENT", styles['MetaLabel']),
            ],
            [
                Paragraph(_safe_escape(candidate_name), styles['MetaVal']),
                Paragraph(f"{_safe_escape(target_role)} ({_safe_escape(target_diff)})", styles['MetaVal']),
                Paragraph(f"{readiness_score}%  <font size=7.5 color='#2563EB'>({_safe_escape(readiness_level)})</font>", styles['MetaVal']),
                Paragraph(f"{daily_hours} hrs/day", styles['MetaVal']),
            ],
            [
                Paragraph("ACCOUNT EMAIL", styles['MetaLabel']),
                Paragraph("TARGET DATE", styles['MetaLabel']),
                Paragraph("ANALYSIS ID", styles['MetaLabel']),
                Paragraph("ROADMAP PHASES", styles['MetaLabel']),
            ],
            [
                Paragraph(_safe_escape(candidate_email), styles['BodyMuted']),
                Paragraph(_safe_escape(target_date_formatted), styles['BodyMuted']),
                Paragraph(f"{_safe_escape(str(roadmap.id)[:12])}...", styles['BodyMuted']),
                Paragraph("4 Sequenced Phases", styles['BodyMuted']),
            ]
        ]
        meta_table = Table(meta_table_data, colWidths=[meta_col_w, meta_col_w, meta_col_w, meta_col_w])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # ==========================================
        # 3. EXECUTIVE SUMMARY & AI ROADMAP ANALYSIS
        # ==========================================
        story.append(Paragraph("1. Executive Summary & Diagnostic Intelligence", styles['SectionTitle']))
        exec_summary_text = getattr(roadmap, 'executive_summary', '') or "No executive summary recorded for this interview session."
        
        exec_table_data = [[
            Paragraph(
                f"<b>AI Diagnostic Overview:</b><br/>{_safe_escape(exec_summary_text)}",
                styles['BodyRegular']
            )
        ]]
        exec_table = Table(exec_table_data, colWidths=[usable_width])
        exec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#BFDBFE")),
            ('LINELEFT', (0, 0), (0, -1), 3.5, colors.HexColor("#2563EB")),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(exec_table)
        story.append(Spacer(1, 12))

        # ==========================================
        # 4. PREPARATION PROGRESS & EFFORT METRICS
        # ==========================================
        tasks_list = _safe_json_load(roadmap.roadmap_tasks)
        total_tasks = len(tasks_list)
        completed_tasks = [t for t in tasks_list if t.get('status') == 'completed']
        completed_count = len(completed_tasks)
        completion_pct = round((completed_count / max(1, total_tasks)) * 100, 1) if total_tasks > 0 else 0.0

        total_hours = sum(float(t.get('estimated_duration_hours', 2.0) or 2.0) for t in tasks_list)
        completed_hours = sum(float(t.get('estimated_duration_hours', 2.0) or 2.0) for t in completed_tasks)
        remaining_hours = max(0.0, total_hours - completed_hours)
        critical_tasks_pending = len([t for t in tasks_list if t.get('priority') == 'CRITICAL' and t.get('status') != 'completed'])

        story.append(Paragraph("2. Preparation Progress & Effort Metrics", styles['SectionTitle']))
        stat_w = usable_width / 4.0
        stats_table_data = [
            [
                Paragraph("<b>ROADMAP PROGRESS</b>", styles['MetaLabel']),
                Paragraph("<b>TASKS COMPLETED</b>", styles['MetaLabel']),
                Paragraph("<b>TOTAL EFFORT</b>", styles['MetaLabel']),
                Paragraph("<b>CRITICAL PENDING</b>", styles['MetaLabel']),
            ],
            [
                Paragraph(f"<font color='#059669'><b>{completion_pct}%</b></font>", ParagraphStyle('Stat1', fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=colors.HexColor("#059669"))),
                Paragraph(f"<b>{completed_count}</b> of {total_tasks} Tasks", styles['MetaVal']),
                Paragraph(f"<b>{round(total_hours, 1)} hrs</b> ({round(remaining_hours, 1)} left)", styles['MetaVal']),
                Paragraph(f"<font color='#DC2626'><b>{critical_tasks_pending}</b></font>", ParagraphStyle('Stat4', fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=colors.HexColor("#DC2626"))),
            ]
        ]
        stats_table = Table(stats_table_data, colWidths=[stat_w, stat_w, stat_w, stat_w])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 14))

        # ==========================================
        # 5. IDENTIFIED SKILL GAPS & ROOT CAUSE ANALYSIS
        # ==========================================
        skill_gaps = _safe_json_load(roadmap.skill_gaps)
        story.append(Paragraph("3. Identified Skill Gaps & Root Cause Analysis", styles['SectionTitle']))
        story.append(Paragraph(
            "Evidence-linked gaps identified during candidate response evaluation, categorized by severity with remediation paths.",
            styles['BodyMuted']
        ))
        story.append(Spacer(1, 4))

        if not skill_gaps:
            no_gaps_table = Table([[Paragraph("<i>No critical skill gaps identified in this evaluation. Candidate met baseline expectations.</i>", styles['BodyMuted'])]], colWidths=[usable_width])
            no_gaps_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ]))
            story.append(no_gaps_table)
        else:
            gap_col_w = [110, 145, 145, 140]
            gaps_table_data = [[
                Paragraph("<b>Competency & Priority</b>", styles['TableHead']),
                Paragraph("<b>Root Cause / What Was Missing</b>", styles['TableHead']),
                Paragraph("<b>Why It Matters & Impact</b>", styles['TableHead']),
                Paragraph("<b>Prescribed Remediation Path</b>", styles['TableHead'])
            ]]

            for gap in skill_gaps:
                competency = _safe_escape(gap.get('competency', 'General Competency'))
                category = _safe_escape(gap.get('category', 'Technical'))
                priority = _safe_escape(gap.get('priority', 'HIGH'))
                prio_color = "#DC2626" if priority == "CRITICAL" else ("#EA580C" if priority == "HIGH" else "#2563EB")

                missing = _safe_escape(gap.get('what_was_missing_or_incorrect', 'Demonstrated incomplete conceptual grasp.'))
                why = _safe_escape(gap.get('why_it_matters', 'Essential for reliable production engineering.'))
                correct = _safe_escape(gap.get('correct_understanding', ''))

                rem = gap.get('remediation_path') or {}
                what_to_learn = _safe_escape(rem.get('what_to_learn', ''))
                what_to_practice = _safe_escape(rem.get('what_to_practice', ''))
                how_to_verify = _safe_escape(rem.get('how_to_verify', ''))

                comp_p = Paragraph(
                    f"<b>{competency}</b><br/>"
                    f"<font size=7 color='#64748B'>{category}</font><br/>"
                    f"<font size=7.5 color='{prio_color}'><b>[{priority}]</b></font>",
                    styles['TableCellBold']
                )

                missing_p = Paragraph(
                    f"{missing}" + (f"<br/><br/><b>Benchmark:</b> {correct}" if correct and correct != "N/A" else ""),
                    styles['TableCellRegular']
                )

                why_p = Paragraph(f"{why}", styles['TableCellRegular'])

                rem_text = []
                if what_to_learn and what_to_learn != "N/A":
                    rem_text.append(f"<b>Learn:</b> {what_to_learn}")
                if what_to_practice and what_to_practice != "N/A":
                    rem_text.append(f"<b>Practice:</b> {what_to_practice}")
                if how_to_verify and how_to_verify != "N/A":
                    rem_text.append(f"<b>Verify:</b> {how_to_verify}")
                rem_combined = "<br/><br/>".join(rem_text) if rem_text else "Self-study curriculum assigned."
                rem_p = Paragraph(rem_combined, styles['TableCellRegular'])

                gaps_table_data.append([comp_p, missing_p, why_p, rem_p])

            gaps_table = Table(gaps_table_data, colWidths=gap_col_w, repeatRows=1)
            gaps_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.append(gaps_table)

        story.append(Spacer(1, 14))

        # ==========================================
        # 6. DEMONSTRATED STRENGTHS
        # ==========================================
        strengths = _safe_json_load(roadmap.strengths)
        if strengths:
            story.append(Paragraph("4. Demonstrated Technical Strengths", styles['SectionTitle']))
            strength_col_w = [140, 400]
            str_table_data = [[
                Paragraph("<b>Competency & Domain</b>", styles['TableHead']),
                Paragraph("<b>Demonstrated Mastery & Evaluator Evidence</b>", styles['TableHead'])
            ]]
            for s in strengths:
                comp = _safe_escape(s.get('competency', 'Strength'))
                cat = _safe_escape(s.get('category', 'Technical'))
                mastery = _safe_escape(s.get('demonstrated_mastery', 'Demonstrated strong proficiency.'))
                str_table_data.append([
                    Paragraph(f"<b>{comp}</b><br/><font size=7 color='#059669'>{cat}</font>", styles['TableCellBold']),
                    Paragraph(mastery, styles['TableCellRegular'])
                ])
            str_table = Table(str_table_data, colWidths=strength_col_w, repeatRows=1)
            str_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#065F46")),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0FDF4")]),
            ]))
            story.append(str_table)
            story.append(Spacer(1, 14))

        # ==========================================
        # 7. PRIORITIZED 4-PHASE ROADMAP & LEARNING TASKS
        # ==========================================
        phases_list = _safe_json_load(roadmap.roadmap_phases)
        story.append(Paragraph("5. Prioritized 4-Phase Learning Roadmap", styles['SectionTitle']))
        story.append(Paragraph(
            "Dynamic curriculum engineered from direct performance evidence. Complete tasks and mark progress to recalibrate readiness.",
            styles['BodyMuted']
        ))
        story.append(Spacer(1, 6))

        # Group tasks by phase number
        tasks_by_phase: Dict[int, List[Dict[str, Any]]] = {}
        for t in tasks_list:
            p_num = int(t.get('phase_number', 1) or 1)
            tasks_by_phase.setdefault(p_num, []).append(t)

        default_phases = [
            {"phase_number": 1, "title": "Core Fundamentals & Direct Gap Remediation", "duration_weeks": 1.5, "milestone": "Master missing core concepts."},
            {"phase_number": 2, "title": "Architecture, Scalability & Deep Design", "duration_weeks": 2.0, "milestone": "Construct resilient architectural designs."},
            {"phase_number": 3, "title": "Applied Coding & Problem Solving", "duration_weeks": 1.5, "milestone": "Implement production-grade algorithms smoothly."},
            {"phase_number": 4, "title": "Mock Simulation & Behavioral Readiness", "duration_weeks": 1.0, "milestone": "Full interview readiness re-test."}
        ]

        active_phases = phases_list if phases_list else default_phases

        for phase in sorted(active_phases, key=lambda x: int(x.get('phase_number', 1))):
            p_num = int(phase.get('phase_number', 1))
            p_title = _safe_escape(phase.get('title', f"Phase {p_num}"))
            p_dur = _safe_escape(str(phase.get('duration_weeks', 1.5)))
            p_milestone = _safe_escape(phase.get('milestone', ''))
            focus_areas = phase.get('focus_areas', [])
            focus_str = ", ".join([_safe_escape(f) for f in focus_areas]) if focus_areas else ""

            # Phase Banner
            phase_banner_text = (
                f"<b>PHASE {p_num}: {p_title.upper()}</b>  "
                f"<font size=8 color='#2563EB'>({p_dur} Weeks)</font><br/>"
                f"<font size=8 color='#475569'><b>Milestone:</b> {p_milestone}" +
                (f"  |  <b>Focus:</b> {focus_str}" if focus_str else "") + "</font>"
            )
            phase_banner_table = Table([[Paragraph(phase_banner_text, styles['BodyRegular'])]], colWidths=[usable_width])
            phase_banner_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                ('LINELEFT', (0, 0), (0, -1), 3, colors.HexColor("#2563EB")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))

            phase_elements = [phase_banner_table, Spacer(1, 4)]

            phase_tasks = tasks_by_phase.get(p_num, [])
            if not phase_tasks:
                no_task_table = Table([[Paragraph("<i>No individual tasks assigned to this phase.</i>", styles['BodyMuted'])]], colWidths=[usable_width])
                no_task_table.setStyle(TableStyle([
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ]))
                phase_elements.append(no_task_table)
            else:
                task_col_w = [55, 155, 220, 45, 65]
                task_table_data = [[
                    Paragraph("<b>Seq / Prio</b>", styles['TableHead']),
                    Paragraph("<b>Topic & Objectives</b>", styles['TableHead']),
                    Paragraph("<b>Practical Exercise & Completion Criteria</b>", styles['TableHead']),
                    Paragraph("<b>Effort</b>", styles['TableHead']),
                    Paragraph("<b>Status</b>", styles['TableHead'])
                ]]

                for t in sorted(phase_tasks, key=lambda x: int(x.get('day_or_sequence', 1) or 1)):
                    seq = _safe_escape(str(t.get('day_or_sequence', 1)))
                    prio = _safe_escape(t.get('priority', 'HIGH'))
                    prio_color = "#DC2626" if prio == "CRITICAL" else ("#EA580C" if prio == "HIGH" else "#2563EB")

                    topic = _safe_escape(t.get('topic', 'Learning Task'))
                    objectives = t.get('learning_objectives', [])
                    obj_str = "<br/>• ".join([_safe_escape(o) for o in objectives[:3]]) if objectives else ""

                    exercise = _safe_escape(t.get('practical_exercise', 'Complete practical exercise.'))
                    criteria = _safe_escape(t.get('completion_criteria', 'Self-verify and review.'))
                    effort = f"{round(float(t.get('estimated_duration_hours', 2.0) or 2.0), 1)}h"
                    
                    status = t.get('status', 'pending')
                    is_completed = (status == 'completed')
                    status_badge = "<font color='#059669'><b>[✔] Done</b></font>" if is_completed else "<font color='#64748B'>[ ] Pending</font>"

                    seq_p = Paragraph(f"<b>Day {seq}</b><br/><font size=7 color='{prio_color}'><b>{prio}</b></font>", styles['TableCellBold'])
                    topic_p = Paragraph(
                        f"<b>{topic}</b>" + (f"<br/><font size=7 color='#475569'>• {obj_str}</font>" if obj_str else ""),
                        styles['TableCellRegular']
                    )
                    exercise_p = Paragraph(
                        f"<b>Exercise:</b> {exercise}<br/>"
                        f"<font size=7.5 color='#2563EB'><b>Criteria:</b> {criteria}</font>",
                        styles['TableCellRegular']
                    )
                    effort_p = Paragraph(effort, styles['TableCellRegular'])
                    status_p = Paragraph(status_badge, styles['TableCellRegular'])

                    task_table_data.append([seq_p, topic_p, exercise_p, effort_p, status_p])

                task_table = Table(task_table_data, colWidths=task_col_w, repeatRows=1)
                task_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ]))
                phase_elements.append(task_table)

            story.append(KeepTogether(phase_elements))
            story.append(Spacer(1, 10))

        # ==========================================
        # 8. DIAGNOSTIC RETEST QUESTIONS & NEXT STEPS
        # ==========================================
        reassessment_qs = _safe_json_load(roadmap.reassessment_questions)
        story.append(Paragraph("6. Diagnostic Retest Questions & Actionable Next Steps", styles['SectionTitle']))
        story.append(Paragraph(
            "Use these targeted re-test questions after completing Phase 1 & 2 remediation to evaluate concept retention.",
            styles['BodyMuted']
        ))
        story.append(Spacer(1, 4))

        if reassessment_qs:
            q_col_w = [140, 400]
            retest_table_data = [[
                Paragraph("<b>Competency & Difficulty</b>", styles['TableHead']),
                Paragraph("<b>Diagnostic Retest Question & Benchmark Solution</b>", styles['TableHead'])
            ]]
            for q in reassessment_qs:
                comp = _safe_escape(q.get('competency', 'Target Competency'))
                diff = _safe_escape(q.get('difficulty', 'Medium'))
                diff_color = "#DC2626" if diff == "Hard" else ("#2563EB" if diff == "Medium" else "#059669")
                q_text = _safe_escape(q.get('question_text', 'Diagnostic question.'))
                bench = _safe_escape(q.get('benchmark_solution', ''))
                key_pts = q.get('expected_key_points', [])
                key_pts_str = "<br/>• ".join([_safe_escape(pt) for pt in key_pts]) if key_pts else ""

                retest_table_data.append([
                    Paragraph(f"<b>{comp}</b><br/><font size=7 color='{diff_color}'><b>[{diff}]</b></font>", styles['TableCellBold']),
                    Paragraph(
                        f"<b>Question:</b> {q_text}<br/>" +
                        (f"<font size=7.5 color='#475569'><b>Expected Key Points:</b><br/>• {key_pts_str}</font><br/>" if key_pts_str else "") +
                        (f"<font size=7.5 color='#2563EB'><b>Benchmark Solution:</b> {bench}</font>" if bench and bench != "N/A" else ""),
                        styles['TableCellRegular']
                    )
                ])

            retest_table = Table(retest_table_data, colWidths=q_col_w, repeatRows=1)
            retest_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.append(retest_table)
            story.append(Spacer(1, 10))

        # Recommended Next Steps Box
        next_steps_text = (
            "<b>Recommended Next Steps:</b><br/>"
            "1. <b>Focus on Critical Gaps:</b> Complete Day 1-3 tasks in Phase 1 before attempting full architectural questions.<br/>"
            "2. <b>Practice Verifiable Code:</b> Build the suggested code artifacts in a local sandbox or the InterviewAI coding studio.<br/>"
            "3. <b>Schedule Diagnostic Retest:</b> Once Phase 2 is completed, run another adaptive mock interview to recalibrate your readiness score.<br/>"
            "4. <b>Dynamic Pace Adjustment:</b> If your interview date changes, use the Schedule Calibrator on the web roadmap to update daily duration targets."
        )
        next_steps_table = Table([[Paragraph(next_steps_text, styles['BodyRegular'])]], colWidths=[usable_width])
        next_steps_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
            ('LINELEFT', (0, 0), (0, -1), 3.5, colors.HexColor("#059669")),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(next_steps_table)

        # Build document with NumberedCanvas
        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
