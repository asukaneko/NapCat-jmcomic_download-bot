from ncatbot.core import BotClient, GroupMessage, PrivateMessage
from config import load_config
from chat import group_messages,user_messages # 导入 chat 函数
import jmcomic,os,sys,requests,random,configparser,json,yaml
from jmcomic import *

if_tts = False #判断是否开启TTS

bot_id = load_config() # 加载配置,返回机器人qq号

bot = BotClient()

command_handlers = {}
group_imgs = {} # 用于存储图片信息

def register_command(command): # 注册命令
    def decorator(func):
        command_handlers[command] = func
        return func
    return decorator

def load_address(): # 加载配置文件，返回图片保存地址
    with open("option.yml", "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)
        after_photo_list = conf.get("plugins", {}).get("after_photo", [])
        if after_photo_list and isinstance(after_photo_list, list):
            pdf_dir = after_photo_list[0].get("kwargs", {}).get("pdf_dir", "./cache/pdf/")
        else:
            pdf_dir = "./cache/pdf/"
        if not pdf_dir.endswith(os.path.sep):
            pdf_dir += os.path.sep
        return pdf_dir

@register_command("测试")
async def handle_test(msg, is_group=True):
    if not msg.raw_message == "测试":
        return
    reply_text = "测试成功喵~\n输入 /help 查看帮助喵~"
    if is_group:
        await msg.reply(text=reply_text)
    else:
        await bot.api.post_private_msg(msg.user_id, text=reply_text)

@register_command("/tts")
async def handle_tts(msg, is_group=True):
    global if_tts
    if_tts = not if_tts
    text = "已开启TTS喵~" if if_tts else "已关闭TTS喵~"
    if is_group:
        await msg.reply(text=text)
    else:
        await bot.api.post_private_msg(msg.user_id, text=text)

@register_command("/jmrank")
async def handle_jmrank(msg, is_group=True):
    select = msg.raw_message[len("/jmrank"):].strip()
    # 创建客户端
    op = JmOption.default()
    cl = op.new_jm_client()

    page: JmCategoryPage = cl.categories_filter(
        page=1,
        time=JmMagicConstants.TIME_ALL,
        category=JmMagicConstants.CATEGORY_ALL,
        order_by=JmMagicConstants.ORDER_BY_LATEST,
    )

    if select == "月排行":
        page: JmCategoryPage = cl.month_ranking(1)
    elif select == "周排行":
        page: JmCategoryPage = cl.week_ranking(1)

    cache_dir = load_address()
    cache_dir += "rank/"
    os.makedirs(cache_dir,exist_ok = True)

    name = time.time()
    for page in cl.categories_filter_gen(page=1,  # 起始页码
                                         # 下面是分类参数
                                         time=JmMagicConstants.TIME_WEEK,
                                         category=JmMagicConstants.CATEGORY_ALL,
                                         order_by=JmMagicConstants.ORDER_BY_VIEW,
                                         ):
        for aid, atitle in page:
            #content += f"ID: {aid}\n"
            with open(cache_dir + f"{select}_{name}.txt", "a", encoding="utf-8") as f:
                f.write(f"ID: {aid} Name: {atitle}\n")

    if is_group:
        await bot.api.post_group_file(msg.group_id, file=cache_dir + f"{select}_{name}.txt")
    else:
        await bot.api.upload_private_file(msg.user_id, cache_dir + f"{select}_{name}.txt", f"{select}_{name}.txt")

@register_command("/jm")
async def handle_jmcomic(msg, is_group=True):
    match = re.match(r'^/jm\s+(\d+)$', msg.raw_message)
    if match:
        comic_id = match.group(1)
        reply_text = f"成功获取漫画ID了喵~: {comic_id}"
        if is_group:
            await msg.reply(text=reply_text)
        else:
            await bot.api.post_private_msg(msg.user_id, text=reply_text)

        try:
            option = jmcomic.create_option_by_file('./option.yml')
            jmcomic.download_album(comic_id, option)

            pdf_dir = load_address()
            file_path = os.path.join(pdf_dir, f"{comic_id}.pdf")

            if is_group:
                await bot.api.post_group_file(msg.group_id, file=file_path)
                await msg.reply(text="漫画下好了喵~")
            else:
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
                await bot.api.post_private_msg(msg.user_id, text=f"漫画下好了喵~")
        except Exception as e:
            error_msg = f"出错了喵~: {e}"
            if is_group:
                await msg.reply(text=error_msg)
            else:
                await bot.api.post_private_msg(msg.user_id, text=error_msg)
    else:
        error_msg = "格式错误了喵~，请输入 /jm 后跟漫画ID"
        if is_group:
            pass
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg)

