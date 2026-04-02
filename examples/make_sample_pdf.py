"""Generate a sample PDF for the simple 'sleep tips' example (offline, no API)."""
from pathlib import Path

from fpdf import FPDF


def main():
    out = Path(__file__).resolve().parent / "sample_report_sleep_tips.pdf"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Multi-Agent Research - Sample Output", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", size=11)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Your request (Goal)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, '"Give me 3 tips to sleep better."')
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Sample report (illustrative - live mode would vary)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    body = (
        "1. Keep a consistent bedtime and wake time, even on weekends.\n"
        "2. Dim screens and bright lights 1 hour before bed.\n"
        "3. Avoid large meals, caffeine, and alcohol close to bedtime.\n\n"
        "Note: In DEMO_MODE the app shows placeholder text. With OpenAI enabled, "
        "the same goal would produce a similar but AI-written report."
    )
    pdf.multi_cell(0, 6, body)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Sample JSON summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", size=9)
    pdf.multi_cell(0, 5, '{"summary": "Three behavioral sleep hygiene tips.", "tips_count": 3}')

    pdf.output(str(out))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
