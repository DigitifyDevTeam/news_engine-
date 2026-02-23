#!/usr/bin/env python3
"""Generate French PDF for the report matching the given English PDF filename."""
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "engine.settings.development")
import django
django.setup()

from django.conf import settings
from reports.models import WeeklyReport
from datetime import date

# From filename: weekly_report_2026-02-23_2026-02-16_2026-02-22_en.pdf
WEEK_START = date(2026, 2, 16)
WEEK_END = date(2026, 2, 22)
OUTPUT_FILENAME = "weekly_report_2026-02-23_2026-02-16_2026-02-22_fr.pdf"

def main():
    report = WeeklyReport.objects.filter(week_start=WEEK_START, week_end=WEEK_END).first()
    if not report:
        print("No report found for week 2026-02-16 to 2026-02-22.")
        return 1
    output_dir = Path(settings.BASE_DIR) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / OUTPUT_FILENAME
    pdf_buffer = report.generate_pdf(lang="fr")
    filepath.write_bytes(pdf_buffer.getvalue())
    print(f"French PDF saved: {filepath.resolve()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