@register_command("/set_prompt")
@register_command("/sp")
async def handle_set_prompt(msg, is_group=True):
    prompt_content = ""
    if msg.raw_message.startswith("/set_prompt"):
        prompt_content = msg.raw_message[len("/set_prompt"):].strip()
    elif msg.raw_message.startswith("/sp"):
        prompt_content = msg.raw_message[len("/sp"):].strip()
    id_str = str(msg.group_id if is_group else msg.user_id)
    os.makedirs("prompts", exist_ok=True)

    prefix = "group" if is_group else "user"
    with open(f"prompts/{prefix}/{prefix}_{id_str}.txt", "w", encoding="utf-8") as file:
        file.write(prompt_content)

    messages = group_messages if is_group else user_messages
    if id_str in messages:
        del messages[id_str]
    messages[id_str] = [{"role": "system", "content": prompt_content}]

    reply_text = "群组提示词已更新，对话记录已清除喵~" if is_group else "个人提示词已更新，对话记录已清除喵~"
    if is_group:
        await msg.reply(text=reply_text)
    else:
        await bot.api.post_private_msg(msg.user_id, text=reply_text)


@register_command("/del_prompt")
@register_command("/dp")
async def handle_del_prompt(msg, is_group=True):
    id_str = str(msg.group_id if is_group else msg.user_id)
    if is_group:
        if id_str in group_messages:
            del group_messages[id_str]
            try:
                os.remove(f"prompts/group/group_{id_str}.txt")
                with open("neko.txt", "r", encoding="utf-8") as file:
                    prompt = file.read()
                    group_messages[id_str] = [{"role": "system", "content": prompt}]
                await msg.reply(text="提示词已删除喵~本子娘回来了喵~")
            except FileNotFoundError:
                await msg.reply(text="没有可以删除的提示词喵~")

    else:
        if id_str in user_messages:
            del user_messages[id_str]
            try:
                os.remove(f"prompts/user/user_{id_str}.txt")
                with open("neko.txt", "r", encoding="utf-8") as file:
                    prompt = file.read()
                    user_messages[id_str] = [{"role": "system", "content": prompt}]
                await bot.api.post_private_msg(msg.user_id, text="提示词已删除喵~本子娘回来了喵~")
            except FileNotFoundError:
                await bot.api.post_private_msg(msg.user_id, text="没有可以删除的提示词喵~")

@register_command("/get_prompt")
@register_command("/gp")
async def handle_get_prompt(msg, is_group=True):
    id_str = str(msg.group_id if is_group else msg.user_id)
    if is_group:
        try:
            with open(f"prompts/group/group_{id_str}.txt", "r", encoding="utf-8") as file:
                prompt = file.read()
                await msg.reply(text=prompt)
        except FileNotFoundError:
            await msg.reply(text="没有找到提示词喵~")
    else:
        try:
            with open(f"prompts/user/user_{id_str}.txt", "r", encoding="utf-8") as file:
                prompt = file.read()
                await bot.api.post_private_msg(msg.user_id, text=prompt)
        except FileNotFoundError:
            await bot.api.post_private_msg(msg.user_id, text="没有找到提示词喵~")


@register_command("/agree") # 同意好友请求
async def handle_agree(msg, is_group=True):
    if not is_group:
        await bot.api.set_friend_add_request(flag=msg.user_id, approve=True,remark=msg.user_id)
        await bot.api.post_private_msg(msg.user_id, text="已同意好友请求喵~")
    else:
        await bot.api.set_friend_add_request(flag=msg.user_id, approve=True,remark=msg.user_id)
        await msg.reply(text="已同意好友请求喵~")


@register_command("/restart")
async def handle_restart(msg, is_group=True):
    reply_text = "正在重启喵~"
    if is_group:
        await msg.reply(text=reply_text)
    else:
        await bot.api.post_private_msg(msg.user_id, text=reply_text)
    # 重启逻辑
    os.execv(sys.executable, [sys.executable] + sys.argv)


@register_command("/random_image")
@register_command("/ri")
async def handle_random_image(msg, is_group=True):
    # 在urls.ini中获取图片的url列表
    config = configparser.ConfigParser()
    config.read('urls.ini')
    urls = json.loads(config['ri']['urls'])

    random_number = random.randint(0, len(urls)-1)
    image_path = urls[random_number]
    if is_group:
        await bot.api.post_group_file(msg.group_id, image=image_path)
    else:
        await bot.api.post_private_file(msg.user_id, image=image_path)

