"""
ULTIMATE Stock Analyzer - Institutional Grade
Features: Technical + News + FII/DII + Insider Trading + Options + Volume
"""
import os
import time
import requests
import json
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

# NSE indices for PCR
NIFTY_SYMBOLS = {
    'TCS': 'TCS', 'INFY': 'INFY', 'WIPRO': 'WIPRO', 'HCLTECH': 'HCLTECH',
    'TECHM': 'TECHM', 'HDFCBANK': 'HDFCBANK', 'ICICIBANK': 'ICICIBANK',
    'KOTAKBANK': 'KOTAKBANK', 'SBIN': 'SBIN', 'AXISBANK': 'AXISBANK',
    'RELIANCE': 'RELIANCE', 'ITC': 'ITC', 'LT': 'LT',
    'HINDUNILVR': 'HINDUNILVR', 'NESTLEIND': 'NESTLEIND',
    'SUNPHARMA': 'SUNPHARMA', 'DRREDDY': 'DRREDDY', 'CIPLA': 'CIPLA',
    'TITAN': 'TITAN', 'ASIANPAINT': 'ASIANPAINT', 'MARUTI': 'MARUTI',
    'BAJFINANCE': 'BAJFINANCE', 'BAJAJFINSV': 'BAJAJFINSV',
    'POWERGRID': 'POWERGRID', 'NTPC': 'NTPC', 'ADANIPORTS': 'ADANIPORTS',
    'ONGC': 'ONGC', 'DIVISLAB': 'DIVISLAB', 'BRITANNIA': 'BRITANNIA',
    'DABUR': 'DABUR'
}

