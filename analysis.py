"""
PRO TRADING SYSTEM v4.0
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
        url = f"https://news.google.com/rss/search?q={symbol}+stock&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=5)
        root = ElementTree.fromstring(resp.content)
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text if item.find('title') is not None else ""
            title = re.sub(r'[^\w\s\-.,%]', '', title)
            if len(title) > 20: all_news.append(title)
        
        if not all_news:
            return {'crux': 'No significant news', 'sentiment': 'Neutral', 'score': 8}
        
        pos_w = ['profit', 'growth', 'rise', 'gain', 'upgrade', 'strong', 'record', 'boost', 'dividend', 'buyback', 'bullish']
        neg_w = ['loss', 'fall', 'drop', 'decline', 'downgrade', 'weak', 'probe', 'fraud', 'scam', 'penalty', 'debt']
        
        scores = []
        for t in all_news:
            tl = t.lower()
            ps = sum(1 for w in pos_w if w in tl)
            ns = sum(1 for w in neg_w if w in tl)
            scores.append(ps - ns)
        
        avg = sum(scores) / len(scores)
        if avg > 1: sentiment, sc = 'Very Positive', 14
        elif avg > 0.3: sentiment, sc = 'Positive', 11
        elif avg > -0.3: sentiment, sc = 'Neutral', 8
        elif avg > -1: sentiment, sc = 'Negative', 4
        else: sentiment, sc = 'Very Negative', 1
        
        return {'crux': all_news[0][:100] if all_news else 'No news', 'sentiment': sentiment, 'score': sc}
    except:
        return {'crux': 'News unavailable', 'sentiment': 'Neutral', 'score': 8}

def detect_risk(symbol):
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+FDA+recall+fraud+investigation+penalty&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=5)
        root = ElementTree.fromstring(resp.content)
        
        risk_score = 0
        flags = []
        
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text if item.find('title') is not None else ""
            tl = title.lower()
            
            if any(w in tl for w in ['recall', 'fda', 'warning']):
                flags.append(f"FDA/RECALL: {title[:80]}")
                risk_score += 25
            if any(w in tl for w in ['fraud', 'scam', 'investigation', 'sebi']):
                flags.append(f"PROBE: {title[:80]}")
                risk_score += 20
            if any(w in tl for w in ['penalty', 'fine', 'ban']):
                flags.append(f"PENALTY: {title[:80]}")
                risk_score += 15
        
        if risk_score >= 40: level = 'HIGH RISK'
        elif risk_score >= 20: level = 'MEDIUM RISK'
        elif risk_score >= 10: level = 'LOW RISK'
        else: level = 'CLEAN'
        
        return {'flags': flags[:2], 'score': risk_score, 'level': level}
    except:
        return {'flags': [], 'score': 0, 'level': 'CLEAN'}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        # Keep messages under 4000 chars
        if len(text) > 3800:
            text = text[:3800] + "\n\n... (truncated)"
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except:
        return False

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

def analyze():
    nse = Nse()
    results = []
    now = datetime.now()
    ist_time = now.strftime('%I:%M %p')
    ist_date = now.strftime('%d-%b-%Y')
    day = now.strftime('%A')
    
    print(f"Starting analysis: {ist_time}")
    
    regime, mult = get_market_regime()
    
    all_stocks = [(sym, sec) for sec, syms in STOCKS.items() for sym in syms]
    
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
            
            # Scoring
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
            elif -1 < change < 0: score += 7
            
            if price > vwap > 0: score += 5
            
            # Delivery
            try:
                dq = float(q.get('deliveryQuantity', 0))
                tv = float(q.get('totalTradedVolume', 1))
                dp = (dq / tv * 100) if tv > 0 else 0
                if dp > 65: score += 15
                elif dp > 50: score += 12
                elif dp > 40: score += 8
            except: pass
            
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
            
            # Target
            if score >= 80: tmul = 1.8
            elif score >= 65: tmul = 1.5
            elif score >= 50: tmul = 1.3
            else: tmul = 1.15
            
            target = round(price * tmul, 0)
            stop = round(price * 0.95, 0)
            qty, inv = calculate_position(100000, price, stop)
            
            if score >= 80: action, stars = "STRONG BUY", 5
            elif score >= 65: action, stars = "BUY", 4
            elif score >= 55: action, stars = "ACCUMULATE", 3
            elif score >= 40: action, stars = "WATCH", 2
            else: action, stars = "SKIP", 1
            
            results.append({
                'symbol': symbol, 'sector': sector, 'price': price,
                'score': score, 'stars': stars, 'action': action,
                'target': target, 'stop': stop, 'qty': qty, 'inv': inv,
                'change': change, 'news': news, 'risk': risk
            })
            
            print(f"  {symbol}: {score}")
            time.sleep(0.15)
            
        except Exception as e:
            print(f"  {symbol}: Error - {str(e)[:30]}")
    
    if not results:
        send_telegram("No data available. Market closed.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # Build clean message
    msg = f"📊 STOCK ANALYSIS\n"
    msg += f"{ist_date} | {ist_time} IST\n"
    msg += f"Market: {regime}\n"
    msg += f"{'='*30}\n\n"
    
    s80 = len([r for r in results if r['score'] >= 80])
    s65 = len([r for r in results if r['score'] >= 65])
    
    msg += f"Scanned: {len(results)} stocks\n"
    msg += f"Strong Buy: {s80} | Buy: {s65}\n\n"
    
    msg += f"TOP 5 PICKS:\n"
    msg += f"{'='*30}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        star_str = "⭐" * r['stars']
        
        msg += f"{i}. {r['symbol']} | {r['sector']}\n"
        msg += f"   Price: Rs.{r['price']:.0f}\n"
        msg += f"   Score: {r['score']}/100 {star_str}\n"
        msg += f"   Action: {r['action']}\n"
        msg += f"   Target: Rs.{r['target']:.0f} (+{gain:.0f}%)\n"
        msg += f"   Stop: Rs.{r['stop']:.0f}\n"
        msg += f"   Qty: {r['qty']} shares\n"
        msg += f"   News: {r['news']['sentiment']}\n"
        
        if r['risk']['flags']:
            msg += f"   Risk: {r['risk']['level']}\n"
            for f in r['risk']['flags']:
                msg += f"   - {f[:70]}\n"
        
        msg += "\n"
    
    msg += f"{'='*30}\n"
    msg += f"Use strict stop loss. Paper trade first."
    
    # Send
    if send_telegram(msg):
        print("Sent to Telegram!")
    else:
        print("Failed to send. Check token.")

if __name__ == "__main__":
    analyze()
