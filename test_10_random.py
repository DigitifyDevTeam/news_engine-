#!/usr/bin/env python
"""
Test script: run pipeline on 10 random articles only and generate PDF report.
Usage: python test_10_random.py
"""
import os
import sys
import django
from datetime import datetime
import random
from pathlib import Path

# Setup Django environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engine'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'engine.settings.development')
django.setup()

from articles.models import Article
from intelligence.tasks import extract_signals_for_article
from reports.tasks import generate_report
from pipeline.models import ProcessingRun
from celery import group
from django.utils import timezone

def run_test_10_random():
    """Run extraction + report on 10 random articles with chunks."""
    
    print("Test pipeline: 10 random articles -> signals -> PDF")
    
    # Create a processing run for this test
    run = ProcessingRun.objects.create(
        run_type=ProcessingRun.RUN_TYPE_FULL,
        status=ProcessingRun.RUN_STATUS_RUNNING,
        started_at=timezone.now(),
        progress_phase="selection",
        progress_total=10,
        progress_current=0,
    )
    
    try:
        # Get articles that have chunks or can be chunked
        articles = list(Article.objects.filter(
            processing_status__in=[Article.STATUS_CHUNKED, Article.STATUS_PENDING]
        ).order_by('?')[:10])  # Random 10
        
        if len(articles) < 10:
            # Fallback: include already extracted articles and reset them
            extracted = list(Article.objects.filter(
                processing_status=Article.STATUS_EXTRACTED,
                chunks__isnull=False
            ).distinct().order_by('?')[:10-len(articles)])
            articles.extend(extracted)
            
            # Reset extracted articles to chunked so we can re-extract
            if extracted:
                from intelligence.models import Signal
                Signal.objects.filter(article_id__in=[a.id for a in extracted]).delete()
                Article.objects.filter(id__in=[a.id for a in extracted]).update(
                    processing_status=Article.STATUS_CHUNKED
                )
        
        actual_count = len(articles)
        print(f"📋 Selected {actual_count} random articles")
        
        if actual_count == 0:
            print("❌ No articles with chunks found")
            run.status = ProcessingRun.RUN_STATUS_FAILED
            run.error_log.append("No articles with chunks available")
            run.save()
            return
        
        # Chunk pending articles if any
        pending = [a for a in articles if a.processing_status == Article.STATUS_PENDING]
        if pending:
            print(f"🧩 Chunking {len(pending)} pending articles...")
            from articles.tasks import chunk_article
            chunk_job = group(chunk_article.s(a.id) for a in pending)
            chunk_result = chunk_job.apply_async()
            chunk_result.get(timeout=300)  # 5 min timeout
            print("✅ Chunking complete")
        
        # Extract signals from all 10 articles
        print("🔍 Extracting signals from 10 articles...")
        run.progress_phase = "extraction"
        run.progress_total = actual_count
        run.progress_current = 0
        run.save(update_fields=["progress_phase", "progress_total", "progress_current"])
        
        extract_job = group(
            extract_signals_for_article.s(a.id, run.id) for a in articles
        )
        extract_result = extract_job.apply_async()
        extract_result.get(timeout=3600)  # 1 hour timeout
        
        # Count extracted signals
        run.refresh_from_db()
        total_signals = run.signals.count()
        print(f"✅ Extracted {total_signals} signals from {actual_count} articles")
        
        # Generate report for current week
        print("📊 Generating weekly report...")
        run.progress_phase = "report"
        run.save(update_fields=["progress_phase"])
        
        report_result = generate_report(processing_run_id=run.id)
        report_id = report_result['report_id']
        
        print(f"✅ Report generated: ID {report_id}")
        
        # Finalize run
        run.status = ProcessingRun.RUN_STATUS_COMPLETED
        run.progress_phase = "completed"
        run.progress_current = actual_count
        run.completed_at = timezone.now()
        run.config["report_id"] = report_id
        run.save()
        
        # Download and save PDFs (EN + FR) to project folder "reports_pdf"
        print("Saving PDFs to disk...")
        from reports.models import WeeklyReport
        report = WeeklyReport.objects.get(pk=report_id)

        pdf_dir = Path(__file__).parent / "reports_pdf"
        pdf_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for lang in ("en", "fr"):
            pdf_buffer = report.generate_pdf(lang=lang)
            filename = f"test_10_random_report_{timestamp}_{lang}.pdf"
            filepath = pdf_dir / filename
            with open(filepath, 'wb') as f:
                f.write(pdf_buffer.getvalue())
            print(f"  -> {lang.upper()}: {filepath.resolve()}")

        print("")
        print("SUCCESS! Both PDFs generated.")
        print("Folder:  " + str(pdf_dir.resolve()))
        print("Summary: " + str(actual_count) + " articles -> " + str(total_signals) + " signals")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        run.status = ProcessingRun.RUN_STATUS_FAILED
        run.error_log.append(str(e))
        run.completed_at = timezone.now()
        run.save()

if __name__ == '__main__':
    run_test_10_random()