# ============================================
# 1. FII/DII DATA (Foreign/Domestic Institutional)
# ============================================
def get_fii_dii_data():
    """Get FII/DII investment data from NSE"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        
        # NSE FII/DII data
        url = "https://www.nseindia.com/api/fii-dii-activity"
        session.get("https://www.nseindia.com", timeout=5)
        response = session.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            recent_data = data[-5:] if len(data) > 5 else data
            
            fii_signal = 'NEUTRAL'
            dii_signal = 'NEUTRAL'
            
            if recent_data:
                last = recent_data[-1]
                fii_net = float(last.get('netValue', 0))
                dii_net = float(last.get('diiNetValue', 0))
                
                if fii_net > 500: fii_signal = '🟢 BULLISH (Buying)'
                elif fii_net > 0: fii_signal = '🔵 SLIGHT BUY'
                elif fii_net > -500: fii_signal = '🟡 SLIGHT SELL'
                else: fii_signal = '🔴 BEARISH (Heavy Selling)'
                
                if dii_net > 500: dii_signal = '🟢 BUYING'
                elif dii_net > 0: dii_signal = '🔵 SLIGHT BUY'
                elif dii_net > -500: dii_signal = '🟡 SLIGHT SELL'
                else: dii_signal = '🔴 SELLING'
                
                return {
                    'fii_signal': fii_signal,
                    'dii_signal': dii_signal,
                    'fii_net': f"{fii_net:.0f} Cr",
                    'dii_net': f"{dii_net:.0f} Cr",
                    'date': last.get('date', 'Today')
                }
    except:
        pass
    
    return {'fii_signal': '📌 Data Unavailable', 'dii_signal': '', 'fii_net': '', 'dii_net': ''}

# ============================================
# 2. INSIDER TRADING DETECTION
# ============================================
def check_insider_trading(symbol):
    """Check recent insider trading activity"""
    try:
        # Check BSE insider trading data
        url = f"https://www.bseindia.com/corporates/Insider_Trading.aspx?expandable=1&scripcd={symbol}"
        response = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        
        # Simple keyword check on the page
        text = response.text.lower()
        
        if 'acquisition' in text or 'buy' in text:
            # Check for positive patterns
            insider_score = 5
            status = '🔵 PROMOTER BUYING'
        elif 'sale' in text or 'disposal' in text:
            insider_score = -15
            status = '⚠️ PROMOTER SELLING'
        else:
            insider_score = 0
            status = '📌 NO ACTIVITY'
        
        return {'score': insider_score, 'status': status}
        
    except:
        return {'score': 0, 'status': '📌 Data Unavailable'}

# ============================================
# 3. TECHNICAL PATTERN DETECTION
# ============================================
def detect_patterns(price, high, low, open_price, prev_close, high_52, low_52):
    """Detect candlestick and technical patterns"""
    patterns = []
    pattern_score = 0
    
    # Body and wicks
    body = abs(price - open_price)
    upper_wick = high - max(price, open_price)
    lower_wick = min(price, open_price) - low
    total_range = high - low
    
    if total_range == 0:
        return {'patterns': ['No pattern'], 'score': 0}
    
    body_ratio = body / total_range
    
    # Doji (Indecision → Potential Reversal)
    if body_ratio < 0.1:
        patterns.append("🕯️ Doji - Reversal possible")
        pattern_score += 5
    
    # Hammer (Bullish Reversal)
    if lower_wick > body * 2 and upper_wick < body * 0.5 and price > open_price:
        patterns.append("🔨 Hammer - Bullish reversal")
        pattern_score += 12
    
    # Shooting Star (Bearish Reversal)
    if upper_wick > body * 2 and lower_wick < body * 0.5 and price < open_price:
        patterns.append("🌠 Shooting Star - Bearish signal")
        pattern_score -= 8
    
    # Bullish Engulfing
    if price > open_price and open_price < prev_close and price > prev_close:
        patterns.append("📈 Bullish Engulfing - Strong buy")
        pattern_score += 15
    
    # Bearish Engulfing
    if price < open_price and open_price > prev_close and price < prev_close:
        patterns.append("📉 Bearish Engulfing - Caution")
        pattern_score -= 10
    
    # Near 52-Week High (Breakout potential)
    if (high_52 - price) / high_52 < 0.05:
        patterns.append("🚀 Near 52W High - Breakout watch")
        pattern_score += 10
    
    # Near 52-Week Low (Value zone)
    if (price - low_52) / low_52 < 0.05:
        patterns.append("💎 Near 52W Low - Value zone")
        pattern_score += 8
    
    # Gap Up
    if open_price > prev_close * 1.01:
        patterns.append("⬆️ Gap Up - Momentum")
        pattern_score += 8
    
    # Gap Down
    if open_price < prev_close * 0.99:
        patterns.append("⬇️ Gap Down - Weakness")
        pattern_score -= 5
    
    if not patterns:
        patterns.append("📊 No clear pattern")
    
    return {
        'patterns': patterns[:3],
        'score': pattern_score
    }

# ============================================
# 4. VOLUME ANALYSIS
# ============================================
def volume_analysis(symbol, price):
    """Analyze volume patterns"""
    try:
        # Get volume data from NSE
        nse = Nse()
        q = nse.get_quote(symbol)
        
        if not q:
            return {'delivery': 'Unknown', 'signal': '📌 N/A', 'score': 0}
        
        total_vol = float(q.get('totalTradedVolume', 0))
        delivery_qty = float(q.get('deliveryQuantity', 0))
        delivery_pct = (delivery_qty / total_vol * 100) if total_vol > 0 else 0
        
        # Volume analysis
        if delivery_pct > 60:
            signal = '🟢 STRONG HANDS (Delivery 60%+)'
            score = 12
        elif delivery_pct > 45:
            signal = '🔵 GOOD ACCUMULATION'
            score = 8
        elif delivery_pct > 30:
            signal = '🟡 AVERAGE'
            score = 3
        else:
            signal = '🔴 SPECULATIVE (Low delivery)'
            score = -5
        
        return {
            'delivery': f"{delivery_pct:.0f}%",
            'signal': signal,
            'score': score,
            'total_volume': f"{total_vol/100000:.1f}L" if total_vol > 0 else '0'
        }
        
    except:
        return {'delivery': 'N/A', 'signal': '📌 Data Unavailable', 'score': 0}

# ============================================
# 5. OPTIONS DATA (PCR, Max Pain, OI)
# ============================================
def get_options_data():
    """Get Nifty options data for market sentiment"""
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        
        # Get Nifty options chain
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        session.get("https://www.nseindia.com", timeout=5)
        response = session.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            records = data.get('records', {}).get('data', [])
            
            # Calculate PCR (Put-Call Ratio)
            total_put_oi = 0
            total_call_oi = 0
            
            for record in records[:50]:
                if 'CE' in record:
                    total_call_oi += record['CE'].get('openInterest', 0)
                if 'PE' in record:
                    total_put_oi += record['PE'].get('openInterest', 0)
            
            if total_call_oi > 0:
                pcr = total_put_oi / total_call_oi
                
                if pcr > 1.5: signal = '🟢 VERY BULLISH'
                elif pcr > 1.2: signal = '🔵 BULLISH'
                elif pcr > 0.8: signal = '🟡 NEUTRAL'
                elif pcr > 0.5: signal = '🟠 BEARISH'
                else: signal = '🔴 VERY BEARISH'
                
                return {
                    'pcr': f"{pcr:.2f}",
                    'signal': signal,
                    'score': (pcr - 0.8) * 15  # Score adjustment
                }
    except:
        pass
    
    return {'pcr': 'N/A', 'signal': '📌 Data Unavailable', 'score': 0}

# ============================================
# NEWS CRUX (Enhanced)
# ============================================
def fetch_news_crux(symbol):
    """Fetch news and create crux points"""
    try:
        news_items = []
        
        # Google News
        try:
            url = f"https://news.google.com/rss/search?q={symbol}+share+stock+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en"
            response = requests.get(url, timeout=8)
            from xml.etree import ElementTree
            root = ElementTree.fromstring(response.content)
            
            for item in root.findall('.//item')[:15]:
                title = item.find('title').text if item.find('title') is not None else ""
                title = re.sub(r'[^\w\s\-.,%₹$&]', '', title)
                title = title.replace(symbol, '').strip()
                if len(title) > 20:
                    news_items.append({'title': title})
        except:
            pass
        
        if not news_items:
            return {'crux': ['📌 No significant news'], 'sentiment': '🟡 NEUTRAL', 'score': 0}
        
        # Sentiment keywords
        positive = ['profit', 'growth', 'rise', 'gain', 'upgrade', 'strong', 'record',
                   'boost', 'expansion', 'launch', 'partnership', 'dividend', 'buyback',
                   'contract', 'order', 'beat', 'outperform', 'rally', 'surge']
        negative = ['loss', 'fall', 'drop', 'decline', 'downgrade', 'weak', 'probe',
                   'fraud', 'scam', 'penalty', 'fine', 'debt', 'default', 'arrest',
                   'raid', 'crash', 'lawsuit', 'crisis', 'layoff', 'resign']
        
        scored = []
        for news in news_items:
            title_lower = news['title'].lower()
            pos = sum(1 for w in positive if w in title_lower)
            neg = sum(1 for w in negative if w in title_lower)
            scored.append({'title': news['title'][:120], 'score': pos - neg})
        
        scored.sort(key=lambda x: abs(x['score']), reverse=True)
        
        # Create crux
        crux = []
        used = set()
        for news in scored:
            key_words = ' '.join(news['title'].lower().split()[:5])
            if key_words not in used and len(crux) < 4:
                used.add(key_words)
                prefix = "✅" if news['score'] > 0 else "⚠️" if news['score'] < 0 else "📌"
                crux.append(f"{prefix} {news['title']}")
        
        # Overall sentiment
        avg = sum(n['score'] for n in scored) / len(scored) if scored else 0
        
        if avg > 2: sentiment = '🟢 VERY POSITIVE'
        elif avg > 0.5: sentiment = '🔵 POSITIVE'
        elif avg > -0.5: sentiment = '🟡 NEUTRAL'
        elif avg > -2: sentiment = '🟠 NEGATIVE'
        else: sentiment = '🔴 VERY NEGATIVE'
        
        return {'crux': crux if crux else ['📌 No significant news'], 'sentiment': sentiment, 'score': avg * 6}
        
    except:
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
    
    # Get Market-wide data (run once)
    print("📊 Fetching market data...")
    fii_dii = get_fii_dii_data()
    options = get_options_data()
    
    all_symbols = []
    for sector, symbols in STOCKS.items():
        all_symbols.extend(symbols)
    
    print(f"🔄 Analyzing {len(all_symbols)} stocks with ALL indicators...")
    
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
            open_price = float(q.get('open', 0))
            change_pct = float(q.get('pChange', 0))
            vwap = float(q.get('vwap', 0)) if q.get('vwap') else 0
            high_52 = float(weekly.get('max', 0))
            low_52 = float(weekly.get('min', 0))
            prev_close = float(q.get('previousClose', 0))
            
            # 1. TECHNICAL PATTERNS (15 points)
            patterns = detect_patterns(price, high, low, open_price, prev_close, high_52, low_52)
            
            # 2. VOLUME ANALYSIS (12 points)
            volume_data = volume_analysis(symbol, price)
            
            # 3. INSIDER TRADING (15 points)
            insider = check_insider_trading(symbol)
            
            # 4. NEWS SENTIMENT (20 points)
            news = fetch_news_crux(symbol)
            
            # 5. BASIC TECHNICAL (20 points)
            tech_score = 0
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            if 50 < pos < 80: tech_score += 8
            elif pos < 30: tech_score += 6
            
            dist_high = ((high_52 - price) / high_52 * 100) if high_52 > 0 else 0
            dist_low = ((price - low_52) / low_52 * 100) if low_52 > 0 else 0
            if dist_high > 20: tech_score += 7
            if dist_low < 10: tech_score += 5
            
            vs_vwap = ((price - vwap) / vwap * 100) if vwap > 0 else 0
            if 0 < vs_vwap < 2: tech_score += 5
            
            # 6. MOMENTUM (10 points)
            momentum = 0
            if 0.5 < change_pct < 2: momentum += 6
            elif -2 < change_pct < 0: momentum += 4
            if price > vwap: momentum += 4
            
            # ===== GRAND TOTAL SCORE =====
            total_score = (
                patterns['score'] * 0.15 +    # Technical Patterns
                volume_data['score'] * 0.12 +  # Volume
                insider['score'] * 0.15 +      # Insider Trading
                news['score'] * 0.20 +         # News Sentiment
                tech_score * 0.20 +            # Basic Technical
                momentum * 0.10 +              # Momentum
                options['score'] * 0.08        # Market Sentiment (PCR)
            )
            
            # Add base score and normalize
            total_score = max(5, min(95, total_score + 25))
            
            # Penalties for negative signals
            if insider['status'] == '⚠️ PROMOTER SELLING':
                total_score = min(total_score, 45)
            if news['sentiment'] == '🔴 VERY NEGATIVE':
                total_score = min(total_score, 35)
            
            target = round(price * (1 + total_score / 100), 2)
            stop_loss = round(price * 0.95, 2)
            
            if total_score >= 80: action = "STRONG BUY 💪"
            elif total_score >= 65: action = "BUY ✅"
            elif total_score >= 50: action = "ACCUMULATE 📥"
            elif total_score >= 35: action = "WATCH 👀"
            else: action = "AVOID ❌"
            
            sector = next((sec for sec, syms in STOCKS.items() if symbol in syms), "Other")
            
            results.append({
                'symbol': symbol, 'sector': sector, 'price': price,
                'score': total_score, 'action': action,
                'target': target, 'stop_loss': stop_loss,
                'change_pct': change_pct,
                'patterns': patterns['patterns'],
                'volume': volume_data,
                'insider': insider['status'],
                'news_crux': news['crux'],
                'news_sentiment': news['sentiment']
            })
            
            print(f"  {symbol}: ₹{price:.0f} | Score: {total_score:.0f} | {action}")
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  {symbol}: ⚠️ {str(e)[:30]}")
    
    if not results:
        send_telegram("❌ Analysis failed.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # ===== BUILD ULTIMATE MESSAGE =====
    strong = len([r for r in results if r['score'] >= 80])
    buy = len([r for r in results if 65 <= r['score'] < 80])
    watch = len([r for r in results if 50 <= r['score'] < 65])
    
    # HEADER
    message = f"🔬 <b>INSTITUTIONAL GRADE ANALYSIS</b>\n"
    message += f"📅 {ist_date} | ⏰ {ist_time} IST\n"
    message += f"{'═'*35}\n\n"
    
    # MARKET CONTEXT
    message += f"🏦 <b>MARKET CONTEXT</b>\n"
    message += f"{'─'*35}\n"
    if fii_dii:
        message += f"🌍 FII: {fii_dii['fii_signal']} ({fii_dii.get('fii_net', '')})\n"
        message += f"🏠 DII: {fii_dii['dii_signal']} ({fii_dii.get('dii_net', '')})\n"
    if options:
        message += f"📊 Nifty PCR: {options['pcr']} - {options['signal']}\n"
    message += f"📈 Analyzed: {len(results)} | 🟢{strong} 🔵{buy} 🟡{watch}\n\n"
    
    # TOP PICKS
    message += f"🎯 <b>TOP 5 PICKS (All Factors)</b>\n"
    message += f"{'═'*35}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        emoji = "🟢" if r['score'] >= 80 else "🔵" if r['score'] >= 65 else "🟡"
        
        message += f"{emoji} <b>{i}. {r['symbol']}</b> | {r['sector']}\n"
        message += f"💰 ₹{r['price']:.0f} → 🎯 ₹{r['target']:.0f} (+{gain:.0f}%) | {r['action']}\n"
        message += f"📊 Score: {r['score']:.0f}/100\n"
        
        # Key indicators
        message += f"📰 News: {r['news_sentiment']}\n"
        if r['patterns']:
            message += f"📈 Pattern: {r['patterns'][0]}\n"
        message += f"📦 Delivery: {r['volume'].get('delivery', 'N/A')} | {r['volume'].get('signal', '')}\n"
        message += f"👤 Insider: {r['insider']}\n"
        
        # News crux
        if r['news_crux']:
            message += f"📋 <b>Key Crux:</b>\n"
            for crux in r['news_crux'][:2]:
                message += f"   {crux}\n"
        
        message += f"🛑 Stop Loss: ₹{r['stop_loss']:.0f}\n\n"
    
    # CAUTION CORNER
    bad_crux = [r for r in results if r['insider'] == '⚠️ PROMOTER SELLING' or 
                r['news_sentiment'] in ['🔴 VERY NEGATIVE', '🟠 NEGATIVE']]
    if bad_crux:
        message += f"⚠️ <b>CAUTION: Red Flags</b>\n{'─'*35}\n"
        for r in bad_crux[:3]:
            message += f"🔴 <b>{r['symbol']}</b>: {r['insider']} | {r['news_sentiment']}\n"
        message += "\n"
    
    # FOOTER
    message += f"{'═'*35}\n"
    message += f"🔬 <i>Multi-Factor: Tech + FII/DII + Options + Insider + Delivery + News</i>\n"
    message += f"⚠️ <i>Verify independently. Use strict stop loss.</i>"
    
    send_telegram(message)
    print("✅ Ultimate Analysis sent!")

if __name__ == "__main__":
    analyze()
