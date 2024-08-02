import logging
import time
from threading import Thread
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import random
from datetime import datetime, timedelta

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

line_bot_api = LineBotApi('jr8iFRvp3cE7qr4wZlIzhrGuKuCXCKj8wPPeWVujVlw59jUIsSWQr5pHdDfUxKcdomWffF/wu0OxD+hkK2gGaD99u6e74B4lT9oJWc4MlRdOuceOWwwMPUoYmE1WbvHnip0NDa+KGXMtLhKh9WH44QdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('4b824b6ade3b043dccca9df9a7829b83')
# 初始化遊戲數據
players = {}
bets = {}
initial_chips = 5000
daily_reward = 5000
bot_enabled = True

def get_player_name(user_id):
    profile = line_bot_api.get_profile(user_id)
    return profile.display_name

def display_rankings():
    sorted_players = sorted(players.values(), key=lambda x: x['chips'], reverse=True)[:5]
    ranking_text = "玩家排名:\n"
    for idx, player in enumerate(sorted_players, 1):
        ranking_text += (f"\n第{idx}名:\n"
                         f"---------------\n"
                         f"玩家名稱: {player['name']}\n"
                         f"籌碼: {player['chips']}\n"
                         f"勝場: {player['wins']}\n"
                         f"敗場: {player['losses']}\n---------------\n")
    return ranking_text

def handle_bet(user_id):
    player_bet = bets[user_id]
    player = players[user_id]
    
    # 莊家擲骰子
    dealer_dice = [random.randint(1, 6) for _ in range(3)]
    dealer_sum = sum(dealer_dice)
    dealer_text = (f"莊家點數為:\n"
                   f"[第一點]:{dealer_dice[0]}\n"
                   f"[第二點]:{dealer_dice[1]}\n"
                   f"[第三點]:{dealer_dice[2]}\n"
                   f"[總合]:{dealer_sum}")

    # 玩家擲骰子
    player_dice = [random.randint(1, 6) for _ in range(3)]
    player_sum = sum(player_dice)
    player_name = player['name']
    player_text = (f"{player_name} 的點數為:\n"
                   f"[第一點]:{player_dice[0]}\n"
                   f"[第二點]:{player_dice[1]}\n"
                   f"[第三點]:{player_dice[2]}\n"
                   f"[總合]:{player_sum}")

    if (player_bet['type'] == '小' and player_sum < dealer_sum) or (player_bet['type'] == '大' and player_sum > dealer_sum):
        result_text = (f"{player_name} 獲勝\n"
                       f"┏━〖結算列表〗━┓\n"
                       f"┣ {player_name} +{player_bet['amount']} 元\n"
                       f"┣━ 餘額: {player['chips'] + player_bet['amount']} 元\n"
                       f"┣ 結算完畢")
        player['chips'] += player_bet['amount']
        player['wins'] += 1
    else:
        result_text = (f"{player_name} 失敗\n"
                       f"┏━〖結算列表〗━┓\n"
                       f"┣ {player_name} -{player_bet['amount']} 元\n"
                       f"┣━ 餘額: {player['chips'] - player_bet['amount']} 元\n"
                       f"┣ 結算完畢")
        player['chips'] -= player_bet['amount']
        player['losses'] += 1

    # 清理當前玩家的下注
    del bets[user_id]
    
    # 發送結果
    line_bot_api.push_message(user_id, TextSendMessage(text=f"{dealer_text}\n\n{player_text}\n\n{result_text}"))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    logging.info(f"Received body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global bot_enabled

    user_id = event.source.user_id
    user_message = event.message.text.lower()
    current_time = datetime.now()

    logging.info(f"Received message: {user_message} from user: {user_id}")

    if not bot_enabled:
        logging.info("Bot is disabled")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"機器人已關機，請點選連結：https://youtu.be/xvFZjo5PgG0?si=PIbeotn79bwpeaYd", sender=None))
        return

    # 开机命令
    if user_message == '開機5269':
        logging.info("Enabling bot")
        bot_enabled = True
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="機器人已開機。"))
        return

    # 关机命令
    if user_message == '關機':
        logging.info("Disabling bot")
        bot_enabled = False
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="機器人已關機。"))
        return

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

    if user_message == '加入遊戲':
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"歡迎加入遊戲！你有 {initial_chips} 個籌碼。"))

    elif user_message == '每日簽到':
        if current_time - player['last_claimed'] >= timedelta(days=1):
            player['chips'] += daily_reward
            player['claimed_reward'] = True
            player['last_claimed'] = current_time
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"簽到成功！你獲得了 {daily_reward} 個籌碼。"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你今天已經簽到過了，請明天再來！"))

    elif user_message == '下注':
        bets[user_id] = None
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請選擇比大小和下注金額，如：大500或小500"))

    elif user_message.startswith('大') or user_message.startswith('小'):
        try:
            bet_type = user_message[0]
            bet_amount = int(user_message[1:])
            if bet_amount > 0 and player['chips'] >= bet_amount:
                bets[user_id] = {'type': bet_type, 'amount': bet_amount}
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{player['name']} 下注 {bet_amount} 成功"))
                handle_bet(user_id)
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你的籌碼不足或下注金額無效。請重新下注。"))
        except ValueError:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入有效的下注金額。"))

    elif user_message == '錢包':
        claimed_reward_text = "已領取" if player['claimed_reward'] else "未領取"
        wallet_info = f"玩家名稱: {player['name']}\n籌碼數量: {player['chips']}\n每日簽到: {claimed_reward_text}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=wallet_info))

    elif user_message == '玩家排名':
        ranking_text = display_rankings()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ranking_text))

    elif user_message == '吃雞雞':
        player['chips'] += 100
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="暗號成功，你獲得了 100 個籌碼。"))

if __name__ == "__main__":
    app.run()
