"""
Stock Market Analyzer - GitHub Actions
Runs automatically Mon-Fri at 9:30AM, 12PM, 2PM, 3:15PM IST
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime

# Get credentials from GitHub Secrets
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

STOCKS = [
    'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM',
    'HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK',
    'RELIANCE', 'ITC', 'LT', 'HINDUNILVR',
    'SUNPHARMA', 'DRREDDY', 'CIPLA',
    'TITAN', 'ASIANPAINT', 'NESTLEIND',
    'BAJFINANCE', 'BAJAJFINSV',
    'MARUTI', 'POWERGRID', 'NTPC', 'ADANIPORTS'
]

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
    except Exception as e:
        print(f"Error: {e}")

def analyze():
    nse = Nse()
    results = []
    now = datetime.now()
    
    for symbol in STOCKS:
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
            
            score = 0
            day_range = high - low
            pos = ((price - low) / day_range * 100) if day_range > 0 else 50
            
            if 50 < pos < 80: score += 25
            elif pos < 30: score += 20
            
            dist_high = ((high_52 - price) / high_52 * 100) if high_52 > 0 else 0
            dist_low = ((price - low_52) / low_52 * 100) if low_52 > 0 else 0
            
            if dist_high > 20: score += 25
            if dist_low < 10: score += 20
            
            vs_vwap = ((price - vwap) / vwap * 100) if vwap > 0 else 0
            if 0 < vs_vwap < 2: score += 15
            
            if 0.5 < change_pct < 2: score += 15
            elif -2 < change_pct < 0: score += 10
            
            score = min(100, score)
            
            results.append({
                'symbol': symbol,
                'price': price,
                'score': score,
                'target': round(price * (1 + score/100), 2),
                'stop_loss': round(price * 0.95, 2)
            })
            time.sleep(0.15)
        except:
            continue
    
    if not results:
        send_telegram("❌ No data. Market may be closed.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    hour = now.hour
    if hour < 11: session = "🌅 MORNING ANALYSIS"
    elif hour < 14: session = "☀️ MIDDAY UPDATE"
    elif hour < 15: session = "🌤️ AFTERNOON CHECK"
    else: session = "🌙 CLOSING REPORT"
    
    strong_buy = len([r for r in results if r['score'] >= 80])
    buy = len([r for r in results if 65 <= r['score'] < 80])
    
    message = f"📊 <b>{session}</b>\n📅 {now.strftime('%d-%b %I:%M %p')} IST\n{'═'*30}\n\n"
    message += f"📈 <b>SUMMARY</b>\n├ Analyzed: {len(results)}\n├ Strong Buy: {strong_buy}\n└ Buy: {buy}\n\n"
    message += f"🎯 <b>TOP 5 PICKS</b>\n{'─'*30}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        gain = ((r['target'] - r['price']) / r['price']) * 100
        emoji = "🟢" if r['score'] >= 80 else "🔵" if r['score'] >= 65 else "🟡"
        
        message += f"{emoji} <b>{i}. {r['symbol']}</b>\n"
        message += f"   💰 ₹{r['price']:.0f}\n"
        message += f"   🎯 ₹{r['target']:.0f} (+{gain:.0f}%)\n"
        message += f"   🛑 Stop: ₹{r['stop_loss']:.0f}\n"
        message += f"   📊 Score: {r['score']}/100\n\n"
    
    message += f"{'═'*30}\n🤖 <i>GitHub Auto-Analyzer</i>"
    send_telegram(message)

if __name__ == "__main__":
    analyze()
