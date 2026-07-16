"""
utils/report_generator.py — Generate a downloadable PDF interview report using fpdf2.
FIXED version with better error handling.
"""

import io
from datetime import datetime


def _safe(text: str) -> str:
    """Encode text safely for latin-1 (fpdf2 default). Replace unrepresentable chars."""
    if not isinstance(text, str):
        text = str(text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class PDFReport:
    def __init__(self, user_name: str, responses: list, average_score: float):
        self.user_name = user_name
        self.responses = responses
        self.average_score = average_score
        self._pdf = None

    def _build(self):
        """Build PDF report."""
        try:
            from fpdf import FPDF
        except ImportError:
            raise ImportError("fpdf2 is not installed. Run: pip install fpdf2")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ── Header ──────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(30, 64, 175)  # deep blue
        pdf.cell(0, 12, _safe("AI Interview Simulator — Report"), new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 7, _safe(f"Candidate: {self.user_name}"), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.cell(0, 7, _safe(f"Date: {datetime.now().strftime('%B %d, %Y  %H:%M')}"), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)

        # ── Overall Score ────────────────────────────────────
        pdf.set_draw_color(30, 64, 175)
        pdf.set_fill_color(239, 246, 255)
        pdf.set_text_color(30, 64, 175)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(
            0,
            12,
            _safe(f"Overall Score: {self.average_score:.1f} / 10"),
            new_x="LMARGIN",
            new_y="NEXT",
            align="C",
            fill=True,
            border=1,
        )
        pdf.ln(6)

        # ── Per-question breakdown ───────────────────────────
        if self.responses:
            for r in self.responses:
                qnum = r.get("question_number", "?")
                score = r.get("score", 0)
                question = _safe(r.get("question_text", ""))
                answer = _safe(r.get("answer_text", "(no answer)"))
                feedback = _safe(r.get("feedback", ""))
                missing_kw = r.get("missing_keywords", [])

                # Convert missing keywords to string
                if isinstance(missing_kw, list):
                    missing_kw = ", ".join([str(k) for k in missing_kw])
                else:
                    missing_kw = str(missing_kw) if missing_kw else ""

                # Question header bar
                pdf.set_fill_color(30, 64, 175)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 9, _safe(f"  Q{qnum}   Score: {score}/10"), new_x="LMARGIN", new_y="NEXT", fill=True)

                # Question text
                pdf.set_text_color(20, 20, 20)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_fill_color(245, 247, 250)
                pdf.multi_cell(0, 7, f"Question: {question}", fill=True, new_x="LMARGIN", new_y="NEXT")
                # NOTE: explicitly reset X to the left margin after every
                # multi_cell — fpdf2 can otherwise leave the cursor at the
                # right edge of the page, causing the next cell/multi_cell
                # (which uses width=0, meaning "remaining width") to receive
                # zero or negative space and raise
                # "Not enough horizontal space to render a single character".
                pdf.set_x(pdf.l_margin)

                # Answer
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 6, f"Answer: {answer}", new_x="LMARGIN", new_y="NEXT")
                pdf.set_x(pdf.l_margin)

                # Feedback
                pdf.set_text_color(22, 101, 52)
                pdf.set_font("Helvetica", "I", 10)
                if feedback:
                    pdf.multi_cell(0, 6, f"Feedback: {feedback}", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_x(pdf.l_margin)

                # Missing keywords
                if missing_kw:
                    pdf.set_text_color(153, 27, 27)
                    pdf.multi_cell(0, 6, f"Missing Keywords: {missing_kw}", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_x(pdf.l_margin)

                pdf.set_text_color(20, 20, 20)
                pdf.ln(4)
        else:
            pdf.set_text_color(100, 100, 100)
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 10, _safe("No responses available"), new_x="LMARGIN", new_y="NEXT")

        # ── Footer ───────────────────────────────────────────
        pdf.set_y(-20)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, _safe("Generated by AI Interview Simulator"), align="C")

        self._pdf = pdf

    def get_bytes(self) -> bytes:
        """Build the PDF and return it as bytes for st.download_button."""
        try:
            self._build()
            buf = io.BytesIO()

            # Get PDF output
            pdf_output = self._pdf.output()

            # Handle different return types
            if isinstance(pdf_output, bytes):
                return pdf_output
            elif isinstance(pdf_output, bytearray):
                return bytes(pdf_output)
            else:
                # String or other type
                return str(pdf_output).encode("latin-1")

        except Exception as e:
            raise Exception(f"PDF generation failed: {str(e)}")