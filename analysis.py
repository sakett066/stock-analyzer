"""
Advanced Stock Market Analyzer with News Crux
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime, timedelta
import re

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

STOCKS = {
    'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM'],
    'Banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK'],
    'Conglomerate': ['RELIANCE', 'ITC', 'LT'],
    'FMCG': ['HINDUNILVR', 'NESTLEIND', 'DABUR', 'BRITANNIA'],
    'Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB'],
    'Consumer': ['TITAN', 'ASIANPAINT', 'MARUTI', 'BAJFINANCE', 'BAJAJFINSV'],
    'Energy': ['POWERGRID', 'NTPC', 'ADANIPORTS', 'ONGC'],
}

# ============================================
# NEWS FETCHER WITH CRUX
# ============================================
def fetch_news_crux(symbol):
    """Fetch news and create 3-point crux"""
    try:
        # Try multiple news sources
        news_items = []
        
        # Source 1: Google News
        try:
            url = f"https://news.google.com/rss/search?q={symbol}+share+stock+market&hl=en-IN&gl=IN&ceid=IN:en"
            response = requests.get(url, timeout=8)
            from xml.etree import ElementTree
            root = ElementTree.fromstring(response.content)
            
            for item in root.findall('.//item')[:15]:
                title = item.find('title').text if item.find('title') is not None else ""
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                source = item.find('source').text if item.find('source') is not None else "Unknown"
                
                # Clean title
                title = re.sub(r'[^\w\s\-.,%₹$]', '', title)
                title = title.replace(symbol, '').strip()
                
                if len(title) > 20:
                    news_items.append({
                        'title': title,
                        'source': source,
                        'date': pub_date
                    })
        except:
            pass
        
        # If no news, try Moneycontrol
        if not news_items:
            try:
                url = f"https://www.moneycontrol.com/news/business/stocks/?query={symbol}"
                response = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for item in soup.find_all(['h2', 'h3'], class_=re.compile('title|headline'))[:5]:
                    title = item.get_text().strip()
                    if len(title) > 20:
                        news_items.append({
                            'title': title,
                            'source': 'Moneycontrol',
                            'date': 'Today'
                        })
            except:
                pass
        
        if not news_items:
            return {'crux': [], 'sentiment': 'NEUTRAL', 'score': 0}
        
        # ===== ANALYZE NEWS =====
        positive_keywords = [
            'profit', 'growth', 'rise', 'gain', 'positive', 'upgrade', 'strong',
            'record', 'boost', 'expansion', 'launch', 'partnership', 'dividend',
            'bonus', 'split', 'approval', 'buyback', 'acquisition', 'contract',
            'order', 'revenue', 'beat', 'outperform', 'rally', 'surge', 'jump',
            'target price', 'bullish', 'recovery', 'turnaround'
        ]
        
        negative_keywords = [
            'loss', 'fall', 'drop', 'decline', 'negative', 'downgrade', 'weak',
            'probe', 'investigation', 'fraud', 'scam', 'penalty', 'fine',
            'debt', 'default', 'arrest', 'raid', 'crash', 'fear', 'warning',
            'concern', 'risk', 'lawsuit', 'ban', 'crisis', 'layoff', 'firing',
            'resign', 'protest', 'strike', 'dispute', 'tension'
        ]
        
        # Score each news item
        scored_news = []
        for news in news_items:
            title_lower = news['title'].lower()
            pos_score = sum(1 for word in positive_keywords if word in title_lower)
            neg_score = sum(1 for word in negative_keywords if word in title_lower)
            net_score = pos_score - neg_score
            scored_news.append({**news, 'score': net_score})
        
        # Sort by impact
        scored_news.sort(key=lambda x: abs(x['score']), reverse=True)
        
        # ===== CREATE 3-POINT CRUX =====
        crux = []
        used_titles = []
        
        for news in scored_news:
            # Skip similar titles
            title_words = set(news['title'].lower().split())
            is_duplicate = False
            for used in used_titles:
                used_words = set(used.lower().split())
                if len(title_words & used_words) / len(title_words | used_words) > 0.6:
                    is_duplicate = True
                    break
            
            if not is_duplicate and len(crux) < 3:
                used_titles.append(news['title'])
                
                if news['score'] > 0:
                    prefix = "✅"
                elif news['score'] < 0:
                    prefix = "⚠️"
                else:
                    prefix = "📌"
                
                # Clean and shorten title for crux
                clean_title = news['title'][:100]
                crux.append(f"{prefix} {clean_title}")
        
        # ===== CALCULATE SENTIMENT =====
        total_score = sum(n['score'] for n in scored_news)
        avg_score = total_score / len(scored_news) if scored_news else 0
        
        if avg_score > 2:
            sentiment = '🟢 VERY POSITIVE'
            impact = 20
        elif avg_score > 0.5:
            sentiment = '🔵 POSITIVE'
            impact = 12
        elif avg_score > -0.5:
            sentiment = '🟡 NEUTRAL'
            impact = 0
        elif avg_score > -2:
            sentiment = '🟠 NEGATIVE'
            impact = -12
        else:
            sentiment = '🔴 VERY NEGATIVE'
            impact = -25
        
        return {
            'crux': crux if crux else ['📌 No significant news today'],
            'sentiment': sentiment,
            'score': impact,
            'count': len(news_items)
        }
        
    except Exception as e:
        return {'crux': ['📌 News unavailable'], 'sentiment': '🟡 NEUTRAL', 'score': 0}

# ============================================
# TELEGRAM SENDER
# ============================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts[:3]:
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': part, 'parse_mode': 'HTML'}, timeout=10)
                time.sleep(1)
        else:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return True
    except:
        return False

# ============================================
# MAIN ANALYZER
# ============================================
def analyze():
    nse = Nse()
    results = []
    now = datetime.now()
    ist_time = now.strftime('%I:%M %p')
    ist_date = now.strftime('%d-%b-%Y')
    
    all_symbols = []
    for sector, symbols in STOCKS.items():
        all_symbols.extend(symbols)
    
    print(f"🔄 Analyzing {len(all_symbols)} stocks...")
    
    for symbol in all_symbols:
        try:
            # Get stock data
            q = nse.get_quote(symbol)
            if not q:
                continue
            
            intraday = q.get('intraDayHighLow', {})
            weekly = q.get('weekHighLow', {})
            
            price = float(q.get('lastPrice', 0))
            high = float(intraday.get('max', 0))
            low = float(intraday.get('min', 0))
            change_pct = float(q.get('pChange', 0))
            vwap = float(q.get('vwap', 0)) if q.get('vwap') else 0
            high_52 = float(weekly.get('max', 0))
            low_52 = float(weekly.get('min', 0))
            
            # ===== TECHNICAL SCORE (60 points max) =====
            tech_score = 0
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            
            if 50 < pos < 80: tech_score += 15
            elif pos < 30: tech_score += 12
            
            dist_high = ((high_52 - price) / high_52 * 100) if high_52 > 0 else 0
            dist_low = ((price - low_52) / low_52 * 100) if low_52 > 0 else 0
            
            if dist_high > 20: tech_score += 15
            elif dist_high > 10: tech_score += 10
            
            if dist_low < 10: tech_score += 12
            
            vs_vwap = ((price - vwap) / vwap * 100) if vwap > 0 else 0
            if 0 < vs_vwap < 2: tech_score += 10
            
            if 0.5 < change_pct < 2: tech_score += 8
            elif -2 < change_pct < -0.5: tech_score += 5
            
            # ===== NEWS SCORE (25 points max) =====
            news_data = fetch_news_crux(symbol)
            news_score = news_data['score']
            
            # ===== MOMENTUM (15 points max) =====
            momentum = 0
            buy_qty = float(q.get('totalBuyQuantity', 0))
            sell_qty = float(q.get('totalSellQuantity', 0))
            if buy_qty > sell_qty * 1.3: momentum += 8
            if change_pct > 0: momentum += 7
            
            # ===== FINAL SCORE =====
            total_score = tech_score + news_score + momentum
            total_score = max(5, min(95, total_score + 10))
            
            # Cap if very negative news
            if news_data['score'] <= -20:
                total_score = min(total_score, 35)
            
            target = round(price * (1 + total_score / 100), 2)
            stop_loss = round(price * 0.95, 2)
            
            if total_score >= 80: action = "STRONG BUY 💪"
            elif total_score >= 65: action = "BUY ✅"
            elif total_score >= 50: action = "ACCUMULATE 📥"
            elif total_score >= 35: action = "WATCH 👀"
            else: action = "AVOID ❌"
            
            # Find sector
            sector = next((sec for sec, syms in STOCKS.items() if symbol in syms), "Other")
            
            results.append({
                'symbol': symbol,
                'sector': sector,
                'price': price,
                'score': total_score,
                'action': action,
                'sentiment': news_data['sentiment'],
                'target': target,
                'stop_loss': stop_loss,
                'change_pct': change_pct,
                'news_crux': news_data['crux'],
                'news_count': news_data.get('count', 0)
            })
            
            print(f"  {symbol}: ₹{price:.0f} | Score: {total_score} | {news_data['sentiment']}")
            time.sleep(0.4)
            
        except Exception as e:
            print(f"  {symbol}: ⚠️ {str(e)[:30]}")
    
    if not results:
        send_telegram("❌ Analysis failed. Market may be closed.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # ===== BUILD MESSAGE =====
    strong = len([r for r in results if r['score'] >= 80])
    buy = len([r for r in results if 65 <= r['score'] < 80])
    neg_news = len([r for r in results if 'NEGATIVE' in r['sentiment']])
    
    # Header - Clean, no "Morning" label
    message = f"📊 <b>MARKET ANALYSIS</b>\n"
    message += f"📅 {ist_date} | ⏰ {ist_time} IST\n"
    message += f"{'═'*35}\n\n"
    
    message += f"📈 <b>Snapshot:</b> {len(results)} stocks | 🟢{strong} | 🔵{buy} | 🔴{neg_news}\n\n"
    
    # Top 5 picks with news crux
    message += f"🎯 <b>TOP 5 PICKS</b>\n"
    message += f"{'─'*35}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        emoji = "🟢" if r['score'] >= 80 else "🔵" if r['score'] >= 65 else "🟡"
        
        message += f"{emoji} <b>{i}. {r['symbol']}</b> | {r['sector']}\n"
        message += f"💰 ₹{r['price']:.0f} → 🎯 ₹{r['target']:.0f} (+{gain:.0f}%) | {r['action']}\n"
        message += f"📊 Score: {r['score']}/100 | Sentiment: {r['sentiment']}\n"
        
        # News Crux (3 points)
        if r['news_crux']:
            message += f"📰 <b>Key News:</b>\n"
            for crux in r['news_crux'][:3]:
                message += f"   {crux}\n"
        
        message += f"🛑 Stop Loss: ₹{r['stop_loss']:.0f}\n\n"
    
    # Warning: Negative news stocks
    bad = [r for r in results if 'NEGATIVE' in r['sentiment'] and r['score'] >= 40]
    if bad:
        message += f"⚠️ <b>CAUTION CORNER</b>\n{'─'*35}\n"
        for r in bad[:3]:
            message += f"🔴 <b>{r['symbol']}</b> - {r['sentiment']}\n"
            for crux in r['news_crux'][:2]:
                message += f"   {crux}\n"
        message += "\n"
    
    # Hot sectors
    message += f"🔥 <b>HOT SECTORS</b>\n{'─'*35}\n"
    sectors_avg = {}
    for r in results:
        sec = r['sector']
        if sec not in sectors_avg:
            sectors_avg[sec] = []
        sectors_avg[sec].append(r['score'])
    
    for sec, scores in sorted(sectors_avg.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)[:4]:
        avg = sum(scores) / len(scores)
        bar = "█" * int(avg/10) + "░" * (10 - int(avg/10))
        message += f"{bar} {sec}: {avg:.0f}/100\n"
    
    message += f"\n{'═'*35}\n"
    message += f"💡 <i>Analysis: Technical + News Crux</i>\n"
    message += f"⚠️ <i>Verify independently before trading</i>"
    
    send_telegram(message)
    print("✅ Analysis sent!")

if __name__ == "__main__":
    analyze()
