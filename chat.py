# 提示词和聊天记录保存在项目目录下，与代码直接关联，不建议修改。保存的图片可以在配置文件中配置
#  .saved_message
#   |--- ...
#  .prompts
#   |---... 

import configparser,requests,os,base64,time,json,datetime,re
from openai import OpenAI
from ncatbot.core.element import Record,MessageChain

config_parser = configparser.ConfigParser()
config_parser.read('config.ini')

user_messages = {}
group_messages = {}

try:
    with open("saved_message/user_messages.json","r",encoding="utf-8") as f:
        user_messages = json.load(f)
    with open("saved_message/group_messages.json","r",encoding="utf-8") as f:
        group_messages = json.load(f) 
except FileNotFoundError:
    os.makedirs("saved_message",exist_ok = True)
    
api_key = config_parser.get('ApiKey', 'api_key')
base_url = config_parser.get('ApiKey', 'base_url')
model = config_parser.get('ApiKey', 'model')
MAX_HISTORY_LENGTH = config_parser.getint('chat', 'MAX_HISTORY_LENGTH')
#用于图片识别
MOONSHOT_API_KEY = config_parser.get('pic', 'MOONSHOT_API_KEY')
MOONSHOT_MODEL = config_parser.get('pic', 'MOONSHOT_MODEL')
cache_address = config_parser.get('cache','cache_address')

def remove_brackets_content(text) -> str:
    """
    删除字符串中所有括号及其内容，包括：
    - 中文括号：（）【】
    - 英文括号：()
    - 花括号：{}
    """
    text = re.sub(r'（.*?）', '', text)
    text = re.sub(r'【.*?】', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\{.*?\}', '', text)
    text = re.sub(r'\「.*?\」', '', text)
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text.strip()

def load_prompt(user_id=None, group_id=None):
    prompt_file = None
    if user_id:
        user_id = str(user_id)
        prompt_file = f"prompts/user/user_{user_id}.txt"
    elif group_id:
        group_id = str(group_id)
        prompt_file = f"prompts/group/group_{group_id}.txt"

    try:
        with open(prompt_file, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        try:
            with open("neko.txt", "r", encoding="utf-8") as file:
                return file.read()
        except FileNotFoundError:
            return ""

def chat(content, user_id=None, group_id=None, group_user_id=None,image=False):
    #如果是图片，则content为图片的url
    
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_id:
        user_id = str(user_id)
        if user_id not in user_messages:
            prompt = load_prompt(user_id=user_id)
            user_messages[user_id] = [{"role": "system", "content": prompt}]
        messages = user_messages[user_id]
    elif group_id:
        group_id = str(group_id)
        if group_id not in group_messages:
            prompt = load_prompt(group_id=group_id)
            group_messages[group_id] = [{"role": "system", "content": prompt}]
        messages = group_messages[group_id]
    else:
        messages = []

    if group_user_id:
        pre_text = f"用户{group_user_id}说："
    else:
        pre_text = ""

    if image:
        response = requests.get(content)
        if response.status_code == 200:
            # 保存图片到本地
            dirs = cache_address+"saved_images"
            os.makedirs(dirs, exist_ok=True)
            name = int(time.time())
            file_name = dirs + f"/{name}.jpg"
            if not os.path.exists(file_name):
                with open(file_name, "wb") as file:
                    file.write(response.content)

        with open(file_name, 'rb') as f: #读取图片
            img_base = base64.b64encode(f.read()).decode('utf-8')

        client = OpenAI(
            api_key=MOONSHOT_API_KEY,
            base_url="https://api.moonshot.cn/v1"
        )
        response = client.chat.completions.create(
            model=MOONSHOT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "请描述这个图片"
                        }
                    ]
                }
            ]
        )
        messages.append({"role": "system", "content":f"当前时间：{now_time}"})
        messages.append({"role": "user", "content":f"{pre_text}"+"这是一张图片的描述："+response.choices[0].message.content})

    else:
        messages.append({"role": "system", "content":f"当前时间：{now_time}"})
        messages.append({"role": "user", "content":f"{pre_text}"+ content})

    #保留最大历史记录
    if len(messages) > MAX_HISTORY_LENGTH:
        messages = messages[-MAX_HISTORY_LENGTH:] #这里有可能会丢失初始提示词，但ai大概率能根据上下文判断提示词

    client = OpenAI(api_key=api_key,base_url=base_url)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False
    )
    
    assistant_response = response.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_response})

    #保存数据
    with open("saved_message/user_messages.json","w",encoding="utf-8") as f:
        json.dump(user_messages,f,ensure_ascii=False,indent = 4)
    with open("saved_message/group_messages.json","w",encoding="utf-8") as f:
        json.dump(group_messages,f,ensure_ascii=False,indent = 4)

    return assistant_response

def tts(content) -> MessageChain:
    file_path = cache_address+ "tts/"
    os.makedirs(file_path, exist_ok=True)
    name = int(time.time())

    speech_file_path = file_path + f"{name}.mp3"

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )

    with client.audio.speech.with_streaming_response.create(
            model="FunAudioLLM/CosyVoice2-0.5B",
            voice="FunAudioLLM/CosyVoice2-0.5B:diana",  # 系统预置音色
            # 用户输入信息
            input="你能用猫娘一样的活跃以及可爱的语气说吗？<|endofprompt|>"+remove_brackets_content(content),
            response_format="mp3"
    ) as response:
        response.stream_to_file(speech_file_path)

    message = MessageChain([
        Record(speech_file_path)
    ])
    return message