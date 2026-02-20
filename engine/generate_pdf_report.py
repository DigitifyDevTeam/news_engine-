#!/usr/bin/env python3
"""
Generate PDF report locally and save it for download.
Run this script to generate the latest report as PDF.
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'engine.settings.development')
django.setup()

from reports.models import WeeklyReport

def generate_latest_report_pdf():
    """Generate PDF for the latest weekly report."""
    
    print("🔍 Searching for latest report...")
    
    # Get the latest report
    latest_report = WeeklyReport.objects.order_by('-week_start').first()
    
    if not latest_report:
        print("❌ No reports found. Please run the pipeline first.")
        return None
    
    print(f"📊 Found report: {latest_report.week_start} to {latest_report.week_end}")
    print(f"📈 Signals: {latest_report.signal_count}, Sources: {latest_report.source_count}")
    
    if latest_report.signal_count == 0:
        print("⚠️  This report has no signals. PDF will be empty.")
    
    try:
        print("🔄 Generating PDFs (EN + FR)...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = []

        for lang in ("en", "fr"):
            pdf_buffer = latest_report.generate_pdf(lang=lang)
            filename = f"report_{latest_report.week_start}_{timestamp}_{lang}.pdf"
            filepath = os.path.join(os.getcwd(), filename)
            with open(filepath, 'wb') as f:
                f.write(pdf_buffer.getvalue())
            file_size = len(pdf_buffer.getvalue())
            print(f"  ✅ {lang.upper()}: {filename} ({file_size:,} bytes)")
            paths.append(filepath)

        print(f"📂 Directory: {os.getcwd()}")
        return paths

    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function."""
    print("=" * 60)
    print("🚀 NEWS ENGINE - PDF REPORT GENERATOR")
    print("=" * 60)
    
    # Generate the PDF
    pdf_file = generate_latest_report_pdf()
    
    if pdf_file:
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! PDF reports are ready for download.")
        print("=" * 60)
        for p in pdf_file:
            print(f"📄 {os.path.basename(p)}")
        print(f"📂 Location: {os.path.dirname(pdf_file[0])}")
        print("\n💡 You can now:")
        print("   • Open the PDFs directly")
        print("   • Email them to stakeholders")
        print("   • Upload them to your document system")
        print("   • Share them with your team")
    else:
        print("\n" + "=" * 60)
        print("❌ FAILED! Could not generate PDF.")
        print("=" * 60)
        print("💡 Make sure:")
        print("   • You have run the pipeline at least once")
        print("   • There are articles and signals in the database")
        print("   • The PDF generation service is working")

if __name__ == "__main__":
    main()
