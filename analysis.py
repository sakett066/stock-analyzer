"""
██████╗ ██████╗  ██████╗     ████████╗██████╗  █████╗ ██████╗ ███████╗██████╗ 
██╔══██╗██╔══██╗██╔═══██╗    ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗
██████╔╝██████╔╝██║   ██║       ██║   ██████╔╝███████║██║  ██║█████╗  ██████╔╝
██╔═══╝ ██╔══██╗██║   ██║       ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ██╔══██╗
██║     ██║  ██║╚██████╔╝       ██║   ██║  ██║██║  ██║██████╔╝███████╗██║  ██║
╚═╝     ╚═╝  ╚═╝ ╚═════╝        ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝
PROFESSIONAL TRADING SYSTEM v4.0
Entry + Exit + Position Sizing + Trailing Stop + Market Regime + Risk Detection
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime, timedelta
import re
from xml.etree import ElementTree

os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

STOCKS = {
    '🖥️ IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM'],
    '🏦 Banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK'],
    '🏗️ Infra': ['LT', 'ADANIPORTS', 'HAL', 'BEL'],
    '🏭 Industry': ['RELIANCE', 'TATASTEEL', 'JSWSTEEL'],
    '💊 Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB'],
    '🛒 Consumer': ['ITC', 'HINDUNILVR', 'TITAN', 'DMART', 'TRENT'],
    '🚗 Auto': ['MARUTI', 'TATAMOTORS', 'M&M'],
    '⚡ Energy': ['POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER'],
    '💰 Finance': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN'],
    '🔧 Others': ['ASIANPAINT', 'PIDILITIND', 'IRCTC']
}

# ============================================
# MARKET REGIME DETECTOR
# ============================================
def get_market_regime():
    """Detect Bull/Bear/Neutral market"""
    try:
        nse = Nse()
        q = nse.get_quote('NIFTY 50')
        if not q:
            q = nse.get_quote('RELIANCE')
        
        price = float(q.get('lastPrice', 0))
        weekly = q.get('weekHighLow', {})
        high_52 = float(weekly.get('max', 0))
        
        if high_52 > 0:
            dist_from_high = ((high_52 - price) / high_52) * 100
            
            if dist_from_high < 5:
                return '🟢 BULL MARKET', 1.0
            elif dist_from_high < 15:
                return '🔵 MODERATE BULL', 0.8
            elif dist_from_high < 30:
                return '🟡 NEUTRAL', 0.6
            elif dist_from_high < 45:
                return '🟠 BEAR MARKET', 0.4
            else:
                return '🔴 DEEP BEAR', 0.2
    except:
        pass
    return '🟡 NEUTRAL', 0.6

# ============================================
# POSITION SIZE CALCULATOR
# ============================================
def calculate_position(capital, entry, stop_loss, risk_percent=2):
    """Calculate exact position size"""
    risk_amount = capital * (risk_percent / 100)
    risk_per_share = abs(entry - stop_loss)
    
    if risk_per_share == 0:
        return 0, 0
    
    quantity = int(risk_amount / risk_per_share)
    investment = quantity * entry
    
    max_investment = capital * 0.20
    if investment > max_investment:
        quantity = int(max_investment / entry)
        investment = quantity * entry
    
    return quantity, investment

# ============================================
# TRAILING STOP LOSS
# ============================================
def calculate_trailing_stop(entry, current, highest, stage):
    """Dynamic trailing stop loss"""
    profit_pct = ((current - entry) / entry) * 100
    
    if profit_pct < 5:
        return entry * 0.95
    elif profit_pct < 10:
        return entry
    elif profit_pct < 20:
        return current * 0.95
    elif profit_pct < 35:
        return current * 0.92
    elif profit_pct < 50:
        return current * 0.90
    else:
        return current * 0.85

# ============================================
# EXIT STRATEGY
# ============================================
def get_exit_strategy(score, entry, target):
    """Generate exit plan with actual prices"""
    
    if score >= 80:
        return {
            'first': f"Book 30% at ₹{entry * 1.25:.0f} (+25%)",
            'second': f"Book 40% at ₹{entry * 1.50:.0f} (+50%)",
            'final': f"Trail 25% on remaining above ₹{entry * 1.50:.0f}",
            'stop': f"Initial SL ₹{entry * 0.95:.0f} (-5%), Trail after +10%"
        }
    elif score >= 65:
        return {
            'first': f"Book 40% at ₹{entry * 1.20:.0f} (+20%)",
            'second': f"Book 40% at ₹{entry * 1.40:.0f} (+40%)",
            'final': f"Hold balance till ₹{entry * 1.60:.0f} (+60%)",
            'stop': f"SL ₹{entry * 0.95:.0f} (-5%), Breakeven at +8%"
        }
    elif score >= 55:
        return {
            'first': f"Book 50% at ₹{entry * 1.15:.0f} (+15%)",
            'second': f"Exit balance at ₹{entry * 1.25:.0f} (+25%)",
            'final': f"Re-enter above ₹{entry * 1.30:.0f}",
            'stop': f"Strict SL ₹{entry * 0.96:.0f} (-4%)"
        }
    elif score >= 40:
        return {
            'first': f"Exit 100% at ₹{entry * 1.10:.0f} (+10%)",
            'second': f"Re-enter if breaks ₹{entry * 1.15:.0f}",
            'final': f"Wait for score >55",
            'stop': f"Strict SL ₹{entry * 0.97:.0f} (-3%)"
        }
    else:
        return {
            'first': f"SKIP - Score too low ({score:.1f})",
            'second': "Wait for better setup",
            'final': "Check next analysis",
            'stop': "Do not trade"
        }

# ============================================
# RISK DETECTION (FDA, Regulatory, Fraud)
# ============================================
def detect_risk_events(symbol):
    """Detect high-risk events: FDA recalls, fraud, regulatory action"""
    risk_flags = []
    risk_score = 0
    
    try:
        risk_queries = [
            f"{symbol} FDA recall drug quality",
            f"{symbol} SEBI investigation fraud penalty",
            f"{symbol} regulatory fine ban arrest"
        ]
        
        for query in risk_queries[:2]:
            try:
                url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
                resp = requests.get(url, timeout=5)
                root = ElementTree.fromstring(resp.content)
                
                for item in root.findall('.//item')[:5]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    title_lower = title.lower()
                    
                    if any(w in title_lower for w in ['recall', 'fda', 'warning letter', 'quality issue']):
                        risk_flags.append(f"🚨 FDA/RECALL: {title[:100]}")
                        risk_score += 25
                    
                    if any(w in title_lower for w in ['fraud', 'scam', 'investigation', 'sebi', 'cbi', 'ed']):
                        risk_flags.append(f"⚠️ INVESTIGATION: {title[:100]}")
                        risk_score += 20
                    
                    if any(w in title_lower for w in ['penalty', 'fine', 'ban', 'suspended']):
                        risk_flags.append(f"💰 PENALTY: {title[:100]}")
                        risk_score += 15
                    
                    if any(w in title_lower for w in ['resign', 'arrest', 'raid', 'ceo']):
                        risk_flags.append(f"👤 MANAGEMENT: {title[:100]}")
                        risk_score += 20
                    
                    if any(w in title_lower for w in ['debt', 'default', 'bankruptcy', 'insolvency']):
                        risk_flags.append(f"💸 FINANCIAL: {title[:100]}")
                        risk_score += 15
            except:
                pass
    except:
        pass
    
    risk_score = min(100, risk_score)
    
    if risk_score >= 40:
        risk_level = '🔴 HIGH RISK'
    elif risk_score >= 20:
        risk_level = '🟠 MEDIUM RISK'
    elif risk_score >= 10:
        risk_level = '🟡 LOW RISK'
    else:
        risk_level = '🟢 CLEAN'
    
    return {'flags': risk_flags[:3], 'score': risk_score, 'level': risk_level}

# ============================================
# MARKET CONTEXT
# ============================================
def get_market_context():
    """FII/DII + Options + Nifty"""
    context = {}
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        session.get("https://www.nseindia.com", timeout=5)
        
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
            pass
        
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
                    context['pcr'] = f"📊 PCR: {pcr:.2f} ({signal})"
        except:
            pass
    except:
        pass
    return context

# ============================================
# NEWS ANALYSIS
# ============================================
def get_news_analysis(symbol):
    try:
        all_news = []
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
        
        all_news = list(set(all_news))
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
        
        crux, seen = [], set()
        for news in scored:
            key = ' '.join(news['title'].lower().split()[:3])
            if key not in seen and len(crux) < 3:
                seen.add(key)
                prefix = "✅" if news['score'] > 0 else "⚠️" if news['score'] < 0 else "📌"
                crux.append(f"{prefix} {news['title']}")
        
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
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts[:3]:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': part, 'parse_mode': 'HTML'}, timeout=10)
            time.sleep(0.5)
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
    day = now.strftime('%A')
    
    print(f"\n{'='*60}")
    print(f"🚀 PRO TRADING SYSTEM v4.0")
    print(f"📅 {day}, {ist_date} | ⏰ {ist_time}")
    print(f"{'='*60}")
    
    regime, regime_multiplier = get_market_regime()
    print(f"📊 Market Regime: {regime} (Multiplier: {regime_multiplier}x)")
    
    market = get_market_context()
    
    all_stocks = [(sym, sec) for sec, syms in STOCKS.items() for sym in syms]
    print(f"🔄 Analyzing {len(all_stocks)} stocks with Risk Detection...\n")
    
    for symbol, sector in all_stocks:
        try:
            q = nse.get_quote(symbol)
            if not q: continue
            
            intraday = q.get('intraDayHighLow', {})
            weekly = q.get('weekHighLow', {})
            
            price = float(q.get('lastPrice', 0))
            if price == 0: continue
            
            high = float(intraday.get('max', 0))
            low = float(intraday.get('min', 0))
            open_price = float(q.get('open', 0))
            change_pct = float(q.get('pChange', 0))
            vwap = float(q.get('vwap', 0)) if q.get('vwap') else 0
            high_52 = float(weekly.get('max', 0))
            low_52 = float(weekly.get('min', 0))
            prev_close = float(q.get('previousClose', 0))
            
            # SCORING
            value_score = 0
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            
            if 50 < pos < 80: value_score += 10
            elif 30 <= pos <= 50: value_score += 7
            elif pos < 30: value_score += 8
            
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
            
            momentum_score = 0
            if 1 < change_pct < 3: momentum_score += 12
            elif 0.5 < change_pct <= 1: momentum_score += 10
            elif 0 < change_pct <= 0.5: momentum_score += 8
            elif -1 < change_pct <= 0: momentum_score += 7
            elif -3 < change_pct <= -1: momentum_score += 5
            
            gap = ((open_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            if 0 < gap < 1: momentum_score += 8
            if price > vwap > 0: momentum_score += 5
            
            smart_score, delivery_info = 0, ""
            try:
                delivery_qty = float(q.get('deliveryQuantity', 0))
                total_vol = float(q.get('totalTradedVolume', 1))
                delivery_pct = (delivery_qty / total_vol * 100) if total_vol > 0 else 0
                
                if delivery_pct > 65: smart_score, delivery_info = 18, f"🟢 {delivery_pct:.0f}% Strong"
                elif delivery_pct > 50: smart_score, delivery_info = 14, f"🔵 {delivery_pct:.0f}% Good"
                elif delivery_pct > 40: smart_score, delivery_info = 10, f"🟡 {delivery_pct:.0f}% Avg"
                elif delivery_pct > 25: smart_score, delivery_info = 5, f"🟠 {delivery_pct:.0f}% Low"
                else: delivery_info = f"🔴 {delivery_pct:.0f}% Weak"
            except:
                delivery_info = "📌 N/A"
            
            news = get_news_analysis(symbol)
            
            # RISK DETECTION
            risk = detect_risk_events(symbol)
            
            tech_bonus = 0
            if price > open_price and open_price > prev_close: tech_bonus += 2
            if price > vwap > 0: tech_bonus += 1
            if pos > 60: tech_bonus += 2
            
            # TOTAL SCORE
            raw_score = value_score + momentum_score + smart_score + news['score'] + tech_bonus
            raw_score = raw_score + 12
            
            if regime_multiplier < 0.6:
                total_score = round(max(10, min(95, raw_score * regime_multiplier)), 1)
            else:
                total_score = round(max(10, min(95, raw_score)), 1)
            
            # News sentiment caps
            if news['sentiment'] == '🔴 Very Negative': total_score = min(total_score, 35)
            elif news['sentiment'] == '🟠 Negative': total_score = min(total_score, 55)
            
            # RISK PENALTY
            if risk['score'] >= 40:
                total_score = min(total_score, 45)
            elif risk['score'] >= 20:
                total_score = min(total_score, 65)
                total_score = total_score - 10
            
            # PRICE TARGETS
            if total_score >= 80: target_mult = 1.8
            elif total_score >= 65: target_mult = 1.5
            elif total_score >= 50: target_mult = 1.3
            else: target_mult = 1.15
            
            entry_price = price
            target_price = round(price * target_mult, 0)
            stop_loss = round(price * 0.95, 0)
            
            capital = 100000
            quantity, investment = calculate_position(capital, entry_price, stop_loss)
            quantity = max(1, quantity)
            investment = quantity * entry_price
            
            exit_plan = get_exit_strategy(total_score, entry_price, target_price)
            trailing_stop = calculate_trailing_stop(entry_price, entry_price, entry_price, 0)
            
            if total_score >= 80: action, stars, conf = "💪 STRONG BUY", "⭐⭐⭐⭐⭐", "HIGH"
            elif total_score >= 65: action, stars, conf = "✅ BUY", "⭐⭐⭐⭐", "GOOD"
            elif total_score >= 55: action, stars, conf = "📥 ACCUMULATE", "⭐⭐⭐", "MODERATE"
            elif total_score >= 40: action, stars, conf = "👀 WATCH", "⭐⭐", "LOW"
            else: action, stars, conf = "❌ SKIP", "⭐", "NONE"
            
            results.append({
                'symbol': symbol, 'sector': sector, 'price': price,
                'score': total_score, 'stars': stars, 'action': action,
                'target': target_price, 'stop_loss': stop_loss,
                'quantity': quantity, 'investment': investment,
                'exit_plan': exit_plan, 'trailing_stop': trailing_stop,
                'delivery': delivery_info, 'news_sentiment': news['sentiment'],
                'news_crux': news['crux'], 'confidence': conf,
                'change_pct': change_pct,
                'risk_level': risk['level'], 'risk_flags': risk['flags']
            })
            
            risk_tag = f"⚠️{risk['level']}" if risk['score'] >= 20 else ""
            print(f"  {symbol:15} ₹{price:>8.0f} | Score: {total_score:>5.1f} | Qty: {quantity:>4} | {stars} {risk_tag}")
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  {symbol}: ⚠️ {str(e)[:30]}")
    
    if not results:
        send_telegram("❌ No data available.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    strong = len([r for r in results if r['score'] >= 80])
    buy = len([r for r in results if 65 <= r['score'] < 80])
    acc = len([r for r in results if 55 <= r['score'] < 65])
    risky = len([r for r in results if r['risk_level'] in ['🔴 HIGH RISK', '🟠 MEDIUM RISK']])
    
    message = f"🚀 <b>PRO TRADING SYSTEM v4.0</b>\n"
    message += f"📅 {day}, {ist_date} | ⏰ {ist_time} IST\n"
    message += f"📊 Regime: {regime}\n"
    message += f"{'═'*35}\n\n"
    
    if market:
        message += f"🏦 <b>MARKET</b>\n{'─'*35}\n"
        for v in market.values():
            message += f"{v}\n"
        message += "\n"
    
    message += f"📈 <b>SCREENED: {len(results)} STOCKS</b>\n"
    message += f"├ 💪 Strong Buy: {strong} | ✅ Buy: {buy} | 📥 Accumulate: {acc}\n"
    if risky > 0:
        message += f"└ 🚨 Risk Flags: {risky} stocks\n\n"
    else:
        message += f"└ 🛡️ All Clean\n\n"
    
    message += f"🎯 <b>TOP 5 PICKS WITH TRADING PLAN</b>\n{'═'*35}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        emoji = "🟢" if r['score'] >= 80 else "🔵" if r['score'] >= 65 else "🟡"
        
        message += f"{emoji} <b>#{i} {r['symbol']}</b> | {r['sector']}\n"
        message += f"{'─'*35}\n"
        message += f"📊 <b>Score:</b> {r['score']}/100 | {r['stars']} | {r['action']}\n"
        
        if r['risk_level'] != '🟢 CLEAN':
            message += f"🛡️ <b>Risk:</b> {r['risk_level']}\n"
        
        message += f"\n💰 <b>TRADE SETUP:</b>\n"
        message += f"   Entry: ₹{r['price']:.2f}\n"
        message += f"   Target: ₹{r['target']:.2f} (+{gain:.0f}%)\n"
        message += f"   Stop Loss: ₹{r['stop_loss']:.2f} (-5%)\n\n"
        
        message += f"📦 <b>POSITION:</b>\n"
        message += f"   Quantity: {r['quantity']} shares\n"
        message += f"   Investment: ₹{r['investment']:,.0f}\n"
        message += f"   Max Risk: ₹{r['quantity'] * (r['price'] - r['stop_loss']):,.0f}\n\n"
        
        message += f"🚪 <b>EXIT PLAN:</b>\n"
        message += f"   1️⃣ {r['exit_plan']['first']}\n"
        message += f"   2️⃣ {r['exit_plan']['second']}\n"
        message += f"   3️⃣ {r['exit_plan']['final']}\n"
        message += f"   🛑 {r['exit_plan']['stop']}\n\n"
        
        if r['risk_flags']:
            message += f"🚨 <b>RISK ALERTS:</b>\n"
            for flag in r['risk_flags'][:2]:
                message += f"   {flag}\n"
            message += "\n"
        
        message += f"📰 <b>NEWS:</b> {r['news_sentiment']} | 📦 {r['delivery']}\n"
        if r['news_crux']:
            for crux in r['news_crux'][:2]:
                message += f"   {crux}\n"
        message += "\n"
    
    message += f"{'═'*35}\n"
    message += f"⚠️ <i>Paper trade first. Start small. Strict stop loss.</i>\n"
    message += f"🛡️ <i>Risk detection active - FDA/Regulatory/Fraud flags</i>"
    
    send_telegram(message)
    
    print(f"\n✅ PRO Analysis Complete!")
    print(f"🏆 #1: {results[0]['symbol']} | Score: {results[0]['score']}/100")
    print(f"📊 Qty: {results[0]['quantity']} shares | Invest: ₹{results[0]['investment']:,.0f}")
    print(f"📊 🟢{strong} 🔵{buy} 🟡{acc} 🚨{risky}")

if __name__ == "__main__":
    analyze()
