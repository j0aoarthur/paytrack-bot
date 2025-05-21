from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, DateTime, event
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.engine import Engine
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./debt_manager.db")

# Habilitar FK para SQLite, se estiver usando
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Pessoa(Base):
    __tablename__ = "pessoas"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)

    # Relações com cascade para deleção
    emprestimos = relationship("Emprestimo", back_populates="pessoa", cascade="all, delete-orphan")
    pagamentos = relationship("Pagamento", back_populates="pessoa", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Pessoa(id={self.id}, nome='{self.nome}')>"

class Emprestimo(Base):
    __tablename__ = "emprestimos"
    id = Column(Integer, primary_key=True, index=True)
    valor = Column(Float, nullable=False)
    data = Column(Date, nullable=False)
    descricao = Column(String, nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    pessoa_id = Column(Integer, ForeignKey("pessoas.id", ondelete="CASCADE"), nullable=False)

    pessoa = relationship("Pessoa", back_populates="emprestimos")

    def __repr__(self):
        return f"<Emprestimo(id={self.id}, valor={self.valor}, pessoa_id={self.pessoa_id})>"

class Pagamento(Base):
    __tablename__ = "pagamentos"
    id = Column(Integer, primary_key=True, index=True)
    valor = Column(Float, nullable=False)
    data = Column(Date, nullable=False)
    descricao = Column(String, nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    pessoa_id = Column(Integer, ForeignKey("pessoas.id", ondelete="CASCADE"), nullable=False)

    pessoa = relationship("Pessoa", back_populates="pagamentos")

    def __repr__(self):
        return f"<Pagamento(id={self.id}, valor={self.valor}, pessoa_id={self.pessoa_id})>"

Base.metadata.create_all(bind=engine)

# Funções CRUD e de consulta (exemplos)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Funções CRUD de Pessoas ---
def db_add_pessoa(db: SessionLocal, nome: str) -> Pessoa | None:
    if db.query(Pessoa).filter(Pessoa.nome == nome).first():
        return None # Pessoa já existe
    nova_pessoa = Pessoa(nome=nome)
    db.add(nova_pessoa)
    db.commit()
    db.refresh(nova_pessoa)
    return nova_pessoa

def db_get_all_pessoas(db: SessionLocal) -> list[Pessoa]:
    return db.query(Pessoa).order_by(Pessoa.nome).all()

def db_get_pessoa_by_id(db: SessionLocal, pessoa_id: int) -> Pessoa | None:
    return db.query(Pessoa).filter(Pessoa.id == pessoa_id).first()

def db_edit_pessoa(db: SessionLocal, pessoa_id: int, novo_nome: str) -> Pessoa | None:
    pessoa = db_get_pessoa_by_id(db, pessoa_id)
    if pessoa:
        existing_person_with_new_name = db.query(Pessoa).filter(Pessoa.nome == novo_nome, Pessoa.id != pessoa_id).first()
        if existing_person_with_new_name:
            return None # Novo nome já em uso
        pessoa.nome = novo_nome
        db.commit()
        db.refresh(pessoa)
    return pessoa

def db_remove_pessoa(db: SessionLocal, pessoa_id: int) -> bool:
    pessoa = db_get_pessoa_by_id(db, pessoa_id)
    if pessoa:
        db.delete(pessoa) # Empréstimos e pagamentos serão removidos em cascata
        db.commit()
        return True
    return False

# --- Funções de Empréstimos e Pagamentos ---
def db_add_emprestimo(db: SessionLocal, pessoa_id: int, valor: float, data_str: str, descricao: str | None) -> Emprestimo:
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        # Tratar erro de data ou lançar exceção
        raise ValueError(f"Formato de data inválido: {data_str}. Use YYYY-MM-DD.")
    emprestimo = Emprestimo(pessoa_id=pessoa_id, valor=valor, data=data_obj, descricao=descricao)
    db.add(emprestimo)
    db.commit()
    db.refresh(emprestimo)
    return emprestimo

def db_add_pagamento(db: SessionLocal, pessoa_id: int, valor: float, data_str: str, descricao: str | None) -> Pagamento:
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Formato de data inválido: {data_str}. Use YYYY-MM-DD.")
    pagamento = Pagamento(pessoa_id=pessoa_id, valor=valor, data=data_obj, descricao=descricao)
    db.add(pagamento)
    db.commit()
    db.refresh(pagamento)
    return pagamento

def db_get_transacoes_pessoa(db: SessionLocal, pessoa_id: int) -> tuple[list[Emprestimo], list[Pagamento]]:
    emprestimos = db.query(Emprestimo).filter(Emprestimo.pessoa_id == pessoa_id).order_by(Emprestimo.data.desc(), Emprestimo.id.desc()).all()
    pagamentos = db.query(Pagamento).filter(Pagamento.pessoa_id == pessoa_id).order_by(Pagamento.data.desc(), Pagamento.id.desc()).all()
    return emprestimos, pagamentos