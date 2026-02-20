#!/usr/bin/env python
"""
Test script for duplicate article removal functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'engine.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from articles.models import Article

def test_duplicate_removal():
    """Test the duplicate removal functionality"""
    print("🧪 Testing duplicate article removal...")
    
    # Get current article count
    total_before = Article.objects.count()
    print(f"📚 Total articles before cleanup: {total_before}")
    
    if total_before == 0:
        print("⚠️  No articles found. Creating test articles...")
        
        # Create some test articles with similar titles
        test_articles = [
            {
                'title': 'Breaking News: New Technology Trends in 2024',
                'url': 'https://example.com/news1',
                'raw_text': 'Article content about technology trends in 2024...',
                'word_count': 150
            },
            {
                'title': 'Breaking News: New Technology Trends in 2024',
                'url': 'https://example.com/news2', 
                'raw_text': 'Similar article content about technology trends in 2024 with more details...',
                'word_count': 200
            },
            {
                'title': 'Technology Trends 2024 - Breaking News Update',
                'url': 'https://example.com/news3',
                'raw_text': 'Another article about technology trends but slightly different title...',
                'word_count': 180
            },
            {
                'title': 'Completely Different Article About Cooking',
                'url': 'https://example.com/cooking',
                'raw_text': 'This article is about cooking recipes and techniques...',
                'word_count': 120
            }
        ]
        
        # Create test articles
        for article_data in test_articles:
            Article.objects.create(**article_data)
        
        total_after_creation = Article.objects.count()
        print(f"✅ Created {total_after_creation} test articles")
    
    # Test 1: Find duplicates with high threshold
    print("\n🔍 Test 1: Finding duplicates with high threshold (0.95)")
    duplicates_high = Article.find_duplicates_by_title(
        'Breaking News: New Technology Trends in 2024',
        threshold=0.95
    )
    print(f"   Found {len(duplicates_high)} duplicates with 95% threshold")
    
    # Test 2: Find duplicates with medium threshold  
    print("\n🔍 Test 2: Finding duplicates with medium threshold (0.85)")
    duplicates_medium = Article.find_duplicates_by_title(
        'Breaking News: New Technology Trends in 2024',
        threshold=0.85
    )
    print(f"   Found {len(duplicates_medium)} duplicates with 85% threshold")
    
    # Test 3: Find duplicates with low threshold
    print("\n🔍 Test 3: Finding duplicates with low threshold (0.70)")
    duplicates_low = Article.find_duplicates_by_title(
        'Breaking News: New Technology Trends in 2024',
        threshold=0.70
    )
    print(f"   Found {len(duplicates_low)} duplicates with 70% threshold")
    
    # Test 4: Dry run removal
    print("\n🏃 Test 4: Dry run removal (threshold 0.85)")
    stats_dry = Article.remove_duplicates_by_title(
        threshold=0.85,
        keep_newest=True
    )
    print(f"   Would remove {stats_dry['articles_removed']} articles in {stats_dry['groups_found']} groups")
    
    # Show final state
    total_final = Article.objects.count()
    print(f"\n📊 Final article count: {total_final}")
    
    # Show remaining articles
    print("\n📝 Remaining articles:")
    for article in Article.objects.all():
        print(f"   - {article.title[:60]}... (ID: {article.pk})")
    
    print("\n✅ Duplicate removal test completed successfully!")
    print("\n📋 Usage Instructions:")
    print("   1. Automatic: Duplicates are removed after each scraping run")
    print("   2. Manual: python manage.py remove_duplicates --threshold 0.85")
    print("   3. Dry run: python manage.py remove_duplicates --dry-run")
    print("   4. Keep oldest: python manage.py remove_duplicates --keep-oldest")

if __name__ == "__main__":
    test_duplicate_removal()
