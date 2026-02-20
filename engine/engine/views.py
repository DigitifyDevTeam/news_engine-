"""
Frontend views: dashboard home page, sources management, text export, and simple LLM chat.
"""
import json

from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from articles.models import Article
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.conf import settings

from sources.models import Source, SOURCE_TYPE_WEB, SCRAPE_TRAFILATURA
from articles.models import Article
from sources.services import ScrapingService
from core.exceptions import ScrapingError, LLMError


def custom_article_admin(request):
    """Custom article admin view to bypass Django admin template issues."""
    
    # Get search query
    search_query = request.GET.get('q', '')
    
    # Filter articles
    articles = Article.objects.all().order_by('-created_at')
    
    if search_query:
        articles = articles.filter(title__icontains=search_query)
    
    # Pagination
    paginator = Paginator(articles, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'articles': page_obj,
        'search_query': search_query,
        'total_count': articles.count(),
        'is_staff': request.user.is_staff if request.user.is_authenticated else False,
    }
    
    return render(request, 'admin/custom_article_list.html', context)


def redirect_article_admin(request):
    """Redirect from broken admin to custom admin."""
    from django.urls import reverse
    return redirect(reverse('custom_article_admin'))


@require_GET
def favicon(request):
    """Avoid 404 in logs when the browser requests /favicon.ico."""
    return HttpResponse(status=204)


@require_GET
def home_page(request):
    """
    Main dashboard: show high-level stats and quick links for the full process:
    sources -> scraping -> signals -> weekly reports.
    """
    from intelligence.models import Signal
    from reports.models import WeeklyReport
    from pipeline.models import ProcessingRun

    sources_count = Source.objects.count()
    articles_count = Article.objects.count()
    signals_count = Signal.objects.count()
    reports_count = WeeklyReport.objects.count()

    latest_runs = ProcessingRun.objects.order_by("-created_at")[:5]
    latest_reports = WeeklyReport.objects.order_by("-week_start")[:3]

    context = {
        "sources_count": sources_count,
        "articles_count": articles_count,
        "signals_count": signals_count,
        "reports_count": reports_count,
        "latest_runs": latest_runs,
        "latest_reports": latest_reports,
    }
    return render(request, "home.html", context)


@require_POST
def chat_llm(request):
    """
    Lightweight chatbot endpoint used on the home dashboard to verify that
    the local LLaMA 3.1 model is working correctly.
    """
    from intelligence.llm_client import LLMClient

    try:
        # Accept JSON body (preferred) or form-encoded fallback.
        if request.content_type == "application/json":
            payload = json.loads(request.body.decode("utf-8") or "{}")
            message = (payload.get("message") or "").strip()
        else:
            message = (request.POST.get("message") or "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Requête JSON invalide."}, status=400)

    if not message:
        return JsonResponse({"error": "Le message ne peut pas être vide."}, status=400)

    cfg = settings.LLM_CONFIG
    client = LLMClient(
        base_url=cfg["base_url"],
        default_model=cfg["default_model"],
        timeout=cfg.get("timeout", 120),
        max_retries=cfg.get("max_retries", 2),
    )

    system_prompt = (
        "Tu es le chatbot de test de News Engine. "
        "Réponds de façon concise en français, en te concentrant sur "
        "l'écosystème numérique (SaaS, agences, ESN, IT) et la région lyonnaise "
        "lorsque c'est pertinent. Ne génère pas de données personnelles."
    )

    try:
        reply = client.generate(system_prompt=system_prompt, user_prompt=message)
    except LLMError as e:
        return JsonResponse({"error": f"Erreur LLM: {e}"}, status=502)
    except Exception as e:  # Safety net: avoid leaking stack traces.
        return JsonResponse({"error": f"Erreur interne: {e}"}, status=500)

    return JsonResponse({"reply": reply})


