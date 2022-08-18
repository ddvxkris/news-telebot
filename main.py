from telebot import types
from loguru import logger as log
import telebot, sqlite3

bot = telebot.TeleBot("yourtokenhere")

class NewsPost:
    title: str
    description: str
    author: str
    moderator_checking: bool = False

    def make_news_post(self) -> str:
        return f"<b>{self.title}</b>\n{self.description}\n\nАвтор: @{self.author}"

# содержит все данные локальные данные пользователя
# должна быть создана и помещена user_datas в стартовой функции start()
class UserData:
    def __init__(self, username: str):
        self.user = username
    user: str
    text_type: str = "start"

    news_create: NewsPost = NewsPost()

    mod_news_index: int = -1

user_datas = []
# ищет в user_datas данные пользователя по его нику
def find_user_data_index(username: str) -> int:
    for index in range(0, len(user_datas)):
        if user_datas[index].user == username:
            return index
    return -1

# новости на модерации, содержит в себе NewsPost'ы
news_on_moderate = []

def handle_user(func):
    def wrapper(message):
        if find_user_data_index(message.from_user.username) == -1:
            # проверяет модератора по имени из mod_names.txt, и заносит его chat.id в moderators.txt (если его там уже нет)
            # заносит chat.id потому что все функции из модерации руботают именно с chat.id
            if open("mod_names.txt", "r").read().split().__contains__(message.from_user.username) and not open("moderators.txt", "r").read().split().__contains__(str(message.chat.id)):
                open("moderators.txt", "a").write(f"{message.chat.id}\n")
                log.warning(f"Добавлен модератор по имени: {message.from_user.username}")
            user_datas.append(UserData(message.from_user.username))
            # проверяем chat_ids на наличие id нашего чата, если нету то заносим
        # используется для broadcast сообщений
        if not open("chat_ids.txt", "r").read().split().__contains__(str(message.chat.id)):
            open("chat_ids.txt", "a").write(str(message.chat.id) + "\n")
        func(message)
    return wrapper

# стартовая функция
@bot.message_handler(commands=["start", "help"])
@handle_user
def start(message):
    markup = types.ReplyKeyboardMarkup(True)
    user_datas[find_user_data_index(message.from_user.username)].text_type = "news"
    markup.add("Создать")
    markup.add("Последнее")
    markup.add("Найти")

    bot.send_message(message.chat.id, "<b>Привет!</b>\nЯ тестовый новостной бот. Ниже можешь найти <b>действия</b> которыми можешь воспольоваться",
                     parse_mode="html", reply_markup=markup)

def broadcast(text: str):
    for chat_id in open("chat_ids.txt", "r").read().split():
        bot.send_message(chat_id, text, "html")

# модерация
# функции реагирующие на сообщения должны содержать в начале функцию check_for_permissions(), которая проверяет
# является ли пользователь модератором
def check_for_permissions(chat_id) -> bool:
    chat_id = str(chat_id)
    for moderator_id in open("moderators.txt", "r").read().split():
        if chat_id == moderator_id:
            return True
    return False

# ищет индекс незанятой новости для модератора
def find_news_for_moderate_index() -> int:
    for index in range(0, len(news_on_moderate)):
        if not news_on_moderate[index].moderator_checking:
            return index
    return -1

# отправляет news_post на модерацию, а именно:
# добавляет её в массив news_on_moderate и рассылает всем модераторам уведомление о новой новости для модерации
def send_to_moderation(news_post: NewsPost):
    log.info(f"Отправлена новость на модерацию: {news_post.title}")
    news_on_moderate.append(news_post)
    for moderator_id in open("moderators.txt", "r").read().split():
        bot.send_message(moderator_id, f"Новый пост для модерирования от @{news_post.author}: {news_post.title}\n/moderate")

# высылает модератору свободный пост для модерации
@bot.message_handler(commands=["moderate"])
@handle_user
def moderate(message):
    if not check_for_permissions(message.chat.id):
        bot.send_message(message.chat.id, "У вас нет разрешения чтобы использовать эту команду!")
        return
    mod_index = find_user_data_index(message.from_user.username)
    news_index = find_news_for_moderate_index()
    if user_datas[mod_index].mod_news_index != -1:
        bot.send_message(message.chat.id, news_on_moderate[user_datas[mod_index].mod_news_index].make_news_post() + "\n\n/modpost /moddelete", "html")
    elif news_index != -1:
        user_datas[mod_index].mod_news_index = news_index
        news_on_moderate[news_index].moderator_checking = True
        bot.send_message(message.chat.id, news_on_moderate[news_index].make_news_post() + "\n\n/modpost /moddecline", "html")
    else:
        bot.send_message(message.chat.id, "Нет новостей для модерации.")

# удаляет пост с модерации
def delete_post_from_moderation(mod_index: int):
    for user_index in range(0, len(user_datas)):
        if user_datas[user_index].mod_news_index > user_datas[mod_index].mod_news_index:
            user_datas[user_index].mod_news_index -= 1
    news_on_moderate[user_datas[mod_index].mod_news_index].moderator_checking = False
    news_on_moderate.pop(user_datas[mod_index].mod_news_index)

