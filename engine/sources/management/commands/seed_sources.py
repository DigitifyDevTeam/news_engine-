"""
Seed curated French digital/IT sources (Lyon-focused where relevant).
Idempotent: creates only if URL does not exist.
"""
from django.core.management.base import BaseCommand
from sources.models import Source, SOURCE_TYPE_WEB, SCRAPE_TRAFILATURA

DEFAULT_SOURCES = [
    {"name": "Maddyness (FR Tech)", "url": "https://www.maddyness.com/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "French Tech Lyon", "url": "https://www.frenchtech.lyon/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "Journal du Net", "url": "https://www.journaldunet.com/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "ZDNet France", "url": "https://www.zdnet.fr/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "Le Monde Informatique", "url": "https://www.lemondeinformatique.fr/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "Lyon Entreprises", "url": "https://www.lyon-entreprises.com/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "Usine Digitale", "url": "https://www.usine-digitale.fr/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "Gazette des communes", "url": "https://www.lagazettedescommunes.com/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "Village de la Justice", "url": "https://www.village-justice.com/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
    {"name": "Actu IA (France)", "url": "https://www.actuia.com/", "source_type": SOURCE_TYPE_WEB, "scrape_strategy": SCRAPE_TRAFILATURA},
]


class Command(BaseCommand):
    help = "Create default French digital/IT sources if they do not exist."

    def handle(self, *args, **options):
        created = 0
        for data in DEFAULT_SOURCES:
            _, was_created = Source.objects.get_or_create(
                url=data["url"],
                defaults={
                    "name": data["name"],
                    "source_type": data["source_type"],
                    "scrape_strategy": data["scrape_strategy"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created: {data['name']}"))
        self.stdout.write(self.style.SUCCESS(f"Done. Created {created} new sources."))
