"""
PRO TRADING SYSTEM v4.0 - Complete with News, Exit Plan, Position Sizing, Risk Detection
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime
import re
from xml.etree import ElementTree

os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

STOCKS = {
    'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM'],
    'Banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK'],
    'Infra': ['LT', 'ADANIPORTS', 'HAL', 'BEL'],
    'Industry': ['RELIANCE', 'TATASTEEL', 'JSWSTEEL'],
    'Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB'],
    'Consumer': ['ITC', 'HINDUNILVR', 'TITAN', 'DMART', 'TRENT'],
    'Auto': ['MARUTI', 'TATAMOTORS', 'M&M'],
    'Energy': ['POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER'],
    'Finance': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN'],
    'Others': ['ASIANPAINT', 'PIDILITIND', 'IRCTC']
}

def get_market_regime():
    try:
        nse = Nse()
        q = nse.get_quote('RELIANCE')
        price = float(q.get('lastPrice', 0))
        weekly = q.get('weekHighLow', {})
        high_52 = float(weekly.get('max', 0))
        if high_52 > 0:
            dist = ((high_52 - price) / high_52) * 100
            if dist < 5: return 'BULL MARKET', 1.0
            elif dist < 15: return 'MODERATE BULL', 0.8
            elif dist < 30: return 'NEUTRAL', 0.6
            elif dist < 45: return 'BEAR MARKET', 0.4
            else: return 'DEEP BEAR', 0.2
    except: pass
    return 'NEUTRAL', 0.6

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
                    if len(title) > 20: all_news.append(title)
            except: pass
        
        if not all_news:
            return {'crux': ['No significant news today'], 'sentiment': 'Neutral', 'score': 8}
        
        all_news = list(set(all_news))
        pos_w = ['profit', 'growth', 'revenue', 'rise', 'gain', 'upgrade', 'strong',
                 'record', 'boost', 'expansion', 'dividend', 'buyback', 'contract',
                 'order', 'beat', 'rally', 'surge', 'bullish', 'recovery']
        neg_w = ['loss', 'fall', 'drop', 'decline', 'downgrade', 'weak', 'probe',
                 'fraud', 'scam', 'penalty', 'debt', 'default', 'crash', 'concern',
                 'risk', 'lawsuit', 'crisis', 'negative']
        
        scored = []
        for title in all_news:
            tl = title.lower()
            ps = sum(1 for w in pos_w if w in tl)
            ns = sum(1 for w in neg_w if w in tl)
            scored.append({'title': title[:120], 'score': ps - ns})
        
        scored.sort(key=lambda x: abs(x['score']), reverse=True)
        
        crux, seen = [], set()
        for news in scored:
            key = ' '.join(news['title'].lower().split()[:4])
            if key not in seen and len(crux) < 3:
                seen.add(key)
                if news['score'] > 0: crux.append(f"+ {news['title']}")
                elif news['score'] < 0: crux.append(f"- {news['title']}")
                else: crux.append(f"~ {news['title']}")
        
        avg = sum(n['score'] for n in scored) / len(scored)
        if avg > 1.5: sentiment, sc = 'Very Positive', 14
        elif avg > 0.3: sentiment, sc = 'Positive', 11
        elif avg > -0.3: sentiment, sc = 'Neutral', 8
        elif avg > -1.5: sentiment, sc = 'Negative', 4
        else: sentiment, sc = 'Very Negative', 1
        
        return {'crux': crux if crux else ['No clear news direction'], 'sentiment': sentiment, 'score': sc}
    except:
        return {'crux': ['News unavailable'], 'sentiment': 'Neutral', 'score': 8}

def detect_risk(symbol):
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+FDA+recall+fraud+investigation+penalty+default&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=5)
        root = ElementTree.fromstring(resp.content)
        
        risk_score = 0
        flags = []
        
        for item in root.findall('.//item')[:8]:
            title = item.find('title').text if item.find('title') is not None else ""
            tl = title.lower()
            
            if any(w in tl for w in ['recall', 'fda', 'warning letter', 'quality issue']):
                flags.append(f"FDA/RECALL: {title[:90]}")
                risk_score += 25
            if any(w in tl for w in ['fraud', 'scam', 'investigation', 'sebi', 'cbi', 'ed raid']):
                flags.append(f"INVESTIGATION: {title[:90]}")
                risk_score += 20
            if any(w in tl for w in ['penalty', 'fine', 'ban', 'suspended']):
                flags.append(f"PENALTY: {title[:90]}")
                risk_score += 15
            if any(w in tl for w in ['resign', 'arrest', 'raid', 'ceo exit']):
                flags.append(f"MANAGEMENT: {title[:90]}")
                risk_score += 20
            if any(w in tl for w in ['debt', 'default', 'bankruptcy']):
                flags.append(f"FINANCIAL: {title[:90]}")
                risk_score += 15
        
        if risk_score >= 40: level = 'HIGH RISK'
        elif risk_score >= 20: level = 'MEDIUM RISK'
        elif risk_score >= 10: level = 'LOW RISK'
        else: level = 'CLEAN'
        
        return {'flags': flags[:3], 'score': risk_score, 'level': level}
    except:
        return {'flags': [], 'score': 0, 'level': 'CLEAN'}

def get_exit_plan(score, entry, target):
    if score >= 80:
        return [
            f"Book 30% at Rs.{entry*1.25:.0f} (+25%)",
            f"Book 40% at Rs.{entry*1.50:.0f} (+50%)",
            f"Trail 25% on remaining",
            f"SL: Rs.{entry*0.95:.0f} (-5%), Trail after +10%"
        ]
    elif score >= 65:
        return [
            f"Book 40% at Rs.{entry*1.20:.0f} (+20%)",
            f"Book 40% at Rs.{entry*1.40:.0f} (+40%)",
            f"Hold balance till Rs.{entry*1.60:.0f} (+60%)",
            f"SL: Rs.{entry*0.95:.0f} (-5%), BE at +8%"
        ]
    elif score >= 55:
        return [
            f"Book 50% at Rs.{entry*1.15:.0f} (+15%)",
            f"Exit balance at Rs.{entry*1.25:.0f} (+25%)",
            f"Re-enter above Rs.{entry*1.30:.0f}",
            f"Strict SL: Rs.{entry*0.96:.0f} (-4%)"
        ]
    elif score >= 40:
        return [
            f"Exit 100% at Rs.{entry*1.10:.0f} (+10%)",
            f"Re-enter if breaks Rs.{entry*1.15:.0f}",
            f"Wait for score above 55",
            f"Strict SL: Rs.{entry*0.97:.0f} (-3%)"
        ]
    else:
        return [
            f"SKIP - Score too low ({score:.1f})",
            "Wait for better setup",
            "Check next analysis",
            "Do not trade"
        ]

def calculate_position(capital, entry, stop_loss):
    risk = capital * 0.02
    risk_per_share = abs(entry - stop_loss)
    if risk_per_share == 0: return 0, 0
    qty = int(risk / risk_per_share)
    inv = qty * entry
    if inv > capital * 0.20:
        qty = int(capital * 0.20 / entry)
        inv = qty * entry
    return max(1, qty), inv

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900:
            parts = [text[i:i+3900] for i in range(0, len(text), 3900)]
            for part in parts[:3]:
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': part, 'parse_mode': 'HTML'}, timeout=10)
                time.sleep(0.5)
            return True
        else:
            resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
            return resp.json().get('ok', False)
    except:
        return False

def analyze():
    nse = Nse()
    results = []
    now = datetime.now()
    ist_time = now.strftime('%I:%M %p')
    ist_date = now.strftime('%d-%b-%Y')
    day = now.strftime('%A')
    
    print(f"\n{'='*50}")
    print(f"PRO TRADING SYSTEM v4.0 - {ist_time}")
    
    regime, mult = get_market_regime()
    print(f"Market: {regime}")
    
    all_stocks = [(sym, sec) for sec, syms in STOCKS.items() for sym in syms]
    print(f"Analyzing {len(all_stocks)} stocks...\n")
    
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
            open_p = float(q.get('open', 0))
            change = float(q.get('pChange', 0))
            vwap = float(q.get('vwap', 0)) if q.get('vwap') else 0
            h52 = float(weekly.get('max', 0))
            l52 = float(weekly.get('min', 0))
            prev = float(q.get('previousClose', 0))
            
            # SCORING
            score = 0
            
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            
            if 50 < pos < 80: score += 10
            elif pos < 30: score += 8
            
            if h52 > 0:
                dh = ((h52 - price) / h52) * 100
                if dh > 30: score += 12
                elif dh > 15: score += 10
            
            if l52 > 0:
                dl = ((price - l52) / l52) * 100
                if dl < 10: score += 8
            
            if vwap > 0:
                vv = ((price - vwap) / vwap) * 100
                if 0 < vv < 2: score += 8
                elif -1 < vv <= 0: score += 10
            
            if 0.5 < change < 2: score += 12
            elif 0 < change <= 0.5: score += 8
            elif -2 < change < 0: score += 7
            
            if price > vwap > 0: score += 5
            if price > open_p: score += 3
            

            # Delivery Analysis
            delivery_info = "N/A"
            dp = 0
            try:
                dq = float(q.get('deliveryQuantity', 0))
                tv = float(q.get('totalTradedVolume', 0))
                
                if tv > 0 and dq > 0:
                    dp = (dq / tv * 100)
                elif tv > 0:
                    # Fallback: use buy/sell ratio
                    buy_qty = float(q.get('totalBuyQuantity', 0))
                    sell_qty = float(q.get('totalSellQuantity', 0))
                    total = buy_qty + sell_qty
                    if total > 0:
                        dp = (buy_qty / total) * 100
                    else:
                        dp = 0
                else:
                    dp = 0
            except:
                dp = 0
            
            # Apply delivery score
            if dp > 65:
                score += 15
                delivery_info = f"{dp:.0f}% (Strong)"
            elif dp > 50:
                score += 12
                delivery_info = f"{dp:.0f}% (Good)"
            elif dp > 40:
                score += 8
                delivery_info = f"{dp:.0f}% (Avg)"
            elif dp > 0:
                score += 3
                delivery_info = f"{dp:.0f}%"
            else:
                delivery_info = "N/A"
            
            news = get_news_analysis(symbol)
            score += news['score']
            
            risk = detect_risk(symbol)
            
            # Final score
            score = score + 12
            if mult < 0.6: score = score * mult
            score = round(max(10, min(95, score)), 1)
            
            if risk['score'] >= 40: score = min(score, 45)
            elif risk['score'] >= 20: score = min(score, 60)
            if news['sentiment'] == 'Very Negative': score = min(score, 35)
            
            # Target & Position
            if score >= 80: tmul = 1.8
            elif score >= 65: tmul = 1.5
            elif score >= 50: tmul = 1.3
            else: tmul = 1.15
            
            target = round(price * tmul, 0)
            stop = round(price * 0.95, 0)
            qty, inv = calculate_position(100000, price, stop)
            
            exit_plan = get_exit_plan(score, price, target)
            
            if score >= 80: action, stars = "STRONG BUY", 5
            elif score >= 65: action, stars = "BUY", 4
            elif score >= 55: action, stars = "ACCUMULATE", 3
            elif score >= 40: action, stars = "WATCH", 2
            else: action, stars = "SKIP", 1
            
            results.append({
                'symbol': symbol, 'sector': sector, 'price': price,
                'score': score, 'stars': stars, 'action': action,
                'target': target, 'stop': stop, 'qty': qty, 'inv': inv,
                'change': change, 'exit_plan': exit_plan,
                'delivery': delivery_info, 'news': news, 'risk': risk
            })
            
            print(f"  {symbol:15} Rs.{price:>8.0f} | Score: {score:>5.1f} | {'⭐'*stars}")
            time.sleep(0.15)
            
        except Exception as e:
            print(f"  {symbol}: Error - {str(e)[:30]}")
    
    if not results:
        send_telegram("No data available. Market may be closed.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # BUILD DETAILED MESSAGE
    s80 = len([r for r in results if r['score'] >= 80])
    s65 = len([r for r in results if 65 <= r['score'] < 80])
    s55 = len([r for r in results if 55 <= r['score'] < 65])
    risky = len([r for r in results if r['risk']['level'] in ['HIGH RISK', 'MEDIUM RISK']])
    
    msg = f"<b>PRO TRADING SYSTEM v4.0</b>\n"
    msg += f"{day}, {ist_date} | {ist_time} IST\n"
    msg += f"Market Regime: {regime}\n"
    msg += f"{'='*35}\n\n"
    
    msg += f"<b>SCREENED:</b> {len(results)} stocks\n"
    msg += f"Strong Buy: {s80} | Buy: {s65} | Accumulate: {s55}\n"
    if risky > 0: msg += f"Risk Flags: {risky} stocks\n"
    msg += f"\n{'='*35}\n\n"
    
    msg += f"<b>TOP 5 PICKS WITH FULL TRADING PLAN</b>\n"
    msg += f"{'='*35}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        star_str = "⭐" * r['stars']
        
        msg += f"<b>{'🟢' if r['score']>=80 else '🔵' if r['score']>=65 else '🟡'} "
        msg += f"#{i} {r['symbol']}</b> | {r['sector']}\n"
        msg += f"{'─'*35}\n"
        
        # Score & Risk
        msg += f"Score: {r['score']}/100 {star_str} | {r['action']}\n"
        if r['risk']['level'] != 'CLEAN':
            msg += f"Risk Level: {r['risk']['level']}\n"
        msg += f"\n"
        
        # Trade Setup
        msg += f"<b>TRADE SETUP:</b>\n"
        msg += f"Entry: Rs.{r['price']:.0f}\n"
        msg += f"Target: Rs.{r['target']:.0f} (+{gain:.0f}%)\n"
        msg += f"Stop Loss: Rs.{r['stop']:.0f} (-5%)\n"
        msg += f"Change Today: {r['change']:+.2f}%\n\n"
        
        # Position
        msg += f"<b>POSITION:</b>\n"
        msg += f"Quantity: {r['qty']} shares\n"
        msg += f"Investment: Rs.{r['inv']:,.0f}\n"
        msg += f"Max Risk: Rs.{r['qty'] * (r['price'] - r['stop']):,.0f}\n"
        msg += f"Delivery: {r['delivery']}\n\n"
        
        # Exit Plan
        msg += f"<b>EXIT PLAN:</b>\n"
        for j, step in enumerate(r['exit_plan']):
            emoji = ["1st", "2nd", "3rd", "SL"][j]
            msg += f"{emoji}: {step}\n"
        msg += f"\n"
        
        # News
        msg += f"<b>NEWS:</b> {r['news']['sentiment']}\n"
        for crux in r['news']['crux'][:2]:
            msg += f"  {crux[:100]}\n"
        
        # Risk Flags
        if r['risk']['flags']:
            msg += f"\n<b>RISK ALERTS:</b>\n"
            for flag in r['risk']['flags'][:2]:
                msg += f"  WARNING: {flag[:90]}\n"
        
        msg += f"\n"
    
    msg += f"{'='*35}\n"
    msg += f"Paper trade first. Start small.\n"
    msg += f"Strict stop loss mandatory.\n"
    msg += f"Risk:Reward target 1:3+"
    
    if send_telegram(msg):
        print(f"\nSent to Telegram!")
        print(f"#1: {results[0]['symbol']} | Score: {results[0]['score']}/100")
    else:
        print("Failed to send.")

if __name__ == "__main__":
    analyze()