# выкладывает новость
@bot.message_handler(commands=["modpost"])
@handle_user
def modpost(message):
    if not check_for_permissions(message.chat.id):
        bot.send_message(message.chat.id, "У вас нет разрешения чтобы использовать эту команду!")
        return
    mod_index = find_user_data_index(message.from_user.username)
    if user_datas[mod_index].mod_news_index == -1:
        bot.send_message(message.chat.id, "Нет новостей для публикации.\n/moderate")
        return
    db = sqlite3.connect("news.db")
    db_cur = db.cursor()
    news_to_post: NewsPost = news_on_moderate[user_datas[mod_index].mod_news_index]
    values_to_insert = [(news_to_post.title, news_to_post.description, news_to_post.author)]
    db_cur.executemany(f"INSERT INTO contents (title, description, author) VALUES (?,?,?)", values_to_insert)
    db.commit()
    broadcast(f"<b>НОВОСТИ:</b> {news_to_post.title}\nЧитайте больше в разделе последнее.")
    log.warning(f"Новость одобрена: {news_to_post.title}")
    delete_post_from_moderation(mod_index)
    user_datas[mod_index].mod_news_index = -1

# отклоняет новость
@bot.message_handler(commands=["moddecline"])
@handle_user
def moddelete(message):
    if not check_for_permissions(message.chat.id):
        bot.send_message(message.chat.id, "У вас нет разрешения чтобы использовать эту команду!")
        return
    mod_index = find_user_data_index(message.from_user.username)
    if user_datas[mod_index].mod_news_index == -1:
        bot.send_message(message.chat.id, "Нет новостей для отклонения.\n/moderate")
        return
    delete_post_from_moderation(mod_index)
    bot.send_message(message.chat.id, "Новость отклонена.")
    user_datas[mod_index].mod_news_index = -1

# принимает текст от пользователя, а потом решает с помощью text_type из user_data что делать с ним
@bot.message_handler(content_types=["text"])
@handle_user
def user_text_linker(message):
    index = find_user_data_index(message.from_user.username)
    if user_datas[index].text_type == "start" or message.text == "Назад":
        start(message)
    elif user_datas[index].text_type == "news" and message.text == "Создать":
        user_datas[index].text_type = "news.create.title"
        user_datas[index].news_create.author = message.from_user.username
        markup = types.ReplyKeyboardMarkup(True)
        markup.add("Назад")
        bot.send_message(message.chat.id, f"Введите <b>название</b> для вашей новости.", "html", reply_markup=markup)
    elif user_datas[index].text_type == "news" and message.text == "Последнее":
        db = sqlite3.connect("news.db")
        db_cur = db.cursor()
        db_cur.execute(f"SELECT * FROM contents ORDER BY rowid DESC")
        last_news = db_cur.fetchall()[0:5]
        last_news.reverse()
        if len(last_news) > 0:
            for news_post_raw in last_news:
                news_post = NewsPost()
                news_post.title = news_post_raw[0]
                news_post.description = news_post_raw[1]
                news_post.author = news_post_raw[2]
                bot.send_message(message.chat.id, news_post.make_news_post(), "html")
        else:
            bot.send_message(message.chat.id, "Новости отсутствуют")
    elif user_datas[index].text_type == "news" and message.text == "Найти":
        markup = types.ReplyKeyboardMarkup(True)
        markup.add("Назад")
        bot.send_message(message.chat.id, "Введите имя автора.", reply_markup=markup)
        user_datas[index].text_type = "news.search"
    elif user_datas[index].text_type == "news.search":
        db = sqlite3.connect("news.db")
        db_cur = db.cursor()
        try:
            db_cur.execute(f"SELECT * FROM contents WHERE author='{message.text.replace('@', '')}'")
        except sqlite3.OperationalError:
            bot.send_message(message.chat.id, "Использованы специальные символы!")
            return
        author_specified_news = db_cur.fetchall()
        if len(author_specified_news) > 0:
            for news_post_raw in author_specified_news:
                news_post = NewsPost()
                news_post.title = news_post_raw[0]
                news_post.description = news_post_raw[1]
                news_post.author = news_post_raw[2]
                bot.send_message(message.chat.id, news_post.make_news_post(), "html")
        else:
            bot.send_message(message.chat.id, "Нету новостей от этого автора.")
        start(message)

    # news create
    elif user_datas[index].text_type == "news.create.title":
        user_datas[index].news_create.title = f"{message.text}"
        user_datas[index].text_type = "news.create.description"

        bot.send_message(message.chat.id, f"Введите <b>описание</b> для ваших новостей.", parse_mode="html")
    elif user_datas[index].text_type == "news.create.description":
        user_datas[index].text_type = "news.create.confirm"
        user_datas[index].news_create.description = message.text

        bot.send_message(message.chat.id, "Это то что вы хотите?")

        markup = types.ReplyKeyboardMarkup()
        markup.add("Да")
        markup.add("Нет")

        bot.send_message(message.chat.id, user_datas[index].news_create.make_news_post(), parse_mode="html", reply_markup=markup)
    elif user_datas[index].text_type == "news.create.confirm" and message.text == "Да":
        send_to_moderation(user_datas[index].news_create)
        bot.send_message(message.chat.id, "Отлично! Ваши новости будут опубликованы после проверки модераторами.")
        start(message)
    elif user_datas[index].text_type == "news.create.confirm" and message.text == "Нет":
        start(message)
    else:
        bot.send_message(message.chat.id, f"Не <b>понял</b> вас. Пожалуйста попробуйте <b>ещё раз</b>.", "html")

bot.polling(True)
