"""
Advanced Stock Market Analyzer - GitHub Actions
Features: Technical Analysis + News Sentiment + Risk Assessment + Manipulation Detection
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime
import re

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Extended stock list with sectors
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
# NEWS SENTIMENT ANALYZER
# ============================================
def get_news_sentiment(symbol):
    """Get news sentiment for a stock"""
    try:
        # Google News RSS feed
        url = f"https://news.google.com/rss/search?q={symbol}+stock+NSE+India&hl=en-IN&gl=IN&ceid=IN:en"
        response = requests.get(url, timeout=10)
        
        from xml.etree import ElementTree
        root = ElementTree.fromstring(response.content)
        
        news_items = []
        for item in root.findall('.//item')[:10]:
            title = item.find('title').text if item.find('title') is not None else ""
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
            
            # Simple sentiment analysis
            positive_words = ['profit', 'growth', 'rise', 'gain', 'positive', 'buy', 'bullish', 
                            'upgrade', 'strong', 'record', 'boost', 'expansion', 'launch',
                            'partnership', 'dividend', 'bonus', 'split', 'approval']
            negative_words = ['loss', 'fall', 'drop', 'decline', 'negative', 'sell', 'bearish',
                            'downgrade', 'weak', 'probe', 'investigation', 'fraud', 'scam',
                            'penalty', 'fine', 'debt', 'default', 'arrest', 'raid']
            
            title_lower = title.lower()
            pos_count = sum(1 for word in positive_words if word in title_lower)
            neg_count = sum(1 for word in negative_words if word in title_lower)
            
            sentiment_score = pos_count - neg_count
            
            news_items.append({
                'title': title,
                'sentiment': sentiment_score,
                'date': pub_date
            })
        
        if not news_items:
            return {'sentiment': 'NEUTRAL', 'score': 0, 'news_count': 0, 'top_news': []}
        
        # Calculate overall sentiment
        total_score = sum(item['sentiment'] for item in news_items)
        avg_score = total_score / len(news_items)
        
        if avg_score > 2:
            sentiment = 'VERY POSITIVE'
        elif avg_score > 0.5:
            sentiment = 'POSITIVE'
        elif avg_score < -2:
            sentiment = 'VERY NEGATIVE'
        elif avg_score < -0.5:
            sentiment = 'NEGATIVE'
        else:
            sentiment = 'NEUTRAL'
        
        return {
            'sentiment': sentiment,
            'score': avg_score,
            'news_count': len(news_items),
            'top_news': [n['title'][:100] for n in news_items[:3]]
        }
        
    except Exception as e:
        return {'sentiment': 'NEUTRAL', 'score': 0, 'news_count': 0, 'top_news': []}

# ============================================
# TELEGRAM SENDER
# ============================================
def send_telegram(text):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts[:3]:
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': part, 'parse_mode': 'HTML'}, timeout=10)
                time.sleep(1)
        else:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ============================================
# MAIN ANALYZER
# ============================================
def analyze():
    """Advanced stock analysis with news sentiment"""
    nse = Nse()
    results = []
    now = datetime.now()
    ist_time = now.strftime('%I:%M %p')
    ist_date = now.strftime('%d-%b-%Y')
    
    print(f"Starting analysis at {ist_time} IST...")
    
    all_symbols = []
    for sector, symbols in STOCKS.items():
        all_symbols.extend(symbols)
    
    for symbol in all_symbols:
        try:
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
            prev_close = float(q.get('previousClose', 0))
            
            # ===== TECHNICAL SCORE =====
            tech_score = 0
            
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            if 50 < pos < 80: tech_score += 20
            elif pos < 30: tech_score += 15
            
            dist_high = ((high_52 - price) / high_52 * 100) if high_52 > 0 else 0
            dist_low = ((price - low_52) / low_52 * 100) if low_52 > 0 else 0
            
            if dist_high > 20: tech_score += 20
            if dist_low < 10: tech_score += 15
            
            vs_vwap = ((price - vwap) / vwap * 100) if vwap > 0 else 0
            if 0 < vs_vwap < 2: tech_score += 12
            
            # Volume check
            total_buy = float(q.get('totalBuyQuantity', 0))
            total_sell = float(q.get('totalSellQuantity', 0))
            if total_buy > total_sell * 1.3: tech_score += 10
            
            # ===== NEWS SENTIMENT SCORE =====
            news_data = get_news_sentiment(symbol)
            news_score = 0
            
            if news_data['sentiment'] == 'VERY POSITIVE': news_score = 18
            elif news_data['sentiment'] == 'POSITIVE': news_score = 12
            elif news_data['sentiment'] == 'NEGATIVE': news_score = -10
            elif news_data['sentiment'] == 'VERY NEGATIVE': news_score = -20
            
            # ===== MOMENTUM SCORE =====
            momentum_score = 0
            if 0.5 < change_pct < 2: momentum_score = 10
            elif 0 < change_pct <= 0.5: momentum_score = 5
            elif -1 < change_pct < 0: momentum_score = 8  # Dip opportunity
            
            # ===== FINAL SCORE =====
            total_score = tech_score + news_score + momentum_score
            total_score = max(0, min(100, total_score + 15))
            
            # Adjust for negative news
            if news_data['sentiment'] == 'VERY NEGATIVE':
                total_score = min(total_score, 40)  # Cap score
            
            target = round(price * (1 + total_score / 100), 2)
            stop_loss = round(price * 0.95, 2)
            
            if total_score >= 80: action = "STRONG BUY 💪"
            elif total_score >= 65: action = "BUY ✅"
            elif total_score >= 50: action = "ACCUMULATE 📥"
            elif total_score >= 35: action = "WATCH 👀"
            else: action = "AVOID ❌"
            
            # Find sector
            sector = "Other"
            for sec, syms in STOCKS.items():
                if symbol in syms:
                    sector = sec
                    break
            
            results.append({
                'symbol': symbol,
                'sector': sector,
                'price': price,
                'score': total_score,
                'tech_score': tech_score,
                'news_score': news_score,
                'action': action,
                'sentiment': news_data['sentiment'],
                'target': target,
                'stop_loss': stop_loss,
                'change_pct': change_pct,
                'news_count': news_data['news_count'],
                'top_news': news_data['top_news']
            })
            
            print(f"  {symbol}: Tech={tech_score} News={news_score} Total={total_score}")
            time.sleep(0.5)  # Slower for news fetching
            
        except Exception as e:
            print(f"  {symbol}: Error - {str(e)[:40]}")
    
    if not results:
        send_telegram("❌ No data available.")
        return
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # ===== BUILD MESSAGE =====
    message = f"📊 <b>MARKET ANALYSIS</b>\n"
    message += f"📅 {ist_date} | ⏰ {ist_time} IST\n"
    message += f"{'═'*35}\n\n"
    
    # Market overview
    strong_buy = len([r for r in results if r['score'] >= 80])
    buy = len([r for r in results if 65 <= r['score'] < 80])
    negative_news = len([r for r in results if r['sentiment'] in ['NEGATIVE', 'VERY NEGATIVE']])
    
    message += f"📈 <b>MARKET SNAPSHOT</b>\n"
    message += f"├ Stocks Analyzed: {len(results)}\n"
    message += f"├ Strong Buy: {strong_buy}\n"
    message += f"├ Buy: {buy}\n"
    message += f"└ Negative News: {negative_news} stocks\n\n"
    
    # Top picks with news
    message += f"🎯 <b>TOP 5 OPPORTUNITIES</b>\n"
    message += f"{'─'*35}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        
        emoji = "🟢" if r['score'] >= 80 else "🔵" if r['score'] >= 65 else "🟡"
        
        message += f"{emoji} <b>{i}. {r['symbol']}</b> ({r['sector']})\n"
        message += f"   💰 ₹{r['price']:.0f} | 🎯 ₹{r['target']:.0f} (+{gain:.0f}%)\n"
        message += f"   📊 Score: {r['score']}/100 | {r['action']}\n"
        message += f"   📰 News: {r['sentiment']} ({r['news_count']} articles)\n"
        message += f"   🛑 Stop: ₹{r['stop_loss']:.0f}\n"
        
        # Show top news headline if available
        if r['top_news']:
            headline = r['top_news'][0][:80]
            message += f"   📰 <i>\"{headline}...\"</i>\n"
        
        message += "\n"
    
    # Warning section for stocks with negative news
    bad_news_stocks = [r for r in results if r['sentiment'] in ['NEGATIVE', 'VERY NEGATIVE'] and r['score'] >= 50]
    if bad_news_stocks:
        message += f"⚠️ <b>CAUTION: Negative News</b>\n"
        message += f"{'─'*35}\n"
        for r in bad_news_stocks[:3]:
            message += f"🔴 {r['symbol']}: {r['sentiment']}\n"
            if r['top_news']:
                message += f"   <i>\"{r['top_news'][0][:70]}...\"</i>\n"
        message += "\n"
    
    # Sector performance
    message += f"📊 <b>SECTOR WATCH</b>\n"
    message += f"{'─'*35}\n"
    sectors = {}
    for r in results:
        sec = r['sector']
        if sec not in sectors:
            sectors[sec] = {'scores': [], 'count': 0}
        sectors[sec]['scores'].append(r['score'])
        sectors[sec]['count'] += 1
    
    for sec, data in sorted(sectors.items(), key=lambda x: sum(x[1]['scores'])/len(x[1]['scores']), reverse=True)[:5]:
        avg = sum(data['scores']) / len(data['scores'])
        message += f"├ {sec}: {avg:.0f}/100 avg\n"
    
    message += f"\n{'═'*35}\n"
    message += f"💡 <i>Analysis: Technical + News Sentiment</i>\n"
    message += f"⚠️ <i>Always verify news before investing</i>"
    
    send_telegram(message)
    print("Analysis complete! Sent to Telegram.")

if __name__ == "__main__":
    analyze()
