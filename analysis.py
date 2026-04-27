"""
MULTI-BAGGER STOCK SCANNER - Production Version
Nifty 50 + Next 50 + Midcap Stocks
Strategy: Value + Momentum + Smart Money + News
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime
import re
from xml.etree import ElementTree

# Set India Timezone
os.environ['TZ'] = 'Asia/Kolkata'

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

STOCKS = {
    '🖥️ IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'PERSISTENT', 'LTI'],
    '🏦 Banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK', 
                   'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB'],
    '🏗️ Infra': ['LT', 'ADANIPORTS', 'HAL', 'BEL', 'IRCON'],
    '🏭 Industry': ['RELIANCE', 'TATASTEEL', 'JSWSTEEL', 'ADANIENT'],
    '💊 Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LAURUSLABS', 'BIOCON'],
    '🛒 Consumer': ['ITC', 'HINDUNILVR', 'TITAN', 'DMART', 'TRENT', 'TATACONSUM'],
    '🚗 Auto': ['MARUTI', 'TATAMOTORS', 'BAJAJ-AUTO', 'M&M', 'EICHERMOT'],
    '⚡ Energy': ['POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER', 'NHPC'],
    '💰 Finance': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN', 'MUTHOOTFIN'],
    '🔧 Others': ['ASIANPAINT', 'PIDILITIND', 'IRCTC', 'ZOMATO']
}

# ============================================
# MARKET CONTEXT
# ============================================
def get_market_context():
    """Get FII/DII + Options data"""
    context = {}
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        session.get("https://www.nseindia.com", timeout=5)
        
        # FII/DII
        try:
            resp = session.get("https://www.nseindia.com/api/fii-dii-activity", timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    last = data[-1]
                    fii = float(last.get('netValue', 0))
                    dii = float(last.get('diiNetValue', 0))
                    context['fii'] = f"🌍 FII: {'🟢 +' if fii > 0 else '🔴 '}{fii:.0f} Cr"
                    context['dii'] = f"🏠 DII: {'🟢 +' if dii > 0 else '🔴 '}{dii:.0f} Cr"
        except:
            context['fii'] = "🌍 FII: Data N/A"
            context['dii'] = "🏠 DII: Data N/A"
        
        # PCR
        try:
            resp = session.get("https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY", timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                records = data.get('records', {}).get('data', [])
                put_oi = sum(r.get('PE', {}).get('openInterest', 0) for r in records[:30] if 'PE' in r)
                call_oi = sum(r.get('CE', {}).get('openInterest', 0) for r in records[:30] if 'CE' in r)
                if call_oi > 0:
                    pcr = put_oi / call_oi
                    signal = '🟢 Bullish' if pcr > 1.3 else '🟡 Neutral' if pcr > 0.9 else '🔴 Bearish'
                    context['pcr'] = f"📊 Nifty PCR: {pcr:.2f} ({signal})"
        except:
            context['pcr'] = "📊 PCR: Data N/A"
            
    except:
        pass
    
    return context

# ============================================
# NEWS ANALYSIS
# ============================================
def get_news_analysis(symbol):
    """Get news sentiment with crux"""
    try:
        all_news = []
        
        # Search with 2 different queries
        for query in [f"{symbol} stock NSE", f"{symbol} share market"]:
            try:
                url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
                resp = requests.get(url, timeout=5)
                root = ElementTree.fromstring(resp.content)
                
                for item in root.findall('.//item')[:8]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    title = re.sub(r'[^\w\s\-.,%₹$&()]', '', title)
                    if len(title) > 20:
                        all_news.append(title)
            except:
                pass
        
        if not all_news:
            return {'crux': ['📌 Limited news'], 'sentiment': '🟡 Neutral', 'score': 8}
        
        all_news = list(set(all_news))  # Remove duplicates
        
        # Sentiment words
        pos_words = ['profit', 'growth', 'revenue', 'rise', 'gain', 'upgrade', 'strong',
                     'record', 'boost', 'expansion', 'dividend', 'buyback', 'contract',
                     'order', 'beat', 'rally', 'surge', 'bullish', 'recovery', 'positive']
        neg_words = ['loss', 'fall', 'drop', 'decline', 'downgrade', 'weak', 'probe',
                     'fraud', 'scam', 'penalty', 'debt', 'default', 'crash', 'concern',
                     'risk', 'lawsuit', 'crisis', 'negative', 'caution']
        
        scored = []
        for title in all_news:
            t = title.lower()
            pos = sum(1 for w in pos_words if w in t)
            neg = sum(1 for w in neg_words if w in t)
            scored.append({'title': title[:120], 'score': pos - neg})
        
        scored.sort(key=lambda x: abs(x['score']), reverse=True)
        
        # Create crux
        crux = []
        seen = set()
        for news in scored:
            key = ' '.join(news['title'].lower().split()[:3])
            if key not in seen and len(crux) < 3:
                seen.add(key)
                if news['score'] > 0:
                    crux.append(f"✅ {news['title']}")
                elif news['score'] < 0:
                    crux.append(f"⚠️ {news['title']}")
                else:
                    crux.append(f"📌 {news['title']}")
        
        # Overall sentiment
        avg = sum(n['score'] for n in scored) / len(scored)
        
        if avg > 1.5: sentiment, score = '🟢 Very Positive', 14
        elif avg > 0.3: sentiment, score = '🔵 Positive', 11
        elif avg > -0.3: sentiment, score = '🟡 Neutral', 8
        elif avg > -1.5: sentiment, score = '🟠 Negative', 4
        else: sentiment, score = '🔴 Very Negative', 1
        
        return {'crux': crux if crux else ['📌 No clear direction'], 'sentiment': sentiment, 'score': score}
        
    except:
        return {'crux': ['📌 News unavailable'], 'sentiment': '🟡 Neutral', 'score': 8}

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
    
    print(f"\n{'='*50}")
    print(f"🔬 MULTI-BAGGER SCANNER - {ist_time}")
    print(f"{'='*50}")
    
    # Market context
    print("📊 Getting market context...")
    market = get_market_context()
    
    # Flatten stocks
    all_stocks = []
    for sector, symbols in STOCKS.items():
        for sym in symbols:
            all_stocks.append((sym, sector))
    
    print(f"🔄 Analyzing {len(all_stocks)} stocks...\n")
    
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
            
            # 1. VALUE & POSITION SCORE (0-35 points)
            value_score = 0
            
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            
            if 50 < pos < 80:
                value_score += 10
            elif 30 <= pos <= 50:
                value_score += 7
            elif pos < 30:
                value_score += 8
            
            dist_high = ((high_52 - price) / high_52 * 100) if high_52 > 0 else 0
            dist_low = ((price - low_52) / low_52 * 100) if low_52 > 0 else 0
            
            if dist_high > 30: value_score += 12
            elif dist_high > 15: value_score += 10
            elif dist_high > 5: value_score += 5
            
            if dist_low < 10: value_score += 8
            elif dist_low < 20: value_score += 5
            
            vs_vwap = ((price - vwap) / vwap * 100) if vwap > 0 else 0
            if 0 < vs_vwap < 2: value_score += 8
            elif -1 < vs_vwap <= 0: value_score += 10
            elif vs_vwap < -2: value_score += 4
            
            # 2. MOMENTUM SCORE (0-25 points)
            momentum_score = 0
            
            if 1 < change_pct < 3: momentum_score += 12
            elif 0.5 < change_pct <= 1: momentum_score += 10
            elif 0 < change_pct <= 0.5: momentum_score += 8
            elif -1 < change_pct <= 0: momentum_score += 7
            elif -3 < change_pct <= -1: momentum_score += 5
            
            gap = ((open_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            if 0 < gap < 1: momentum_score += 8
            elif gap > 1: momentum_score += 5
            
            if price > vwap and vwap > 0:
                momentum_score += 5
            
            # 3. SMART MONEY SCORE (0-20 points)
            smart_score = 0
            delivery_info = ""
            
            try:
                delivery_qty = float(q.get('deliveryQuantity', 0))
                total_vol = float(q.get('totalTradedVolume', 1))
                delivery_pct = (delivery_qty / total_vol * 100) if total_vol > 0 else 0
                
                if delivery_pct > 65:
                    smart_score += 18
                    delivery_info = f"🟢 {delivery_pct:.0f}% Strong Hands"
                elif delivery_pct > 50:
                    smart_score += 14
                    delivery_info = f"🔵 {delivery_pct:.0f}% Good"
                elif delivery_pct > 40:
                    smart_score += 10
                    delivery_info = f"🟡 {delivery_pct:.0f}% Avg"
                elif delivery_pct > 25:
                    smart_score += 5
                    delivery_info = f"🟠 {delivery_pct:.0f}% Low"
                else:
                    delivery_info = f"🔴 {delivery_pct:.0f}% Speculative"
            except:
                buy_qty = float(q.get('totalBuyQuantity', 0))
                sell_qty = float(q.get('totalSellQuantity', 0))
                total = buy_qty + sell_qty
                if total > 0:
                    buy_ratio = buy_qty / total
                    if buy_ratio > 0.6:
                        smart_score += 12
                        delivery_info = f"🔵 {buy_ratio:.0%} Buyers"
                    elif buy_ratio > 0.5:
                        smart_score += 8
                        delivery_info = f"🟡 Balanced"
                    else:
                        smart_score += 4
                        delivery_info = f"🔴 Sellers"
                else:
                    delivery_info = "📌 N/A"
            
            # 4. NEWS SENTIMENT (0-15 points)
            news = get_news_analysis(symbol)
            
            # 5. TECHNICAL BONUS (0-5 points)
            tech_bonus = 0
            
            if price > open_price and open_price > prev_close:
                tech_bonus += 2
            
            if price > vwap > 0:
                tech_bonus += 1
            
            if high > prev_close:
                tech_bonus += 1
            
            if pos > 60:
                tech_bonus += 1
            
            # ===== TOTAL SCORE =====
            total_score = value_score + momentum_score + smart_score + news['score'] + tech_bonus
            total_score = max(5, min(95, total_score))
            
            # Cap for negative news
            if news['sentiment'] == '🔴 Very Negative':
                total_score = min(total_score, 35)
            elif news['sentiment'] == '🟠 Negative':
                total_score = min(total_score, 55)
            
            # Target based on conviction
            if total_score >= 80: target_mult = 1.8
            elif total_score >= 65: target_mult = 1.5
            elif total_score >= 50: target_mult = 1.3
            else: target_mult = 1.15
            
            target = round(price * target_mult, 2)
            stop_loss = round(price * 0.95, 2)
            
            # Action
            if total_score >= 80:
                action, stars, conf = "💪 STRONG BUY", "⭐⭐⭐⭐⭐", "HIGH"
            elif total_score >= 65:
                action, stars, conf = "✅ BUY", "⭐⭐⭐⭐", "GOOD"
            elif total_score >= 55:
                action, stars, conf = "📥 ACCUMULATE", "⭐⭐⭐", "MODERATE"
            elif total_score >= 40:
                action, stars, conf = "👀 WATCH", "⭐⭐", "LOW"
            else:
                action, stars, conf = "❌ SKIP", "⭐", "NONE"
            
            results.append({
                'symbol': symbol, 'sector': sector, 'price': price,
                'score': total_score, 'stars': stars, 'action': action,
                'target': target, 'stop_loss': stop_loss,
                'change_pct': change_pct, 'delivery': delivery_info,
                'news_sentiment': news['sentiment'],
                'news_crux': news['crux'],
                'confidence': conf
            })
            
            print(f"  {symbol:15} ₹{price:>8.0f} | V:{value_score} M:{momentum_score} S:{smart_score} N:{news['score']} = {total_score:>2} | {stars}")
            time.sleep(0.15)
            
        except Exception as e:
            print(f"  {symbol}: ⚠️ {str(e)[:30]}")
    
    if not results:
        send_telegram("❌ No data available.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # ===== BUILD TELEGRAM MESSAGE =====
    strong = len([r for r in results if r['score'] >= 80])
    buy = len([r for r in results if 65 <= r['score'] < 80])
    acc = len([r for r in results if 55 <= r['score'] < 65])
    watch = len([r for r in results if 40 <= r['score'] < 55])
    
    message = f"📊 <b>MULTI-BAGGER SCANNER</b>\n"
    message += f"📅 {ist_date} | ⏰ {ist_time} IST\n"
    message += f"{'═'*35}\n\n"
    
    # Market Context
    if market:
        message += f"🏦 <b>MARKET CONTEXT</b>\n{'─'*35}\n"
        for v in market.values():
            message += f"{v}\n"
        message += "\n"
    
    # Stats
    message += f"📈 <b>SCREENED: {len(results)} STOCKS</b>\n"
    message += f"├ 💪 Strong Buy: {strong}\n"
    message += f"├ ✅ Buy: {buy}\n"
    message += f"├ 📥 Accumulate: {acc}\n"
    message += f"└ 👀 Watch: {watch}\n\n"
    
    # Top 7 Picks
    message += f"🎯 <b>TOP 7 PICKS</b>\n{'═'*35}\n\n"
    
    for i, r in enumerate(results[:7], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        emoji = "🟢" if r['score'] >= 80 else "🔵" if r['score'] >= 65 else "🟡" if r['score'] >= 55 else "⚪"
        
        message += f"{emoji} <b>{i}. {r['symbol']}</b> | {r['sector']}\n"
        message += f"   💰 ₹{r['price']:.0f} → 🎯 ₹{r['target']:.0f} (+{gain:.0f}%) | {r['stars']}\n"
        message += f"   📊 Score: {r['score']}/100 | {r['action']} | {r['confidence']} confidence\n"
        message += f"   📦 {r['delivery']}\n"
        message += f"   📰 {r['news_sentiment']}\n"
        
        if r['news_crux']:
            for crux in r['news_crux'][:2]:
                message += f"   {crux}\n"
        
        message += f"   🛑 Stop: ₹{r['stop_loss']:.0f}\n\n"
    
    # Sector Leaders
    message += f"🔥 <b>SECTOR RANKING</b>\n{'─'*35}\n"
    sec_scores = {}
    for r in results:
        s = r['sector']
        if s not in sec_scores: sec_scores[s] = []
        sec_scores[s].append(r['score'])
    
    for sec, scores in sorted(sec_scores.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)[:5]:
        avg = sum(scores) / len(scores)
        bar = "█" * int(avg/10) + "░" * (10 - int(avg/10))
        message += f"{bar} {sec}: {avg:.0f}/100\n"
    
    message += f"\n{'═'*35}\n"
    message += f"🎯 <i>Strong Buy (80+): Full position | Buy (65+): Half position</i>\n"
    message += f"⚠️ <i>5% stop loss mandatory | Book at target</i>"
    
    send_telegram(message)
    
    print(f"\n✅ Analysis complete!")
    print(f"🏆 Top Pick: {results[0]['symbol']} ({results[0]['score']}/100)")
    print(f"📊 Distribution: 🟢{strong} 🔵{buy} 🟡{acc} ⚪{watch}")

if __name__ == "__main__":
    analyze()
