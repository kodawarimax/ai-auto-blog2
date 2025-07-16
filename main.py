"""
完全自動AI投稿システム - メインプログラム
朝7:30と夜7:30に自動でブログ記事を生成・投稿する
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import time

# プロジェクトルートをPythonパスに追加
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# 環境変数を読み込む（APIキーなどの秘密情報）
load_dotenv()

# 自作モジュールをインポート
from database import DatabaseManager
from auto_poster import AutoPoster

# 外部ライブラリのインポート
try:
    import google.generativeai as genai
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"❌ 必要なライブラリがインストールされていません: {e}")
    sys.exit(1)


class SimpleNewsCollector:
    """シンプルなニュース収集クラス"""
    
    def __init__(self):
        self.sources = [
            {
                'name': 'ITmedia AI',
                'url': 'https://www.itmedia.co.jp/news/subtop/aiplus/',
                'selector': 'article'
            },
            {
                'name': 'TechCrunch Japan',
                'url': 'https://jp.techcrunch.com/category/artificial-intelligence/',
                'selector': 'article'
            }
        ]
    
    def get_ai_news(self, limit=3):
        """AI関連のニュースを収集"""
        news_list = []
        
        # フォールバック用のニュース（接続エラー時に使用）
        fallback_news = [
            {
                'title': 'AI技術の最新動向',
                'summary': 'AI技術が私たちの生活を変えています。最新の研究により、AIはますます人間に近い判断ができるようになっています。',
                'url': 'https://example.com/ai-news-1',
                'source': 'fallback'
            },
            {
                'title': '生成AIの活用事例',
                'summary': '企業での生成AI活用が加速しています。業務効率化や新サービス開発に大きく貢献しています。',
                'url': 'https://example.com/ai-news-2',
                'source': 'fallback'
            },
            {
                'title': 'AIと教育の未来',
                'summary': 'AIを活用した個別最適化学習が注目されています。一人ひとりに合わせた学習プログラムが可能になります。',
                'url': 'https://example.com/ai-news-3',
                'source': 'fallback'
            }
        ]
        
        try:
            # 実際のニュース収集を試みる
            for source in self.sources[:1]:  # まず1つのソースから取得
                try:
                    response = requests.get(source['url'], timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # タイトルを含む要素を探す
                        articles = soup.find_all(['h2', 'h3', 'article'], limit=limit)
                        
                        for article in articles:
                            title_text = article.get_text(strip=True)[:100]
                            if title_text and len(title_text) > 10:
                                news_list.append({
                                    'title': title_text,
                                    'summary': f'{title_text} についての最新情報です。',
                                    'url': source['url'],
                                    'source': source['name']
                                })
                        
                        if len(news_list) >= limit:
                            break
                            
                except Exception as e:
                    print(f"⚠️ {source['name']}からのニュース取得に失敗: {e}")
            
            # ニュースが取得できなかった場合はフォールバックを使用
            if not news_list:
                print("⚠️ ニュース取得に失敗。フォールバックニュースを使用します。")
                news_list = fallback_news[:limit]
            
            return news_list[:limit]
            
        except Exception as e:
            print(f"❌ ニュース収集エラー: {e}")
            return fallback_news[:limit]


class GeminiWriter:
    """Gemini APIを使用した記事生成クラス"""
    
    def __init__(self, api_key):
        """Gemini APIを初期化"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def generate_blog_post(self, article, max_length=500):
        """ニュースを元にブログ記事を生成"""
        try:
            # 現在の時間帯を判定（朝か夜か）
            current_hour = datetime.now().hour
            time_context = "朝" if 5 <= current_hour < 12 else "夜"
            
            # プロンプトを作成（高校生向けの親しみやすい文章）
            prompt = f"""
以下のニュースを元に、高校生向けのブログ記事を{max_length}文字以内で書いてください。

ニュースタイトル: {article['title']}
ニュース概要: {article['summary']}

要件:
1. {time_context}の投稿として自然な挨拶から始める
2. 難しい専門用語は避け、わかりやすい言葉で説明
3. 具体例や身近な例えを使う
4. 読者が興味を持てるような問いかけを含める
5. ポジティブで前向きな内容にする
6. 最後は読者への感謝や次回予告で締める

記事を書いてください:
"""
            
            # Gemini APIで記事を生成
            response = self.model.generate_content(prompt)
            content = response.text
            
            # 文字数制限を適用
            if len(content) > max_length:
                # 文の途中で切れないように調整
                content = content[:max_length-3]
                last_period = content.rfind('。')
                if last_period > max_length * 0.8:
                    content = content[:last_period+1]
                else:
                    content = content + '...'
            
            # ハッシュタグを生成
            hashtags = self._generate_hashtags(article['title'])
            
            return {
                'title': self._generate_title(article['title']),
                'content': content,
                'hashtags': hashtags,
                'source_url': article['url'],
                'generated_at': datetime.now().isoformat(),
            }
            
        except Exception as e:
            print(f"❌ 記事生成エラー: {e}")
            # エラー時のフォールバック
            return self._create_fallback_post(article, max_length)
    
    def _generate_title(self, original_title):
        """ブログ用のタイトルを生成（50文字以内）"""
        # 絵文字を追加して親しみやすくする
        emojis = ['🤖', '✨', '🚀', '💡', '🌟', '📱', '🔮', '🎯']
        import random
        emoji = random.choice(emojis)
        
        # タイトルを短縮
        if len(original_title) > 45:
            title = original_title[:42] + '...'
        else:
            title = original_title
        
        return f"{emoji} {title}"
    
    def _generate_hashtags(self, title):
        """記事に合ったハッシュタグを生成"""
        base_tags = ['#AI', '#人工知能', '#テクノロジー', '#イノベーション']
        
        # タイトルに含まれるキーワードでタグを追加
        if '生成AI' in title or 'ChatGPT' in title:
            base_tags.append('#生成AI')
        if '教育' in title:
            base_tags.append('#EdTech')
        if 'ビジネス' in title or '企業' in title:
            base_tags.append('#DX')
        
        return ' '.join(base_tags[:5])  # 最大5個まで
    
    def _create_fallback_post(self, article, max_length):
        """エラー時のフォールバック記事"""
        current_hour = datetime.now().hour
        greeting = "おはようございます！" if 5 <= current_hour < 12 else "こんばんは！"
        
        content = f"""
{greeting}

今日は「{article['title']}」についてお話しします。

{article['summary']}

AI技術の進歩は本当に速いですね。私たちの生活がどんどん便利になっていくのを実感します。

皆さんはAIをどのように活用していますか？ぜひ教えてください！

今日も読んでいただきありがとうございました。次回もお楽しみに！
"""
        
        if len(content) > max_length:
            content = content[:max_length-3] + '...'
        
        return {
            'title': self._generate_title(article['title']),
            'content': content.strip(),
            'hashtags': '#AI #人工知能 #テクノロジー',
            'source_url': article['url'],
            'generated_at': datetime.now().isoformat(),
        }


