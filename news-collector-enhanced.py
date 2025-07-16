"""
完全自動AI投稿システム - 強化版ニュース収集モジュール
複数のソースから確実にAI関連ニュースを収集
"""
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timedelta
import time
import hashlib
from typing import List, Dict, Optional
import re


class EnhancedNewsCollector:
    """強化版ニュース収集クラス"""
    
    def __init__(self):
        """各種ニュースソースを設定"""
        # RSSフィード（最も確実な方法）
        self.rss_feeds = [
            {
                'name': 'Google News - AI',
                'url': 'https://news.google.com/rss/search?q=AI+人工知能&hl=ja&gl=JP&ceid=JP:ja',
                'type': 'rss'
            },
            {
                'name': 'ITmedia AI+',
                'url': 'https://rss.itmedia.co.jp/rss/2.0/aiplus.xml',
                'type': 'rss'
            },
            {
                'name': 'GIGAZINE',
                'url': 'https://gigazine.net/news/rss_2.0/',
                'type': 'rss',
                'filter': ['AI', '人工知能', 'ChatGPT', '機械学習']
            }
        ]
        
        # ウェブスクレイピング用のソース
        self.web_sources = [
            {
                'name': 'AI News Japan',
                'url': 'https://ledge.ai/categories/news/',
                'selector': {
                    'container': 'article',
                    'title': 'h2',
                    'link': 'a',
                    'summary': 'p'
                }
            },
            {
                'name': 'ASCII AI',
                'url': 'https://ascii.jp/ai/',
                'selector': {
                    'container': 'div.articleList',
                    'title': 'h3',
                    'link': 'a',
                    'summary': 'p'
                }
            }
        ]
        
        # ユーザーエージェント（ブラウザのふりをする）
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        
        # 収集したニュースを一時保存（重複防止用）
        self.collected_news = []
        self.seen_urls = set()
    
    def get_ai_news(self, limit: int = 5, hours_back: int = 48) -> List[Dict]:
        """
        AI関連のニュースを収集
        
        Args:
            limit: 取得する記事数
            hours_back: 何時間前までのニュースを取得するか
        
        Returns:
            ニュース記事のリスト
        """
        print(f"📡 {hours_back}時間以内のAIニュースを収集開始...")
        
        # 期限を設定
        time_limit = datetime.now() - timedelta(hours=hours_back)
        
        # 1. RSSフィードから収集（最も確実）
        self._collect_from_rss(time_limit)
        
        # 2. 不足分をウェブスクレイピングで補完
        if len(self.collected_news) < limit:
            self._collect_from_web()
        
        # 3. フォールバックニュースを準備
        if len(self.collected_news) < limit:
            self._add_fallback_news()
        
        # 4. 重複を除去して最新順にソート
        unique_news = self._remove_duplicates()
        
        # 5. スコアリングして重要度順に並べ替え
        scored_news = self._score_and_sort(unique_news)
        
        # 6. 指定数だけ返す
        result = scored_news[:limit]
        
        print(f"✅ {len(result)}件のニュースを収集完了")
        return result
    
    def _collect_from_rss(self, time_limit: datetime):
        """RSSフィードからニュースを収集"""
        for feed_info in self.rss_feeds:
            try:
                print(f"  📻 {feed_info['name']}から収集中...")
                
                # RSSフィードを取得
                feed = feedparser.parse(feed_info['url'])
                
                if not feed.entries:
                    continue
                
                # 各記事を処理
                for entry in feed.entries[:10]:  # 最新10件まで
                    # 公開日時を確認
                    published = self._parse_date(entry.get('published', ''))
                    if published and published < time_limit:
                        continue
                    
                    # フィルターがある場合は適用
                    if 'filter' in feed_info:
                        title = entry.get('title', '')
                        if not any(keyword in title for keyword in feed_info['filter']):
                            continue
                    
                    # ニュース記事を作成
                    article = {
                        'title': self._clean_text(entry.get('title', '')),
                        'url': entry.get('link', ''),
                        'summary': self._clean_text(entry.get('summary', '')[:200]),
                        'source': feed_info['name'],
                        'published': published.isoformat() if published else datetime.now().isoformat(),
                        'score': 0  # 後でスコアリング
                    }
                    
                    # URLの重複チェック
                    if article['url'] and article['url'] not in self.seen_urls:
                        self.collected_news.append(article)
                        self.seen_urls.add(article['url'])
                
                time.sleep(0.5)  # サーバーに優しく
                
            except Exception as e:
                print(f"    ⚠️ {feed_info['name']}のRSS取得エラー: {e}")
    
    def _collect_from_web(self):
        """ウェブサイトから直接スクレイピング"""
        for source in self.web_sources:
            try:
                print(f"  🌐 {source['name']}から収集中...")
                
                # ウェブページを取得
                response = requests.get(source['url'], headers=self.headers, timeout=10)
                if response.status_code != 200:
                    continue
                
                # BeautifulSoupで解析
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # セレクターに基づいて記事を抽出
                selector = source['selector']
                containers = soup.select(selector['container'])[:5]  # 最新5件
                
                for container in containers:
                    # タイトルを取得
                    title_elem = container.select_one(selector['title'])
                    if not title_elem:
                        continue
                    
                    title = self._clean_text(title_elem.get_text())
                    
                    # AI関連の記事かチェック
                    if not self._is_ai_related(title):
                        continue
                    
                    # リンクを取得
                    link_elem = container.select_one(selector['link'])
                    url = link_elem.get('href', '') if link_elem else ''
                    if url and not url.startswith('http'):
                        url = source['url'].split('/')[0] + '//' + source['url'].split('/')[2] + url
                    
                    # 概要を取得
                    summary_elem = container.select_one(selector.get('summary', 'p'))
                    summary = self._clean_text(summary_elem.get_text()[:200]) if summary_elem else ''
                    
                    # ニュース記事を作成
                    article = {
                        'title': title,
                        'url': url,
                        'summary': summary or f'{title}に関する最新情報です。',
                        'source': source['name'],
                        'published': datetime.now().isoformat(),
                        'score': 0
                    }
                    
                    # URLの重複チェック
                    if url and url not in self.seen_urls:
                        self.collected_news.append(article)
                        self.seen_urls.add(url)
                
                time.sleep(1)  # サーバーに優しく
                
            except Exception as e:
                print(f"    ⚠️ {source['name']}のスクレイピングエラー: {e}")
    
    def _add_fallback_news(self):
        """フォールバック用のニュースを追加"""
        fallback_news = [
            {
                'title': '【最新】生成AIが変える私たちの未来',
                'summary': 'ChatGPTやGeminiなどの生成AIが、教育やビジネスの現場で急速に普及しています。AIとの共存について考える時が来ています。',
                'url': 'https://example.com/ai-future',
                'source': 'AI Times (Fallback)',
                'published': datetime.now().isoformat(),
                'score': 0
            },
            {
                'title': 'AI技術の倫理的な課題と解決策',
                'summary': 'AI技術の発展に伴い、プライバシーや著作権などの倫理的な課題が浮上しています。適切なルール作りが求められています。',
                'url': 'https://example.com/ai-ethics',
                'source': 'Tech Ethics (Fallback)',
                'published': datetime.now().isoformat(),
                'score': 0
            },
            {
                'title': '日本企業のAI活用事例10選',
                'summary': '製造業からサービス業まで、様々な分野でAIが活用されています。成功事例から学ぶAI導入のポイントを紹介します。',
                'url': 'https://example.com/ai-cases',
                'source': 'Business AI (Fallback)',
                'published': datetime.now().isoformat(),
                'score': 0
            }
        ]
        
        for article in fallback_news:
            if article['url'] not in self.seen_urls:
                self.collected_news.append(article)
                self.seen_urls.add(article['url'])
    
    def _is_ai_related(self, text: str) -> bool:
        """テキストがAI関連かどうかを判定"""
        ai_keywords = [
            'AI', '人工知能', 'ChatGPT', 'GPT', 'Gemini', 'Claude',
            '機械学習', 'ディープラーニング', '深層学習', 'ニューラルネット',
            '生成AI', 'LLM', '大規模言語モデル', '画像生成', '音声認識',
            'OpenAI', 'Google AI', 'Microsoft AI', 'Meta AI',
            'Stable Diffusion', 'DALL-E', 'Midjourney',
            'AIアシスタント', 'チャットボット', '自動化', 'ロボット'
        ]
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in ai_keywords)
    
    def _clean_text(self, text: str) -> str:
        """テキストをクリーンアップ"""
        # HTMLタグを除去
        text = re.sub(r'<[^>]+>', '', text)
        # 連続する空白を1つに
        text = re.sub(r'\s+', ' ', text)
        # 前後の空白を除去
        text = text.strip()
        # 特殊文字を除去
        text = text.replace('\u3000', ' ')  # 全角スペース
        text = text.replace('\xa0', ' ')    # ノーブレークスペース
        
        return text
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """日付文字列をdatetimeオブジェクトに変換"""
        if not date_str:
            return None
        
        # 一般的な日付フォーマットを試す
        date_formats = [
            '%a, %d %b %Y %H:%M:%S %Z',  # RFC822
            '%Y-%m-%dT%H:%M:%S%z',       # ISO8601
            '%Y-%m-%d %H:%M:%S',         # 一般的な形式
            '%Y/%m/%d %H:%M:%S',         # 日本式
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.replace('GMT', '+0000'), fmt)
            except:
                continue
        
        return None
    
    def _remove_duplicates(self) -> List[Dict]:
        """重複記事を除去"""
        unique_news = []
        seen_titles = set()
        
        for article in self.collected_news:
            # タイトルの類似性でも重複チェック
            title_hash = hashlib.md5(article['title'][:30].encode()).hexdigest()
            
            if title_hash not in seen_titles:
                unique_news.append(article)
                seen_titles.add(title_hash)
        
        return unique_news
    
    def _score_and_sort(self, news_list: List[Dict]) -> List[Dict]:
        """ニュースの重要度をスコアリングして並べ替え"""
        for article in news_list:
            score = 0
            
            # タイトルに重要キーワードが含まれているか
            important_keywords = ['ChatGPT', 'GPT-4', 'Gemini', 'Claude', '最新', '発表', '新機能', '革新']
            for keyword in important_keywords:
                if keyword in article['title']:
                    score += 10
            
            # 信頼できるソースか
            trusted_sources = ['Google News', 'ITmedia', 'ASCII']
            if any(source in article['source'] for source in trusted_sources):
                score += 5
            
            # 概要の長さ（情報量）
            if len(article['summary']) > 100:
                score += 3
            
            # URLがあるか
            if article['url'] and article['url'].startswith('http'):
                score += 2
            
            article['score'] = score
        
        # スコアの高い順に並べ替え
        return sorted(news_list, key=lambda x: (x['score'], x['published']), reverse=True)


# requirements.txtに追加が必要な依存関係
REQUIREMENTS_UPDATE = """
# 既存の依存関係に加えて以下を追加:
feedparser==6.0.10  # RSS フィード解析用
"""
class SimpleNewsCollector(EnhancedNewsCollector):
    """後方互換性のためのラッパークラス"""
    
    def get_ai_news(self, limit: int = 3) -> List[Dict]:
        """シンプルなインターフェースを提供"""
        # 強化版の機能を使いつつ、シンプルなインターフェースを維持
        return super().get_ai_news(limit=limit, hours_back=48)


if __name__ == "__main__":
    # テスト実行
    print("🧪 ニュース収集モジュールのテスト")
    print("=" * 50)
    
    collector = EnhancedNewsCollector()
    news = collector.get_ai_news(limit=5)
    
    print(f"\n📰 収集したニュース: {len(news)}件")
    print("=" * 50)
    
    for i, article in enumerate(news, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   📍 ソース: {article['source']}")
        print(f"   🔗 URL: {article['url'][:50]}...")
        print(f"   📝 概要: {article['summary'][:100]}...")
        print(f"   ⭐ スコア: {article['score']}")
        print(f"   📅 日時: {article['published'][:19]}")