@register_command("/random_words")
@register_command("/rw")
async def handle_random_words(msg, is_group=True):
    words = requests.get("https://uapis.cn/api/say").text
    if is_group:
        await msg.reply(text=words)
    else:
        await bot.api.post_private_msg(msg.user_id, text=words)


@register_command("/weather")
@register_command("/w")
async def handle_weather(msg, is_group=True):
    location = None
    if msg.raw_message.startswith("/weather"):
        location = msg.raw_message[len("/weather"):].strip()
    elif msg.raw_message.startswith("/w"):
        location = msg.raw_message[len("/w"):].strip()
    if not location:
        reply_text = "格式错误喵~ 请输入 /weather 城市名"
    else:
        # 调用天气 API 获取数据
        res = requests.get(f"https://uapis.cn/api/weather?name={location}")
        weather = res.json().get("weather")
        weather_info = f"{location}的天气是 {weather} 喵~"
        reply_text = weather_info
    if is_group:
        await msg.reply(text=reply_text)
    else:
        await bot.api.post_private_msg(msg.user_id, text=reply_text)

@register_command("/random_emoticons")
@register_command("/re")
async def handle_random_emoticons(msg, is_group=True):
    #在urls.ini中获取表情包的url列表
    config = configparser.ConfigParser()
    config.read('urls.ini')
    urls = json.loads(config['re']['urls'])

    random_number = random.randint(0, len(urls)-1)
    if is_group:
        await bot.api.post_group_file(msg.group_id,image=urls[random_number])
    else:
        await bot.api.post_private_file(msg.user_id, image=urls[random_number])

@register_command("/st")
async def handle_st(msg, is_group=True):
    tags = msg.raw_message[len("/st"):].strip()
    res = requests.get(f"https://api.lolicon.app/setu/v2?tag={tags}").json().get("data")[0].get("urls").get("original")
    if is_group:
        await bot.api.post_group_file(msg.group_id,image=res)
    else:
        await bot.api.post_private_file(msg.user_id, image=res)


@register_command("/random_dice")
@register_command("/rd")
async def handle_random_dice(msg, is_group=True):

    if is_group:
        await bot.api.post_group_msg(msg.group_id,dice=True)
    else:
        await bot.api.post_private_msg(msg.user_id,dice=True)

@register_command("/random_rps")
@register_command("/rps")
async def handle_random_rps(msg, is_group=True):
    if is_group:
        await bot.api.post_group_msg(msg.group_id,rps=True)
    else:
        await bot.api.post_private_msg(msg.user_id,rps=True)

@register_command("/del_message")
@register_command("/dm")
async def handle_del_message(msg, is_group=True):
    if is_group:
        del group_messages[str(msg.group_id)]
        await msg.reply(text="主人要离我而去了吗？呜呜呜……好吧，那我们以后再见喵~")
    else:
        del user_messages[str(msg.user_id)]
        await bot.api.post_private_msg(msg.user_id, text="主人要离我而去了吗？呜呜呜……好吧，那我们以后再见喵~")

@register_command("/help")
@register_command("/h")
async def handle_help(msg, is_group=True):
    help_text = ("欢迎使用喵~~\n"
                 "/jm xxxxxx 下载漫画\n"
                 "/jmrank 月排行/周排行  获取月排行/周排行\n"
                 "/set_prompt 或 /sp 设置提示词\n"
                 "/del_prompt 或 /dp 删除提示词\n"
                 "/get_prompt 或 /gp 获取提示词\n"
                 "/agree 同意好友请求\n"
                 "/restart 重启Bot\n"
                 "/random_image 或 /ri 发送随机图片\n"
                 "/random_words 或 /rw 发送随机一言\n"
                 "/weather 城市名 或 /w 城市名 发送天气\n"
                 "/random_emoticons 或 /re 发送随机表情包\n"
                 "/random_dice 或 /rd 发送随机骰子\n"
                 "/random_rps 或 /rps 发送随机石头剪刀布\n"
                 "/st 标签名 发送随机涩图,标签支持与或(& |)\n"
                 "/del_message 或 /dm 删除对话记录\n"
                 "/tts 开启或关闭TTS\n"
                 "/help 或 /h 查看帮助"
    )
    if is_group:
        await msg.reply(text=help_text)
    else:
        await bot.api.post_private_msg(msg.user_id, text=help_text)