@require_GET
def signals_page(request):
    """
    Signals workspace:
    - Manual: manage signals via Django admin.
    - Professional: define and save prompt templates for signal extraction.
    """
    from intelligence.models import PromptTemplate, Signal, SimpleNote, SIGNAL_CATEGORIES
    from articles.models import Article

    prompts = PromptTemplate.objects.order_by("name")
    manual_signals = (
        Signal.objects.filter(processing_run__isnull=True)
        .select_related("article")
        .order_by("-created_at")[:50]
    )
    simple_notes = SimpleNote.objects.order_by("-created_at")[:50]
    articles = Article.objects.order_by("-created_at")[:50]
    categories = SIGNAL_CATEGORIES
    context = {
        "prompts": prompts,
        "manual_signals": manual_signals,
        "simple_notes": simple_notes,
        "articles": articles,
        "categories": categories,
    }
    return render(request, "signals_manage.html", context)


@require_POST
def save_prompt_template(request):
    """Create or update a PromptTemplate from the professional signals form."""
    from intelligence.models import PromptTemplate

    name = (request.POST.get("name") or "").strip()
    purpose = (request.POST.get("purpose") or "").strip()
    body = (request.POST.get("body") or "").strip()
    if not name or not body:
        messages.error(request, "Le nom et le prompt sont obligatoires.")
        return redirect("signals_page")

    tmpl, created = PromptTemplate.objects.update_or_create(
        name=name,
        defaults={"purpose": purpose, "body": body},
    )
    msg = "Prompt créé." if created else "Prompt mis à jour."
    messages.success(request, msg)
    return redirect("signals_page")


@require_POST
def save_manual_signal(request):
    """Create or update a manual Signal (processing_run is left null)."""
    from intelligence.models import Signal

    signal_id = request.POST.get("signal_id")
    category = (request.POST.get("category") or "").strip()
    title = (request.POST.get("title") or "").strip()
    description = (request.POST.get("description") or "").strip()
    article_id = request.POST.get("article_id")
    relevance = request.POST.get("relevance_score") or "0.7"
    confidence = request.POST.get("confidence") or "0.7"
    entities_raw = (request.POST.get("entities") or "").strip()

    if not title or not description or not category or not article_id:
        messages.error(request, "Catégorie, article, titre et description sont obligatoires.")
        return redirect("signals_page")

    try:
        relevance_f = float(relevance)
        confidence_f = float(confidence)
    except ValueError:
        messages.error(request, "Les scores doivent être des nombres.")
        return redirect("signals_page")

    if entities_raw:
        entities = [e.strip() for e in entities_raw.split(",") if e.strip()]
    else:
        entities = []

    try:
        article = Article.objects.get(pk=article_id)
    except Article.DoesNotExist:
        messages.error(request, "Article introuvable.")
        return redirect("signals_page")

    data = {
        "article": article,
        "category": category,
        "title": title,
        "description": description,
        "relevance_score": max(0.0, min(1.0, relevance_f)),
        "confidence": max(0.0, min(1.0, confidence_f)),
        "entities": entities,
        "raw_llm_output": {},
        "processing_run": None,
    }

    if signal_id:
        try:
            sig = Signal.objects.get(pk=signal_id, processing_run__isnull=True)
        except Signal.DoesNotExist:
            messages.error(request, "Signal manuel introuvable.")
            return redirect("signals_page")
        for k, v in data.items():
            setattr(sig, k, v)
        sig.save()
        messages.success(request, "Signal mis à jour.")
    else:
        Signal.objects.create(**data)
        messages.success(request, "Signal créé.")

    return redirect("signals_page")


@require_POST
def delete_manual_signal(request, signal_id: int):
    """Delete a manual Signal (processing_run is null)."""
    from intelligence.models import Signal

    try:
        sig = Signal.objects.get(pk=signal_id, processing_run__isnull=True)
    except Signal.DoesNotExist:
        messages.error(request, "Signal manuel introuvable.")
        return redirect("signals_page")

    sig.delete()
    messages.success(request, "Signal supprimé.")
    return redirect("signals_page")


@require_POST
def save_simple_note(request):
    """Create or update a simple note without article association."""
    from intelligence.models import SimpleNote

    note_id = request.POST.get("note_id")
    content = (request.POST.get("content") or "").strip()

    if not content:
        messages.error(request, "Le contenu du signal est obligatoire.")
        return redirect("signals_page")

    # Derive a simple title from the first line / characters of the content
    first_line = content.splitlines()[0] if content else ""
    title = first_line[:512] or content[:512]

    data = {
        "title": title,
        "content": content,
        "category": "",
    }

    if note_id:
        try:
            note = SimpleNote.objects.get(pk=note_id)
        except SimpleNote.DoesNotExist:
            messages.error(request, "Note introuvable.")
            return redirect("signals_page")
        for k, v in data.items():
            setattr(note, k, v)
        note.save()
        messages.success(request, "Note mise à jour.")
    else:
        SimpleNote.objects.create(**data)
        messages.success(request, "Note créée.")

    return redirect("signals_page")


