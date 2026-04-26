"""
PRODUCTION Stock Analyzer - Nifty 50 + Next 50 + Midcap Multibaggers
Strategy: Technical + Volume + News + Market Context
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime
import re
from xml.etree import ElementTree

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Expanded universe: Nifty 50 + Next 50 + High Growth Midcaps
STOCKS = {
    '🖥️ IT Giants': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'PERSISTENT', 'LTI', 'MINDTREE'],
    
    '🏦 Banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK', 
                   'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB', 'AUBANK'],
    
    '🏗️ Infrastructure': ['LT', 'ADANIPORTS', 'HAL', 'BEL', 'IRCON', 'RVNL'],
    
    '🏭 Manufacturing': ['RELIANCE', 'TATASTEEL', 'JSWSTEEL', 'HINDZINC', 
                         'VEDL', 'JINDALSTEL', 'ADANIENT'],
    
    '💊 Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LAURUSLABS', 
                  'ALKEM', 'BIOCON'],
    
    '🛒 Consumer': ['ITC', 'HINDUNILVR', 'TITAN', 'DMART', 'TRENT', 
                    'METROBRAND', 'TATACONSUM'],
    
    '🚗 Auto': ['MARUTI', 'TATAMOTORS', 'BAJAJ-AUTO', 'M&M', 'EICHERMOT', 'TVSMOTOR'],
    
    '⚡ Energy': ['POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER', 'ADANIGREEN', 'NHPC'],
    
    '💰 Financial': ['BAJFINANCE', 'BAJAJFINSV', 'HDFC', 'CHOLAFIN', 'MUTHOOTFIN'],
    
    '🔧 Others': ['ASIANPAINT', 'PIDILITIND', 'BERGEPAINT', 'IRCTC', 'ZOMATO']
}

# ============================================
# MARKET CONTEXT (FII/DII + Options)
# ============================================
def get_market_context():
    """Get overall market sentiment"""
    context = {}
    
    # FII/DII Data
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        session.get("https://www.nseindia.com", timeout=5)
        
        url = "https://www.nseindia.com/api/fii-dii-activity"
        resp = session.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data:
                last = data[-1]
                fii_net = float(last.get('netValue', 0))
                dii_net = float(last.get('diiNetValue', 0))
                
                context['fii'] = f"🌍 FII: {'🟢 +' if fii_net > 0 else '🔴 '}{fii_net:.0f} Cr"
                context['dii'] = f"🏠 DII: {'🟢 +' if dii_net > 0 else '🔴 '}{dii_net:.0f} Cr"
    except:
        context['fii'] = "🌍 FII: Data N/A"
        context['dii'] = "🏠 DII: Data N/A"
    
    # Nifty PCR
    try:
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            records = data.get('records', {}).get('data', [])
            
            total_put = sum(r.get('PE', {}).get('openInterest', 0) for r in records[:30] if 'PE' in r)
            total_call = sum(r.get('CE', {}).get('openInterest', 0) for r in records[:30] if 'CE' in r)
            
            if total_call > 0:
                pcr = total_put / total_call
                if pcr > 1.3: signal = '🟢 Bullish'
                elif pcr > 0.9: signal = '🟡 Neutral'
                else: signal = '🔴 Bearish'
                context['pcr'] = f"📊 PCR: {pcr:.2f} ({signal})"
    except:
        context['pcr'] = "📊 PCR: Data N/A"
    
    return context

# ============================================
# NEWS ANALYSIS (Proven Method)
# ============================================
def get_news_analysis(symbol):
    """Get news sentiment with crux"""
    try:
        # Multiple news queries for better coverage
        queries = [
            f"{symbol} stock NSE share price",
            f"{symbol} company results news",
            f"{symbol} stock market today"
        ]
        
        all_news = []
        
        for query in queries[:2]:
            try:
                url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
                resp = requests.get(url, timeout=6)
                root = ElementTree.fromstring(resp.content)
                
                for item in root.findall('.//item')[:8]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    # Clean title
                    title = re.sub(r'[^\w\s\-.,%₹$&()]', '', title)
                    if len(title) > 25 and symbol[:4] in title.upper():
                        all_news.append(title)
            except:
                pass
        
        if not all_news:
            return {'crux': ['📌 Limited news coverage'], 'sentiment': '🟡 Neutral', 'score': 0}
        
        # Remove duplicates
        all_news = list(set(all_news))
        
        # Sentiment scoring
        positive_words = [
            'profit', 'growth', 'revenue', 'rise', 'gain', 'upgrade', 'strong',
            'record', 'boost', 'expansion', 'launch', 'partnership', 'dividend',
            'buyback', 'contract', 'order win', 'beat', 'outperform', 'rally',
            'surge', 'jump', 'target', 'bullish', 'recovery', 'turnaround',
            'acquisition', 'merger', 'approval', 'positive'
        ]
        
        negative_words = [
            'loss', 'fall', 'drop', 'decline', 'downgrade', 'weak', 'probe',
            'fraud', 'scam', 'penalty', 'fine', 'debt', 'default', 'arrest',
            'raid', 'crash', 'concern', 'risk', 'lawsuit', 'crisis', 'layoff',
            'resign', 'protest', 'strike', 'dispute', 'negative', 'caution'
        ]
        
        scored_news = []
        for title in all_news:
            t = title.lower()
            pos = sum(1 for w in positive_words if w in t)
            neg = sum(1 for w in negative_words if w in t)
            scored_news.append({'title': title[:120], 'score': pos - neg})
        
        scored_news.sort(key=lambda x: abs(x['score']), reverse=True)
        
        # Create crux (3 unique points)
        crux = []
        seen = set()
        for news in scored_news:
            key = ' '.join(news['title'].lower().split()[:4])
            if key not in seen and len(crux) < 3:
                seen.add(key)
                if news['score'] > 0:
                    crux.append(f"✅ {news['title']}")
                elif news['score'] < 0:
                    crux.append(f"⚠️ {news['title']}")
                else:
                    crux.append(f"📌 {news['title']}")
        
        # Overall sentiment
        avg = sum(n['score'] for n in scored_news) / len(scored_news)
        
        if avg > 1.5: sentiment = '🟢 Very Positive'
        elif avg > 0.3: sentiment = '🔵 Positive'
        elif avg > -0.3: sentiment = '🟡 Neutral'
        elif avg > -1.5: sentiment = '🟠 Negative'
        else: sentiment = '🔴 Very Negative'
        
        return {
            'crux': crux if crux else ['📌 No clear news direction'],
            'sentiment': sentiment,
            'score': avg * 8  # Scale for scoring
        }
        
    except:
        return {'crux': ['📌 News unavailable'], 'sentiment': '🟡 Neutral', 'score': 0}

# ============================================
# TELEGRAM
# ============================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts[:3]:
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': part, 'parse_mode': 'HTML'}, timeout=10)
                time.sleep(0.5)
        else:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
    except:
        pass

# ============================================
# MAIN ANALYZER
# ============================================
def analyze():
    nse = Nse()
    results = []
    now = datetime.now()
    ist_time = now.strftime('%I:%M %p')
    ist_date = now.strftime('%d-%b-%Y')
    
    # Get market context
    print("📊 Getting market context...")
    market = get_market_context()
    
    # Flatten all stocks
    all_stocks = []
    for sector, symbols in STOCKS.items():
        for sym in symbols:
            all_stocks.append((sym, sector))
    
    print(f"🔄 Analyzing {len(all_stocks)} stocks across {len(STOCKS)} sectors...")
    
    for symbol, sector in all_stocks:
        try:
            q = nse.get_quote(symbol)
            if not q:
                continue
            
            intraday = q.get('intraDayHighLow', {})
            weekly = q.get('weekHighLow', {})
            
            price = float(q.get('lastPrice', 0))
            if price == 0:
                continue
                
            high = float(intraday.get('max', 0))
            low = float(intraday.get('min', 0))
            open_price = float(q.get('open', 0))
            change_pct = float(q.get('pChange', 0))
            vwap = float(q.get('vwap', 0)) if q.get('vwap') else 0
            high_52 = float(weekly.get('max', 0))
            low_52 = float(weekly.get('min', 0))
            prev_close = float(q.get('previousClose', 0))
            
            # ===== SCORING =====
            
            # 1. PRICE ACTION (30 points)
            price_score = 0
            
            # Day range position
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            
            if 50 < pos < 75:
                price_score += 10  # Strong, not overbought
            elif pos < 30:
                price_score += 8   # Potential reversal
            
            # 52-week position (Value play)
            dist_high = ((high_52 - price) / high_52 * 100) if high_52 > 0 else 0
            dist_low = ((price - low_52) / low_52 * 100) if low_52 > 0 else 0
            
            if 15 < dist_high < 40:
                price_score += 12  # Room to grow
            elif dist_high > 40:
                price_score += 8   # Deep value
            
            if dist_low < 15:
                price_score += 8   # Near support
            
            # 2. VOLUME & DELIVERY (20 points)
            volume_score = 0
            delivery_signal = ""
            
            try:
                delivery_qty = float(q.get('deliveryQuantity', 0))
                total_vol = float(q.get('totalTradedVolume', 1))
                delivery_pct = (delivery_qty / total_vol * 100) if total_vol > 0 else 0
                
                if delivery_pct > 60:
                    volume_score += 15
                    delivery_signal = f"🟢 {delivery_pct:.0f}% delivery"
                elif delivery_pct > 45:
                    volume_score += 10
                    delivery_signal = f"🔵 {delivery_pct:.0f}% delivery"
                elif delivery_pct > 30:
                    volume_score += 5
                    delivery_signal = f"🟡 {delivery_pct:.0f}% delivery"
                else:
                    delivery_signal = f"🔴 {delivery_pct:.0f}% delivery"
            except:
                delivery_signal = "📌 N/A"
                # Fallback: Buy vs Sell quantity
                buy_qty = float(q.get('totalBuyQuantity', 0))
                sell_qty = float(q.get('totalSellQuantity', 0))
                if buy_qty > sell_qty * 1.3:
                    volume_score += 10
                    delivery_signal = "🔵 Buying pressure"
            
            # 3. NEWS SENTIMENT (20 points)
            news = get_news_analysis(symbol)
            
            # 4. MOMENTUM (15 points)
            momentum_score = 0
            
            if 0.3 < change_pct < 2:
                momentum_score += 10  # Steady rise
            elif 2 <= change_pct < 5:
                momentum_score += 6   # Strong but may pullback
            elif -2 < change_pct < 0:
                momentum_score += 8   # Dip opportunity
            
            if price > vwap and vwap > 0:
                momentum_score += 5
            
            # 5. TECHNICAL PATTERN (10 points)
            pattern_score = 0
            patterns = []
            
            # Bullish candle
            body = abs(price - open_price)
            if body > 0 and price > open_price:
                patterns.append("📈 Green candle")
                pattern_score += 4
            
            # Above VWAP
            if price > vwap > 0:
                patterns.append("Above VWAP")
                pattern_score += 3
            
            # Near day high
            if pos > 70:
                patterns.append("Near day high")
                pattern_score += 3
            
            # 6. SECTOR BONUS (5 points)
            # Premium sectors get bonus
            premium_sectors = ['🖥️ IT Giants', '🏦 Banking', '💊 Pharma']
            if sector in premium_sectors:
                pattern_score += 3
            
            # ===== TOTAL SCORE =====
            total_score = (
                price_score * 0.30 +
                volume_score * 0.20 +
                news['score'] * 0.20 +
                momentum_score * 0.15 +
                pattern_score * 0.10 +
                5  # Base
            )
            
            total_score = max(5, min(95, round(total_score)))
            
            # Apply penalties
            if news['sentiment'] in ['🔴 Very Negative', '🟠 Negative']:
                total_score = min(total_score, 45)
            
            # Calculate targets
            target = round(price * (1 + total_score / 100), 2)
            stop_loss = round(price * 0.95, 2)
            
            # Action
            if total_score >= 75:
                action = "💪 STRONG BUY"
                stars = "⭐⭐⭐⭐⭐"
            elif total_score >= 60:
                action = "✅ BUY"
                stars = "⭐⭐⭐⭐"
            elif total_score >= 50:
                action = "📥 ACCUMULATE"
                stars = "⭐⭐⭐"
            elif total_score >= 35:
                action = "👀 WATCH"
                stars = "⭐⭐"
            else:
                action = "❌ SKIP"
                stars = "⭐"
            
            results.append({
                'symbol': symbol, 'sector': sector, 'price': price,
                'score': total_score, 'stars': stars, 'action': action,
                'target': target, 'stop_loss': stop_loss,
                'change_pct': change_pct,
                'delivery': delivery_signal,
                'news_sentiment': news['sentiment'],
                'news_crux': news['crux'][:2],
                'patterns': patterns[:2]
            })
            
            print(f"  {symbol:15} ₹{price:>8.0f} | Score: {total_score:>2} | {stars}")
            time.sleep(0.2)
            
        except Exception as e:
            print(f"  {symbol}: ⚠️ {str(e)[:30]}")
    
    if not results:
        send_telegram("❌ No data. Market may be closed.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # ===== BUILD MESSAGE =====
    strong_buy = len([r for r in results if r['score'] >= 75])
    buy = len([r for r in results if 60 <= r['score'] < 75])
    accumulate = len([r for r in results if 50 <= r['score'] < 60])
    
    # HEADER
    message = f"📊 <b>MULTI-BAGGER SCANNER</b>\n"
    message += f"📅 {ist_date} | ⏰ {ist_time} IST\n"
    message += f"{'═'*35}\n\n"
    
    # MARKET CONTEXT
    message += f"🏦 <b>MARKET CONTEXT</b>\n"
    message += f"{'─'*35}\n"
    if market:
        for key, value in market.items():
            message += f"{value}\n"
    message += f"\n"
    
    # QUICK STATS
    message += f"📈 <b>SCREENING {len(results)} STOCKS</b>\n"
    message += f"├ 💪 Strong Buy: {strong_buy}\n"
    message += f"├ ✅ Buy: {buy}\n"
    message += f"└ 📥 Accumulate: {accumulate}\n\n"
    
    # TOP PICKS
    message += f"🎯 <b>TOP 7 MULTI-BAGGER CANDIDATES</b>\n"
    message += f"{'═'*35}\n\n"
    
    for i, r in enumerate(results[:7], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        
        if r['score'] >= 75:
            emoji = "🟢"
        elif r['score'] >= 60:
            emoji = "🔵"
        elif r['score'] >= 50:
            emoji = "🟡"
        else:
            emoji = "⚪"
        
        message += f"{emoji} <b>{i}. {r['symbol']}</b> | {r['sector']}\n"
        message += f"   💰 ₹{r['price']:.0f} | 🎯 ₹{r['target']:.0f} (+{gain:.0f}%) | {r['stars']}\n"
        message += f"   📊 Score: {r['score']}/100 | {r['action']}\n"
        message += f"   📦 {r['delivery']}\n"
        message += f"   📰 News: {r['news_sentiment']}\n"
        
        if r['news_crux']:
            for crux in r['news_crux']:
                message += f"   {crux}\n"
        
        message += f"   🛑 Stop Loss: ₹{r['stop_loss']:.0f}\n\n"
    
    # SECTOR SUMMARY
    message += f"🔥 <b>SECTOR LEADERS</b>\n{'─'*35}\n"
    sector_scores = {}
    for r in results:
        sec = r['sector']
        if sec not in sector_scores:
            sector_scores[sec] = []
        sector_scores[sec].append(r['score'])
    
    for sec, scores in sorted(sector_scores.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)[:5]:
        avg = sum(scores) / len(scores)
        bar = "█" * int(avg/10) + "░" * (10 - int(avg/10))
        message += f"{bar} {sec}: {avg:.0f}/100\n"
    
    message += f"\n{'═'*35}\n"
    message += f"🎯 <i>Focus: Score 75+ for swing trading</i>\n"
    message += f"⚠️ <i>5% stop loss mandatory. Book at target.</i>"
    
    send_telegram(message)
    print(f"\n✅ Analysis complete! Top pick: {results[0]['symbol']} ({results[0]['score']}/100)")

if __name__ == "__main__":
    analyze()
