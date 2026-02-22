import sqlalchemy
import os
import json
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sqlalchemy import Column, String, Integer, ForeignKey, BigInteger
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()
load_dotenv()
DSN = os.getenv('DSN')
engine = sqlalchemy.create_engine(DSN)
Session = sessionmaker(bind=engine)


class Word(Base):
    __tablename__ = 'words'
    id = Column(Integer, primary_key=True)
    russian = Column(String, nullable=False)
    english = Column(String, nullable=False)
    def __str__(self):
        return f"{self.english} - {self.russian}"

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)


class UserWord(Base):
    __tablename__ = 'user_words'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    word_id = Column(Integer, ForeignKey('words.id'))

    user = relationship("User", backref="user_words")
    word = relationship("Word", backref="user_words")


def load_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session() as session:
        if session.query(Word).count() == 0:
            with open('data_bot.json', 'r', encoding='utf-8') as f:
                words = json.load(f)
            for w in words:
                session.add(Word(russian=w['russian'], english=w['english']))
            session.commit()
