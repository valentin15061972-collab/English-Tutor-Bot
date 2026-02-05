import telebot
import os
import json
import random
import sqlalchemy
from telebot.storage import StateMemoryStorage
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from telebot import types
from telebot.handler_backends import State, StatesGroup
from models_bot import Word, User, UserWord, Base


load_dotenv()
state_storage = StateMemoryStorage()
TOKEN = os.getenv('TOKEN_ET')
DSN = os.getenv('DSN')
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

engine = sqlalchemy.create_engine(DSN)
Session = sessionmaker(bind=engine)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


def load_db():
    with Session() as session:
        if session.query(Word).count() == 0:
            with open('data_bot.json', 'r', encoding='utf-8') as f:
                words = json.load(f)
            for w in words:
                session.add(Word(russian=w['russian'], english=w['english']))
            session.commit()


class Command:
    ADD_WORD = 'добавить ➕'
    DELETE_WORD = 'удалить 🔙'
    NEXT = 'дальше ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()


@bot.message_handler(commands=['start'])
def start_bot_greeting(message):
    bot.send_message(message.chat.id, 'Привет 👋 Давай попрактикуемся в английском языке. Чтоб начать введите команду /card')


@bot.message_handler(commands=['card'])
def start_bot(message):
    with Session() as session:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            user = User(telegram_id=message.from_user.id)
            session.add(user)
            session.commit()

        word = random.choice(session.query(Word).all())
        target_word = word.english
        russian_word = word.russian

        all_words = [w.english for w in session.query(Word).filter(Word.id != word.id).all()]
        wrong_words = random.sample(all_words, 3)

        markup = types.ReplyKeyboardMarkup(row_width=2)
        buttons = [types.KeyboardButton(w) for w in [target_word] + wrong_words]
        random.shuffle(buttons)
        buttons += [
            types.KeyboardButton(Command.NEXT),
            types.KeyboardButton(Command.ADD_WORD),
            types.KeyboardButton(Command.DELETE_WORD)
        ]
        markup.add(*buttons)

        bot.send_message(message.chat.id, f"Угадай слово: {russian_word}",
                         reply_markup=markup, parse_mode="Markdown")
        bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)

        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word'] = target_word
            data['russian_word'] = russian_word


@bot.message_handler(func=lambda message: message.text not in
                     [Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD],
                     content_types=['text'])
def check_answer(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
    if message.text == target_word:
        bot.send_message(message.chat.id, 'Правильно!', reply_markup=None)
    else:
        bot.send_message(message.chat.id, 'Неправильно! Попробуй ещё раз.')


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_word(message):
    start_bot(message)


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        english = data['target_word']

    session = Session()
    user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
    word = session.query(Word).filter(Word.english == english).first()

    if not session.query(UserWord).filter_by(user_id=user.id, word_id=word.id).first():
        session.add(UserWord(user_id=user.id, word_id=word.id))
        session.commit()
        bot.send_message(message.chat.id, f"'{english}' добавлено в словарь!")
    else:
        bot.send_message(message.chat.id, "Это слово уже есть в словаре.")
    session.close()


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        english = data['target_word']

    session = Session()
    user = (session.query(User).filter
            (User.telegram_id == message.from_user.id).first())
    word = session.query(Word).filter(Word.english == english).first()

    user_word = (session.query(UserWord).filter_by
                 (user_id=user.id, word_id=word.id).first())
    if user_word:
        session.delete(user_word)
        session.commit()
        bot.send_message(message.chat.id, f"Слово '{english}' удалено.")
    else:
        bot.send_message(message.chat.id, "Этого слова нет в словаре.")
    session.close()


if __name__ == '__main__':
    load_db()
    print('Бот запущен...')
bot.polling()