@require_POST
def delete_simple_note(request, note_id: int):
    """Delete a simple note."""
    from intelligence.models import SimpleNote

    try:
        note = SimpleNote.objects.get(pk=note_id)
    except SimpleNote.DoesNotExist:
        messages.error(request, "Note introuvable.")
        return redirect("signals_page")

    note.delete()
    messages.success(request, "Note supprimée.")
    return redirect("signals_page")


@ensure_csrf_cookie
@require_GET
def sources_page(request):
    """Render the sources UI: add URL, list sources, list articles, download .txt."""
    sources = Source.objects.all().order_by("name")
    articles = Article.objects.select_related("source").order_by("-created_at")[:200]
    return render(request, "sources_manage.html", {"sources": sources, "articles": articles})


@require_POST
def add_source(request):
    """Create a source from form POST (name, url). Redirects back to sources page."""
    name = (request.POST.get("name") or "").strip() or None
    url = (request.POST.get("url") or "").strip() or None
    if not url:
        messages.error(request, "URL is required.")
        return redirect("sources_page")
    if not name:
        name = url
    try:
        Source.objects.get_or_create(
            url=url,
            defaults={"name": name[:255], "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA, "is_active": True},
        )
        messages.success(request, f"Source added: {name}")
    except Exception as e:
        messages.error(request, str(e))
    return redirect("sources_page")


@require_POST
def scrape_source_page(request, source_id):
    """Run scrape for one source (form POST). No JavaScript required; avoids fetch timeouts."""
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        messages.error(request, "Source not found.")
        return redirect("sources_page")
    if not source.is_active:
        messages.warning(request, f"Source « {source.name} » is inactive.")
        return redirect("sources_page")
    try:
        service = ScrapingService()
        articles = service.scrape_source(source)
        if articles:
            messages.success(request, f"Scraped {len(articles)} article(s) from « {source.name} ».")
        else:
            messages.warning(
                request,
                f"No articles from « {source.name} ». The site may be unreachable (e.g. domain not found), "
                "returned no content, or the page structure changed. Check the URL or deactivate the source.",
            )
    except ScrapingError as e:
        messages.error(request, f"Scrape error: {e}")
    except Exception as e:
        messages.error(request, f"Scrape failed: {e}")
    return redirect("sources_page")


@require_GET
def export_articles_txt(request):
    """Export scraped articles as a single .txt file. Optional ?source_id=<id> to filter by source."""
    source_id = request.GET.get("source_id")
    if source_id:
        articles = Article.objects.filter(source_id=source_id).select_related("source").order_by("-created_at")
    else:
        articles = Article.objects.select_related("source").order_by("-created_at")

    lines = []
    for a in articles:
        lines.append(f"# {a.title}")
        lines.append(f"Source: {a.source.name} | URL: {a.url}")
        lines.append("")
        lines.append(a.raw_text or "(no content)")
        lines.append("")
        lines.append("-" * 60)
        lines.append("")

    content = "\n".join(lines)
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    filename = f"scraped_articles_{source_id or 'all'}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_GET
def download_report_pdf(request, report_id: int):
    """Download a weekly report as PDF. Filename includes today's date."""
    from datetime import date

    from reports.models import WeeklyReport

    try:
        report = WeeklyReport.objects.get(pk=report_id)
    except WeeklyReport.DoesNotExist:
        messages.error(request, "Rapport introuvable.")
        return redirect("home_page")

    try:
        lang = request.GET.get("lang", "en")
        if lang not in ("en", "fr"):
            lang = "en"
        pdf_buffer = report.generate_pdf(lang=lang)
        today = date.today().isoformat()
        week_range = f"{report.week_start}_{report.week_end}"
        filename = f"weekly_report_{today}_{week_range}_{lang}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(pdf_buffer.getvalue())

        return response
    except Exception as e:
        messages.error(request, f"Error generating PDF: {e}")
        return redirect("home_page")
