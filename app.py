import os
import re
import html
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from groq import Groq

app = Flask(__name__)

line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')
groq_api_key = os.getenv('GROQ_API_KEY')

line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)
groq_client = Groq(api_key=groq_api_key)

IG_PATTERN = re.compile(r'https?://(?:www\.)?instagram\.com/(?:reel|p|tv|stories)/[^\s]+')


def fetch_ig_metadata(url):
    try:
        headers = {
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            og_title = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
            og_desc = re.search(r'<meta property="og:description" content="([^"]+)"', r.text)
            title = html.unescape(og_title.group(1)) if og_title else ''
            desc = html.unescape(og_desc.group(1)) if og_desc else ''
            return title, desc
    except Exception as e:
        print(f"Error fetching IG metadata for {url}: {e}")
    return '', ''


def classify_ig_link(message_text, ig_links):
    description = message_text
    for link in ig_links:
        description = description.replace(link, '').strip()

    ig_info_parts = []
    for link in ig_links:
        title, desc = fetch_ig_metadata(link)
        info = f"連結：{link}"
        if title:
            info += f"\n頁面標題：{title}"
        if desc:
            info += f"\n頁面描述：{desc}"
        ig_info_parts.append(info)

    ig_info = '\n\n'.join(ig_info_parts)

    prompt = f"""你是一個內容分類助理。用戶分享了 Instagram 連結，請幫忙分類整理。

用戶附帶的文字：「{description}」

以下是從 IG 頁面抓取到的資訊：
{ig_info}

請根據以上資訊判斷分類，常見分類包括（但不限於）：
- 地點-秘境-美食（餐廳、景點、秘境等）
- AI工具（AI 相關工具、教學）
- 娛樂（搞笑、音樂、遊戲等）
- 旅遊景點（旅遊相關）
- 賺錢-副業（賺錢方法、副業、接案等）
- 學習資源（教學、知識分享）
- 生活好物（推薦商品、生活技巧）

請用以下格式回覆（直接輸出結果，不要加任何解釋）：

📂 [分類名稱]
[標題或簡短描述]
[IG連結]

如果有多個連結，每個都要分類。標題請根據頁面資訊寫一個簡短的中文描述。"""

    try:
        response = groq_client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': '你是一個專業的內容分類助理，擅長將 Instagram 影片連結分類整理。請用繁體中文回覆，格式要整齊方便複製。'},
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error classifying IG link: {e}")
        return None


def chat_reply(user_message):
    try:
        response = groq_client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': '你是一個輕鬆親切、像朋友一樣聊天的 AI 助理，請用繁體中文回覆。回覆要簡短自然，不要太長。'},
                {'role': 'user', 'content': user_message}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in chat reply: {e}")
        return None


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
    print(f"Received message: {user_message}")

    ig_links = IG_PATTERN.findall(user_message)

    if ig_links:
        print(f"Detected IG links: {ig_links}")
        reply_text = classify_ig_link(user_message, ig_links)
        if not reply_text:
            reply_text = "抱歉，分類時出了點問題，請稍後再試～"
    else:
        reply_text = chat_reply(user_message)
        if not reply_text:
            reply_text = "抱歉，我現在有點忙，請稍後再試～"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))
