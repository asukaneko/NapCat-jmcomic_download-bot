import configparser,requests,os,base64,time

config_parser = configparser.ConfigParser()
config_parser.read('config.ini')

user_messages = {}
group_messages = {}

api_key = config_parser.get('ApiKey', 'api_key')
base_url = config_parser.get('ApiKey', 'base_url')
model = config_parser.get('ApiKey', 'model')
MAX_HISTORY_LENGTH = config_parser.getint('chat', 'MAX_HISTORY_LENGTH')
#用于图片识别
MOONSHOT_API_KEY = config_parser.get('pic', 'MOONSHOT_API_KEY')
MOONSHOT_MODEL = config_parser.get('pic', 'MOONSHOT_MODEL')

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

def chat(content, user_id=None, group_id=None,image=False):
    from openai import OpenAI

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

    if image:
        response = requests.get(content)
        if response.status_code == 200:
            # 保存图片到本地
            os.makedirs("saved_images", exist_ok=True)
            name = int(time.time())
            file_name = f"saved_images/{name}.jpg"
            if not os.path.exists(file_name):
                with open(file_name, "wb") as file:
                    file.write(response.content)

        with open(f"saved_images/{name}.jpg", 'rb') as f: #读取图片
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
        messages.append({"role": "user", "content":"这是一张图片的描述："+response.choices[0].message.content })

    else:
        messages.append({"role": "user", "content": content})


    if len(messages) > MAX_HISTORY_LENGTH:
        messages = messages[-MAX_HISTORY_LENGTH:]

    client = OpenAI(api_key=api_key,
                    base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False
    )
    assistant_response = response.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_response})
    return assistant_response