def run_auto_post():
    """自動投稿を実行するメイン関数"""
    print("=" * 50)
    print(f"🚀 完全自動AI投稿システム起動")
    print(f"📅 実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 環境変数を取得
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    blog_url = os.getenv('BLOG_URL')
    blog_username = os.getenv('BLOG_USERNAME')
    blog_password = os.getenv('BLOG_PASSWORD')
    max_content_length = int(os.getenv('MAX_CONTENT_LENGTH', '500'))
    
    # 必須設定の確認
    if not all([gemini_api_key, supabase_url, supabase_key, blog_url, blog_username, blog_password]):
        print("❌ 環境変数が設定されていません")
        print("必要な環境変数:")
        print("- GEMINI_API_KEY")
        print("- SUPABASE_URL")
        print("- SUPABASE_KEY")
        print("- BLOG_URL")
        print("- BLOG_USERNAME")
        print("- BLOG_PASSWORD")
        return False
    
    try:
        # 各コンポーネントを初期化
        print("\n📚 コンポーネントを初期化中...")
        db = DatabaseManager(supabase_url, supabase_key)
        news_collector = SimpleNewsCollector()
        writer = GeminiWriter(gemini_api_key)
        poster = AutoPoster(blog_url, blog_username, blog_password)
        
        # ニュースを収集
        print("\n📰 AI関連ニュースを収集中...")
        news_articles = news_collector.get_ai_news(limit=1)  # 1記事のみ生成
        
        if not news_articles:
            print("❌ ニュースが取得できませんでした")
            return False
        
        print(f"✅ {len(news_articles)}件のニュースを取得")
        
        # 最初のニュースを選択
        selected_article = news_articles[0]
        print(f"\n📝 選択された記事: {selected_article['title']}")
        
        # データベースに保存
        db.save_news_article(selected_article)
        
        # ブログ記事を生成
        print("\n✍️ AI記事を生成中...")
        blog_post = writer.generate_blog_post(selected_article, max_content_length)
        
        if not blog_post:
            print("❌ 記事の生成に失敗しました")
            return False
        
        print(f"✅ 記事生成完了: {blog_post['title']}")
        print(f"   文字数: {len(blog_post['content'])}文字")
        
        # 生成記事をデータベースに保存
        post_id = db.save_generated_post(blog_post)
        
        # ブログに投稿
        print("\n📤 ブログに投稿中...")
        if poster.post_article(blog_post):
            print("✅ 投稿成功！")
            
            # 投稿確認
            time.sleep(2)  # 少し待機
            post_url = poster.verify_post(blog_post)
            
            if post_url:
                print(f"🔗 投稿URL: {post_url}")
                db.update_post_status(post_id, 'published', post_url)
            else:
                db.update_post_status(post_id, 'published')
            
            # 成功ログを記録
            db.save_system_log('INFO', '自動投稿成功', {
                'title': blog_post['title'],
                'url': post_url
            })
            
            return True
        else:
            print("❌ 投稿に失敗しました")
            db.update_post_status(post_id, 'failed')
            db.save_system_log('ERROR', '投稿失敗', {'title': blog_post['title']})
            return False
            
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        if 'db' in locals():
            db.save_system_log('ERROR', 'システムエラー', {'error': str(e)})
        return False


def show_dashboard():
    """システムダッシュボードを表示"""
    print("\n" + "=" * 50)
    print("📊 AI自動投稿システム - ダッシュボード")
    print("=" * 50)
    
    # 環境変数を取得
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not all([supabase_url, supabase_key]):
        print("❌ データベース設定が不完全です")
        return
    
    try:
        db = DatabaseManager(supabase_url, supabase_key)
        
        # システム統計を取得
        stats = db.get_system_stats()
        
        print(f"\n📈 システム統計:")
        print(f"   総ニュース記事数: {stats.get('total_articles', 0)}件")
        print(f"   総生成記事数: {stats.get('total_posts', 0)}件")
        print(f"   公開済み記事数: {stats.get('published_posts', 0)}件")
        print(f"   本日の投稿数: {stats.get('today_posts', 0)}件")
        print(f"   成功率: {stats.get('success_rate', 0)}%")
        
        # 最近の投稿を表示
        recent_posts = db.get_recent_posts(limit=5)
        
        if recent_posts:
            print(f"\n📝 最近の投稿:")
            for post in recent_posts:
                status_emoji = '✅' if post['status'] == 'published' else '⏳'
                print(f"   {status_emoji} {post['title'][:40]}... ({post['status']})")
                print(f"      生成日時: {post['generated_at'][:19]}")
        
        # 未投稿記事の確認
        unpublished = db.get_unpublished_posts()
        if unpublished:
            print(f"\n⏳ 未投稿記事: {len(unpublished)}件")
        
        print("\n✅ ダッシュボード表示完了")
        
    except Exception as e:
        print(f"❌ ダッシュボードエラー: {e}")


def main():
    """メインエントリーポイント"""
    # コマンドライン引数を確認
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'auto':
            # 自動投稿を実行
            success = run_auto_post()
            sys.exit(0 if success else 1)
            
        elif command == 'dashboard':
            # ダッシュボードを表示
            show_dashboard()
            sys.exit(0)
            
        elif command == 'test':
            # テストモード
            print("🧪 テストモード")
            print("環境変数チェック:")
            required_vars = ['GEMINI_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY', 
                           'BLOG_URL', 'BLOG_USERNAME', 'BLOG_PASSWORD']
            for var in required_vars:
                value = os.getenv(var)
                status = '✅' if value else '❌'
                masked_value = '***' if value else 'Not Set'
                print(f"  {status} {var}: {masked_value}")
            sys.exit(0)
            
        else:
            print(f"❌ 不明なコマンド: {command}")
            print("使用方法:")
            print("  python main.py auto      - 自動投稿を実行")
            print("  python main.py dashboard - ダッシュボードを表示")
            print("  python main.py test      - 設定をテスト")
            sys.exit(1)
    
    else:
        # 引数なしの場合は使用方法を表示
        print("完全自動AI投稿システム")
        print("使用方法:")
        print("  python main.py auto      - 自動投稿を実行")
        print("  python main.py dashboard - ダッシュボードを表示")
        print("  python main.py test      - 設定をテスト")
        sys.exit(0)


if __name__ == "__main__":
    main()
