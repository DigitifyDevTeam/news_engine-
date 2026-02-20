from django.core.management.base import BaseCommand
from articles.models import Article


class Command(BaseCommand):
    help = 'Remove duplicate articles based on title similarity'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.85,
            help='Similarity threshold for duplicate detection (0.0-1.0, default: 0.85)'
        )
        parser.add_argument(
            '--keep-newest',
            action='store_true',
            default=True,
            help='Keep newest article when duplicates found (default: True)'
        )
        parser.add_argument(
            '--keep-oldest',
            action='store_true',
            help='Keep oldest article when duplicates found'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be removed without actually removing'
        )
    
    def handle(self, *args, **options):
        threshold = options['threshold']
        keep_newest = options['keep_newest'] and not options['keep_oldest']
        dry_run = options['dry_run']
        
        self.stdout.write(
            f'🔍 Finding duplicate articles with threshold {threshold}...'
        )
        
        # Find duplicates
        duplicates_stats = Article.remove_duplicates_by_title(
            threshold=threshold,
            keep_newest=keep_newest
        )
        
        groups_found = duplicates_stats['groups_found']
        articles_removed = duplicates_stats['articles_removed']
        removed_ids = duplicates_stats['removed_ids']
        
        if dry_run:
            self.stdout.write(
                f'📊 DRY RUN - Would remove {articles_removed} articles '
                f'in {groups_found} duplicate groups'
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Removed {articles_removed} duplicate articles '
                    f'in {groups_found} groups (threshold: {threshold})'
                )
            )
            
            if removed_ids:
                self.stdout.write(
                    f'🗑️  Removed article IDs: {removed_ids}'
                )
        
        # Show remaining count
        total_articles = Article.objects.count()
        self.stdout.write(
            f'📚 Total articles remaining: {total_articles}'
        )
