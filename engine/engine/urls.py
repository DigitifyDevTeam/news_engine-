"""
URL configuration for engine project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

from engine import views as engine_views

urlpatterns = [
    path("admin/articles/custom/", engine_views.custom_article_admin, name="custom_article_admin"),
    path("admin/articles/article/", engine_views.redirect_article_admin),
    path("admin/", admin.site.urls),
    path("api/", include("engine.api_urls")),
    path("export.txt", engine_views.export_articles_txt),
    path("add-source/", engine_views.add_source, name="add_source"),
    path("scrape/<int:source_id>/", engine_views.scrape_source_page, name="scrape_source"),
    path("signals/", engine_views.signals_page, name="signals_page"),
    path("signals/save/", engine_views.save_prompt_template, name="save_prompt_template"),
     path("signals/manual/save/", engine_views.save_manual_signal, name="save_manual_signal"),
     path("signals/manual/<int:signal_id>/delete/", engine_views.delete_manual_signal, name="delete_manual_signal"),
     path("signals/notes/save/", engine_views.save_simple_note, name="save_simple_note"),
     path("signals/notes/<int:note_id>/delete/", engine_views.delete_simple_note, name="delete_simple_note"),
    path("reports/<int:report_id>/pdf/", engine_views.download_report_pdf, name="download_report_pdf"),
    path("chat/", engine_views.chat_llm, name="chat_llm"),
    path("favicon.ico", engine_views.favicon),
    path("sources/", engine_views.sources_page, name="sources_page"),
    path("", engine_views.home_page, name="home_page"),
]
