import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google import genai

app = Flask(__name__)

line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')
gemini_api_key = os.getenv('GEMINI_API_KEY')

line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

client = genai.Client(api_key=gemini_api_key)

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
    user_message = event.message.text
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=user_message,
            config={
                'system_instruction': '你是一個輕鬆親切、像朋友一樣聊天的 AI 助理，請用繁體中文回覆。回覆要簡短自然，不要太長。',
            }
        )
        reply_text = response.text
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    except Exception as e:
        print(f"Error: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="抱歉，我現在有點忙，請稍後再試～")
        )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))
