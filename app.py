import os
import json
from flask import Flask, request, Response, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# 配置大模型 (这里以DeepSeek为例，你可以换成百川、Kimi、OpenAI等)
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", "your-api-key"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1") 
)
MODEL_NAME = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    game_state = data.get('state', {})
    player_input = data.get('input', '')
    event_context = data.get('event', {})

    # 构建系统提示词 (核心剧本逻辑)
    system_prompt = f"""
    你是一个文字冒险游戏的底层引擎。当前剧本是《皇帝后宫模拟器》。
    当前游戏状态：回合 {game_state.get('turn', 1)}/{game_state.get('max_turns', 100)}
    玩家属性：{json.dumps(game_state.get('attributes', {}), ensure_ascii=False)}
    当前正在处理的事件：{event_context.get('name', '无')} - {event_context.get('desc', '无')}
    
    玩家的行动/选择是："{player_input}"
    
    请严格按照以下格式回复（不要包含其他废话）：
    第一部分：直接输出剧情的文字描述（这部分会被流式展示给玩家）。
    第二部分：必须在文章末尾加上分隔符 ===JSON=== ，然后紧跟一个合法的JSON对象，包含接下来的数据：
    {{
        "choices": ["选项1", "选项2", "选项3"], // 提供给玩家的后续选项，如果不需选项填[]
        "event_completed": true/false, // 当前事件是否结束
        "impact_summary": "如果事件结束，这里写总结和影响",
        "new_events":[ // 衍生出的新事件
            {{"id": "随机ID", "name": "事件名", "desc": "描述", "turns_left": 3}}
        ],
        "attr_changes": {{"体质": 1, "才华": -1}} // 属性变动
    }}
    """

    messages =[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "请推动剧情并返回规定格式的内容。"}
    ]

    def generate():
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                stream=True,
                temperature=0.7
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    # 使用 SSE 格式推送数据
                    content = chunk.choices[0].delta.content
                    # 将换行符等处理一下防止SSE格式错乱
                    data_str = json.dumps({"text": content})
                    yield f"data: {data_str}\n\n"
            
            yield "event: end\ndata: {}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))