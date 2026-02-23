import random
import os
from dotenv import load_dotenv
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from models_bot import Session, load_db, Word, User, UserWord


load_dotenv()
load_db()
print('Start telegram bot...')

state_storage = StateMemoryStorage()
token_bot = os.getenv('TOKEN')
bot = TeleBot(token_bot, state_storage=state_storage)

known_users = []
userStep = {}
buttons = []


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово'
    DELETE_WORD = 'Удалить слово'
    NEXT = 'Дальше'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    add_english = State()
    add_russian = State()
    delete_word = State()


def get_user_step(uid):
    if uid in userStep:
        return userStep[uid]
    else:
        known_users.append(uid)
        userStep[uid] = 0
        print("New user detected, who hasn't used \"/start\" yet")
        return 0


@bot.message_handler(commands=['start'])
def bot_greeting(message):
    bot.send_message(message.chat.id, 'Привет! Давай изучать английский язык.'
                                      'Чтобы начать, введи команду /card')


@bot.message_handler(commands=['card'])
def create_cards(message):
    cid = message.chat.id
    if cid not in known_users:
        known_users.append(cid)
        userStep[cid] = 0
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    with Session() as session:
        user = session.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            user = User(telegram_id=message.from_user.id)
            session.add(user)
            session.commit()

        word = random.choice(session.query(Word).all())
        target_word = word.english
        translate = word.russian
        other_words = [w.english for w in session.query(Word).filter(Word.id != word.id).all()]
        wrong_words = random.sample(other_words, 3)

        markup = types.ReplyKeyboardMarkup(row_width=2)
        buttons = [types.KeyboardButton(w) for w in [target_word] + wrong_words]
        random.shuffle(buttons)
        buttons += [
            types.KeyboardButton(Command.NEXT),
            types.KeyboardButton(Command.ADD_WORD),
            types.KeyboardButton(Command.DELETE_WORD)
        ]
        markup.add(*buttons)

    greeting = f"Выбери перевод слова: {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = other_words


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def start_delete_word(message):
    bot.set_state(message.from_user.id, MyStates.delete_word, message.chat.id)
    bot.send_message(message.chat.id, "Введите английское слово для удаления")


@bot.message_handler(state=MyStates.delete_word)
def delete_word(message):
    with Session() as session:
        word = message.text
        word_to_delete = session.query(Word).filter(Word.english == word.lower()).first()
        if delete_word:
            session.delete(word_to_delete)
            session.commit()
            bot.send_message(message.chat.id, f"Слово '{word_to_delete}' удалено.")
        else:
            bot.send_message(message.chat.id, f"Слова '{word_to_delete}' нет. Попробуйте снова.")


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    bot.send_message(message.chat.id, "Введите английское слово:")
    bot.set_state(message.from_user.id, MyStates.add_english, message.chat.id)


@bot.message_handler(state=MyStates.add_english)
def add_english(message):
    with Session() as session:
        english = message.text
        existing_word = session.query(Word).filter(Word.english == english).first()
        if not existing_word:
            new_word = Word(english=english, russian='unknown')
            session.add(new_word)
            session.commit()
            bot.set_state(message.from_user.id, MyStates.add_russian, message.chat.id)
            
            with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                data['new_word_id'] = new_word.id
            bot.send_message(message.chat.id, "Слово добавлено. Теперь введите перевод на русском:")
        else:
            bot.send_message(message.chat.id, "Слово уже есть в базе")
            bot.delete_state(message.from_user.id, message.chat.id)


@bot.message_handler(state=MyStates.add_russian)
def add_russian(message):
    with Session() as session:
        russian = message.text
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            word_id = data.get('new_word_id')
        if not word_id:
            bot.send_message(message.chat.id, "Произошла ошибка: не найдено английское слово.")
            bot.delete_state(message.from_user.id, message.chat.id)
            return
        word_to_update = session.query(Word).get(word_id)
        if not word_to_update:
            bot.send_message(message.chat.id, "Ошибка: слово не найдено в базе.")
            bot.delete_state(message.from_user.id, message.chat.id)
            return
        existing_word = session.query(Word).filter(Word.russian == russian).first()
        if existing_word:
            bot.send_message(message.chat.id, "Слово на русском уже существует в базе.")
            bot.delete_state(message.from_user.id, message.chat.id)
            return
        word_to_update.russian = russian
        session.commit()

        bot.send_message(message.chat.id, "Перевод добавлен! Слово успешно обновлено.")
        bot.delete_state(message.from_user.id, message.chat.id)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def check_answer(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            hint = show_target(data)
            hint_text = ["Отлично!", hint]
            hint = show_hint(*hint_text)
        else:
            for btn in buttons:
                if btn.text == text:
                    btn.text = text + '❌'
                    break
            hint = show_hint("Допущена ошибка!",
                             f"Попробуй ещё раз вспомнить слово {data['translate_word']}")
    markup.add(*buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)


bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.infinity_polling(skip_pending=True)
