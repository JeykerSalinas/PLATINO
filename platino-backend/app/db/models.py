from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)

    topics = relationship("Topic", back_populates="module", cascade="all, delete")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)

    module = relationship("Module", back_populates="topics")
    documents = relationship("Document", back_populates="topic", cascade="all, delete")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

    documents = relationship("Document", back_populates="owner")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True, nullable=False)
    filepath = Column(String, nullable=False)
    thumbnail = Column(String, nullable=True)
    # "metadata" is reserved by SQLAlchemy's declarative system, so use a
    # different attribute name while keeping the same column name in the DB.
    file_metadata = Column("metadata", JSON, nullable=True)
    chunks = Column(JSON, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)

    owner = relationship("User", back_populates="documents")
    topic = relationship("Topic", back_populates="documents")
