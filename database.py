"""
完全自動AI投稿システム - Supabaseデータベース管理
"""
from supabase import create_client, Client
import os
from datetime import datetime
from typing import Dict, List, Optional
import json

class DatabaseManager:
    """Supabaseデータベース管理クラス"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Supabaseクライアントを初期化"""
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """必要なテーブルが存在することを確認"""
        # テーブル作成はSupabase管理画面で事前に行う
        # または初回実行時にSQLで作成
        pass
    
    def save_news_article(self, article: Dict) -> bool:
        """ニュース記事をデータベースに保存"""
        try:
            data = {
                'title': article.get('title', ''),
                'url': article.get('url', ''),
                'summary': article.get('summary', ''),
                'source': article.get('source', ''),
                'published_at': article.get('published', datetime.now().isoformat()),
                'created_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table('news_articles').insert(data).execute()
            return len(result.data) > 0
            
        except Exception as e:
            print(f"ニュース保存エラー: {e}")
            return False
    
    def save_generated_post(self, post: Dict) -> bool:
        """生成された投稿をデータベースに保存"""
        try:
            data = {
                'title': post.get('title', ''),
                'content': post.get('content', ''),
                'hashtags': post.get('hashtags', ''),
                'source_url': post.get('source_url', ''),
                'generated_at': post.get('generated_at', datetime.now().isoformat()),
                'status': 'generated'
            }
            
            result = self.supabase.table('generated_posts').insert(data).execute()
            if len(result.data) > 0:
                return result.data[0]['id']
            return False
            
        except Exception as e:
            print(f"投稿保存エラー: {e}")
            return False
    
    def update_post_status(self, post_id: int, status: str, blog_url: str = None) -> bool:
        """投稿ステータスを更新"""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now().isoformat()
            }
            
            if blog_url:
                update_data['blog_url'] = blog_url
            
            if status == 'published':
                update_data['published_at'] = datetime.now().isoformat()
            
            result = self.supabase.table('generated_posts').update(update_data).eq('id', post_id).execute()
            return len(result.data) > 0
            
        except Exception as e:
            print(f"ステータス更新エラー: {e}")
            return False
    
    def get_recent_news(self, limit: int = 10) -> List[Dict]:
        """最近のニュース記事を取得"""
        try:
            result = self.supabase.table('news_articles').select('*').order('created_at', desc=True).limit(limit).execute()
            return result.data
        except Exception as e:
            print(f"ニュース取得エラー: {e}")
            return []
    
    def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """最近の生成投稿を取得"""
        try:
            result = self.supabase.table('generated_posts').select('*').order('generated_at', desc=True).limit(limit).execute()
            return result.data
        except Exception as e:
            print(f"投稿取得エラー: {e}")
            return []
    
    def get_unpublished_posts(self) -> List[Dict]:
        """未投稿の記事を取得"""
        try:
            result = self.supabase.table('generated_posts').select('*').eq('status', 'generated').execute()
            return result.data
        except Exception as e:
            print(f"未投稿記事取得エラー: {e}")
            return []
    
    def save_system_log(self, level: str, message: str, details: Dict = None) -> bool:
        """システムログを保存"""
        try:
            data = {
                'level': level,
                'message': message,
                'details': json.dumps(details) if details else None,
                'created_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table('system_logs').insert(data).execute()
            return len(result.data) > 0
            
        except Exception as e:
            print(f"ログ保存エラー: {e}")
            return False
    
    def get_system_stats(self) -> Dict:
        """システム統計を取得"""
        try:
            # 総記事数
            total_articles = self.supabase.table('news_articles').select('id', count='exact').execute()
            
            # 総投稿数
            total_posts = self.supabase.table('generated_posts').select('id', count='exact').execute()
            
            # 公開済み投稿数
            published_posts = self.supabase.table('generated_posts').select('id', count='exact').eq('status', 'published').execute()
            
            # 今日の投稿数
            today = datetime.now().date().isoformat()
            today_posts = self.supabase.table('generated_posts').select('id', count='exact').gte('published_at', today).execute()
            
            return {
                'total_articles': total_articles.count,
                'total_posts': total_posts.count,
                'published_posts': published_posts.count,
                'today_posts': today_posts.count,
                'success_rate': round((published_posts.count / max(total_posts.count, 1)) * 100, 2)
            }
            
        except Exception as e:
            print(f"統計取得エラー: {e}")
            return {}

# データベーススキーマ（Supabase管理画面で作成）
DATABASE_SCHEMA = """
-- ニュース記事テーブル
CREATE TABLE news_articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    source TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 生成投稿テーブル
CREATE TABLE generated_posts (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    hashtags TEXT,
    source_url TEXT,
    generated_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW(),
    status TEXT DEFAULT 'generated',
    blog_url TEXT
);

-- システムログテーブル
CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- インデックス作成
CREATE INDEX idx_news_articles_created_at ON news_articles(created_at);
CREATE INDEX idx_generated_posts_status ON generated_posts(status);
CREATE INDEX idx_generated_posts_published_at ON generated_posts(published_at);
CREATE INDEX idx_system_logs_level ON system_logs(level);
"""

if __name__ == "__main__":
    # テスト実行
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase設定が不完全です")
        exit(1)
    
    db = DatabaseManager(supabase_url, supabase_key)
    
    # テストデータ
    test_article = {
        'title': 'テストニュース',
        'url': 'https://example.com/test',
        'summary': 'これはテスト用のニュースです。',
        'source': 'test'
    }
    
    # ニュース保存テスト
    if db.save_news_article(test_article):
        print("✅ ニュース保存テスト成功")
    else:
        print("❌ ニュース保存テスト失敗")
    
    # 統計取得テスト
    stats = db.get_system_stats()
    print(f"📊 システム統計: {stats}")
    
    print("データベーススキーマ:")
    print(DATABASE_SCHEMA)

