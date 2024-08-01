import time
from threading import Thread
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import random
from datetime import datetime, timedelta

app = Flask(__name__)

line_bot_api = LineBotApi('jr8iFRvp3cE7qr4wZlIzhrGuKuCXCKj8wPPeWVujVlw59jUIsSWQr5pHdDfUxKcdomWffF/wu0OxD+hkK2gGaD99u6e74B4lT9oJWc4MlRdOuceOWwwMPUoYmE1WbvHnip0NDa+KGXMtLhKh9WH44QdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('4b824b6ade3b043dccca9df9a7829b83')

# 初始化遊戲數據
players = {}
bets = {}
initial_chips = 5000
daily_reward = 5000
rolling_players = {}
dealer_dice = []
dealer_sum = 0
results = {}

def get_player_name(user_id):
    profile = line_bot_api.get_profile(user_id)
    return profile.display_name

def reset_daily_rewards():
    for player in players.values():
        player['claimed_reward'] = False

def countdown_timer():
    time.sleep(20)
    for user_id in bets:
        line_bot_api.push_message(user_id, TextSendMessage(text="下注時間結束"))
    if bets:
        dealer_roll()

def dealer_roll():
    global dealer_dice, dealer_sum
    dealer_dice = [random.randint(1, 6) for _ in range(3)]
    dealer_sum = sum(dealer_dice)
    dealer_text = (f"莊家點數為:\n"
                   f"[第一點]:{dealer_dice[0]}\n"
                   f"[第二點]:{dealer_dice[1]}\n"
                   f"[第三點]:{dealer_dice[2]}\n"
                   f"[總合]:{dealer_sum}")
    for user_id in bets:
        line_bot_api.push_message(user_id, TextSendMessage(text=dealer_text))
        line_bot_api.push_message(user_id, TextSendMessage(text="請輸入“擲骰子”以擲骰子。\n請等待30秒"))
        rolling_players[user_id] = bets[user_id]
        results[user_id] = None
        Thread(target=rolling_countdown, args=(user_id,)).start()

def rolling_countdown(user_id):
    time.sleep(20)
    if results[user_id] is None:
        player_bet = rolling_players[user_id]
        player_dice = [random.randint(1, 6) for _ in range(3)]
        player_sum = sum(player_dice)
        results[user_id] = {
            'dice': player_dice,
            'sum': player_sum,
            'bet': player_bet
        }
    if all(results.values()):
        finalize_results()

def finalize_results():
    for user_id, result in results.items():
        player_dice = result['dice']
        player_sum = result['sum']
        player_bet = result['bet']
        player_name = players[user_id]['name']

        player_text = (f"{player_name} 的點數為:\n"
                       f"[第一點]:{player_dice[0]}\n"
                       f"[第二點]:{player_dice[1]}\n"
                       f"[第三點]:{player_dice[2]}\n"
                       f"[總合]:{player_sum}")

        if (player_bet['type'] == '小' and player_sum < dealer_sum) or (player_bet['type'] == '大' and player_sum > dealer_sum):
            result_text = (f"{player_name} 獲勝\n"
                           f"┏━〖結算列表〗━┓\n"
                           f"┣ {player_name} +{player_bet['amount']} 元\n"
                           f"┣━ 餘額: {players[user_id]['chips'] + player_bet['amount']} 元\n"
                           f"┣ 結算完畢")
            players[user_id]['chips'] += player_bet['amount']
            players[user_id]['wins'] += 1
        else:
            result_text = (f"{player_name} 失敗\n"
                           f"┏━〖結算列表〗━┓\n"
                           f"┣ {player_name} -{player_bet['amount']} 元\n"
                           f"┣━ 餘額: {players[user_id]['chips'] - player_bet['amount']} 元\n"
                           f"┣ 結算完畢")
            players[user_id]['chips'] -= player_bet['amount']
            players[user_id]['losses'] += 1

        line_bot_api.push_message(user_id, TextSendMessage(text=f"{player_text}\n\n{result_text}"))

    rolling_players.clear()
    results.clear()
    bets.clear()

def display_rankings():
    sorted_players = sorted(players.values(), key=lambda x: x['chips'], reverse=True)[:5]
    ranking_text = "玩家排名:\n"
    for idx, player in enumerate(sorted_players, 1):
        ranking_text += (f"第{idx}名:\n"
                         f"---------------\n"
                         f"玩家名稱: {player['name']}\n"
                         f"籌碼: {player['chips']}\n"
                         f"勝場: {player['wins']}\n"
                         f"敗場: {player['losses']}\n---------------\n")
    return ranking_text

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    current_time = datetime.now()

    if user_id not in players:
        players[user_id] = {
            'chips': initial_chips,
            'claimed_reward': False,
            'last_claimed': current_time - timedelta(days=1),
            'name': get_player_name(user_id),
            'wins': 0,
            'losses': 0
        }

    player = players[user_id]

    if user_message.lower() == '加入遊戲':
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"歡迎加入遊戲！你有 {initial_chips} 個籌碼。"))

    elif user_message.lower() == '每日簽到':
        if current_time - player['last_claimed'] >= timedelta(days=1):
            player['chips'] += daily_reward
            player['claimed_reward'] = True
            player['last_claimed'] = current_time
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"簽到成功！你獲得了 {daily_reward} 個籌碼。"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你今天已經簽到過了，請明天再來！"))

    elif user_message.lower() == '下注':
        bets[user_id] = None
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請選擇比大小和下注金額，如：大500或小500\n請等待30秒"))
        Thread(target=countdown_timer).start()

    elif user_message.lower().startswith('大') or user_message.lower().startswith('小'):
        try:
            bet_type = user_message[0]
            bet_amount = int(user_message[1:])
            if bet_amount > 0 and player['chips'] >= bet_amount:
                bets[user_id] = {'type': bet_type, 'amount': bet_amount}
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{player['name']} 下注 {bet_amount} 成功"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你的籌碼不足或下注金額無效。請重新下注。"))
        except ValueError:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入有效的下注金額。"))

    elif user_message.lower() == '錢包':
        claimed_reward_text = "已領取" if player['claimed_reward'] else "未領取"
        wallet_info = f"玩家名稱: {player['name']}\n籌碼數量: {player['chips']}\n每日簽到: {claimed_reward_text}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=wallet_info))

    elif user_message.lower() == '擲骰子' and user_id in rolling_players:
        player_bet = rolling_players[user_id]
        player_dice = [random.randint(1, 6) for _ in range(3)]
        player_sum = sum(player_dice)
        player_name = player['name']
        
        player_text = (f"{player_name} 的點數為:\n"
                       f"[第一點]:{player_dice[0]}\n"
                       f"[第二點]:{player_dice[1]}\n"
                       f"[第三點]:{player_dice[2]}\n"
                       f"[總合]:{player_sum}")

        results[user_id] = {
            'dice': player_dice,
            'sum': player_sum,
            'bet': player_bet
        }

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"擲骰成功\n{player_text}"))

    elif user_message.lower() == '玩家排名':
        ranking_text = display_rankings()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ranking_text))

if __name__ == "__main__":
    app.run()
