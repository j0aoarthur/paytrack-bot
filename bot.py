import asyncio
import logging
import os
from dotenv import load_dotenv
from datetime import datetime, date as DateObject # Renomeado para evitar conflito

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode, ChatAction


# Carregar variáveis de ambiente
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Token do Telegram não encontrado. Defina TELEGRAM_BOT_TOKEN no .env")

# Importar do projeto
from database import (
    get_db, Pessoa, Emprestimo, Pagamento,
    db_add_pessoa, db_get_all_pessoas, db_get_pessoa_by_id,
    db_edit_pessoa, db_remove_pessoa, db_add_emprestimo,
    db_add_pagamento, db_get_transacoes_pessoa, SessionLocal
)
from gemini_service import extract_transaction_data

# Configuração de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados da ConversationHandler
# Para Pessoas
TYPING_PESSOA_NOME, CONFIRM_PESSOA_EDIT_NOME, SELECT_PESSOA_TO_EDIT, SELECT_PESSOA_TO_REMOVE, CONFIRM_PESSOA_REMOVE = range(5)
# Para Transações (Empréstimos/Pagamentos)
SELECT_PESSOA_TRANSACAO, TYPING_TRANSACAO_DETALHES, CONFIRM_TRANSACAO = range(5, 8) # Continuar a numeração
# Para Status
SELECT_PESSOA_STATUS = range(8,9)


# --- Funções Auxiliares ---
def get_pessoas_keyboard(callback_prefix: str, include_cancel=True, db_session=None):
    """Cria um teclado inline com as pessoas cadastradas."""
    close_session_locally = False
    if db_session is None:
        db_session = next(get_db())
        close_session_locally = True

    pessoas = db_get_all_pessoas(db_session)
    keyboard = []
    if not pessoas:
        keyboard.append([InlineKeyboardButton("Nenhuma pessoa cadastrada.", callback_data="no_pessoas_found")])
    else:
        for p in pessoas:
            keyboard.append([InlineKeyboardButton(p.nome, callback_data=f"{callback_prefix}_{p.id}")])
    
    if include_cancel:
        keyboard.append([InlineKeyboardButton("↩️ Cancelar", callback_data="cancel_operation")])

    if close_session_locally:
        db_session.close()
    return InlineKeyboardMarkup(keyboard) if keyboard else None

# --- Comando /start ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Olá, {user.mention_html()}! 👋"
        "\nSou seu assistente para controle de dívidas."
        "\n\nUse os comandos abaixo:"
        "\n/pessoas - 🧍 Gerenciar pessoas devedoras"
        "\n/emprestimos - 💸 Registrar novo empréstimo"
        "\n/pagamentos - 💰 Registrar pagamento recebido"
        "\n/status - 📊 Ver status de um devedor"
        "\n/cancel - ❌ Cancelar operação atual",
        reply_markup=ReplyKeyboardRemove() # Remove qualquer teclado customizado anterior
    )
    return ConversationHandler.END # Garante que qualquer conversa anterior seja encerrada


# --- Gerenciamento de Pessoas (/pessoas) ---
async def pessoas_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("➕ Adicionar Pessoa", callback_data="add_pessoa_start")],
        [InlineKeyboardButton("📝 Editar Pessoa", callback_data="edit_pessoa_select")],
        [InlineKeyboardButton("➖ Remover Pessoa", callback_data="remove_pessoa_select")],
        [InlineKeyboardButton("📋 Listar Pessoas", callback_data="list_pessoas")],
        [InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "🛠️ *Gerenciamento de Pessoas*\n\nEscolha uma opção:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# Listar Pessoas
async def list_pessoas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = next(get_db())
    pessoas = db_get_all_pessoas(db)
    db.close()

    message_text = "📋 *Pessoas Cadastradas*\n\n"
    if not pessoas:
        message_text += "_Nenhuma pessoa cadastrada ainda._"
    else:
        for p in pessoas:
            message_text += f"- {p.nome}\n" # Não mostrar ID aqui para o usuário final

    keyboard = [[InlineKeyboardButton("↩️ Voltar ao Menu Pessoas", callback_data="pessoas_menu_refresh")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# Adicionar Pessoa - Início
async def add_pessoa_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="✏️ Digite o nome completo da pessoa que deseja adicionar:")
    return TYPING_PESSOA_NOME

# Adicionar Pessoa - Receber Nome
async def add_pessoa_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nome_pessoa = update.message.text.strip()
    if not nome_pessoa or len(nome_pessoa) < 3:
        await update.message.reply_text("Nome muito curto ou inválido. Por favor, digite um nome com pelo menos 3 caracteres.")
        return TYPING_PESSOA_NOME

    db = next(get_db())
    pessoa_existente = db.query(Pessoa).filter(Pessoa.nome == nome_pessoa).first()
    if pessoa_existente:
        await update.message.reply_text(f"⚠️ A pessoa '{nome_pessoa}' já está cadastrada. Tente outro nome ou edite a existente.")
        db.close()
        # Voltar ao menu de pessoas ou pedir novo nome
        await pessoas_menu_command(update, context) # Reexibe o menu de pessoas
        return ConversationHandler.END
    
    nova_pessoa = db_add_pessoa(db, nome_pessoa)
    db.close()

    if nova_pessoa:
        await update.message.reply_text(f"✅ Pessoa '{nova_pessoa.nome}' adicionada com sucesso!")
    else: # Deve ser pego pelo check de existente, mas como fallback
        await update.message.reply_text(f"⚠️ Ops! Não foi possível adicionar '{nome_pessoa}'. Já existe ou ocorreu um erro.")

    await pessoas_menu_command(update, context) # Reexibe o menu de pessoas
    return ConversationHandler.END

# Editar Pessoa - Selecionar
async def edit_pessoa_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db = next(get_db())
    reply_markup = get_pessoas_keyboard(callback_prefix="edit_p_id", db_session=db)
    db.close()

    if not reply_markup or not db_get_all_pessoas(next(get_db())): # Verifica se há pessoas
        await query.edit_message_text("🚫 Nenhuma pessoa cadastrada para editar.\nAdicione uma pessoa primeiro usando /pessoas.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Voltar ao Menu Pessoas", callback_data="pessoas_menu_refresh")]]))
        return ConversationHandler.END

    await query.edit_message_text("📝 Selecione a pessoa que deseja editar:", reply_markup=reply_markup)
    return SELECT_PESSOA_TO_EDIT

# Editar Pessoa - Guardar ID e pedir novo nome
async def edit_pessoa_ask_new_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pessoa_id = int(query.data.split("_")[-1])
    context.user_data["pessoa_id_to_edit"] = pessoa_id
    db = next(get_db())
    pessoa = db_get_pessoa_by_id(db, pessoa_id)
    db.close()

    if not pessoa:
        await query.edit_message_text("⚠️ Pessoa não encontrada. Pode ter sido removida.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Voltar ao Menu Pessoas", callback_data="pessoas_menu_refresh")]]))
        return ConversationHandler.END

    await query.edit_message_text(f"Editando '{pessoa.nome}'.\n✏️ Digite o novo nome para esta pessoa:")
    return CONFIRM_PESSOA_EDIT_NOME

# Editar Pessoa - Receber e Salvar Novo Nome
async def edit_pessoa_receive_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    novo_nome = update.message.text.strip()
    pessoa_id = context.user_data.get("pessoa_id_to_edit")

    if not novo_nome or len(novo_nome) < 3:
        await update.message.reply_text("Nome muito curto ou inválido. Digite um nome com pelo menos 3 caracteres.")
        return CONFIRM_PESSOA_EDIT_NOME
    if not pessoa_id:
        await update.message.reply_text("⚠️ Erro: ID da pessoa não encontrado. Tente novamente a partir do menu /pessoas.")
        await pessoas_menu_command(update, context)
        return ConversationHandler.END

    db = next(get_db())
    pessoa_editada = db_edit_pessoa(db, pessoa_id, novo_nome)
    
    if pessoa_editada:
        await update.message.reply_text(f"✅ Nome da pessoa atualizado para '{pessoa_editada.nome}'.")
    else:
        # Verificar se o nome já existe
        existing_person = db.query(Pessoa).filter(Pessoa.nome == novo_nome).first()
        if existing_person:
            await update.message.reply_text(f"⚠️ Não foi possível atualizar. O nome '{novo_nome}' já está em uso por outra pessoa.")
        else:
            await update.message.reply_text("⚠️ Não foi possível atualizar. A pessoa pode não ter sido encontrada.")
    db.close()
    del context.user_data["pessoa_id_to_edit"]
    await pessoas_menu_command(update, context)
    return ConversationHandler.END

# Remover Pessoa - Selecionar
async def remove_pessoa_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db = next(get_db())
    reply_markup = get_pessoas_keyboard(callback_prefix="remove_p_id", db_session=db)
    db.close()

    if not reply_markup or not db_get_all_pessoas(next(get_db())):
        await query.edit_message_text("🚫 Nenhuma pessoa cadastrada para remover.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Voltar ao Menu Pessoas", callback_data="pessoas_menu_refresh")]]))
        return ConversationHandler.END
    
    await query.edit_message_text("➖ Selecione a pessoa que deseja remover:", reply_markup=reply_markup)
    return SELECT_PESSOA_TO_REMOVE

# Remover Pessoa - Confirmar
async def remove_pessoa_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pessoa_id = int(query.data.split("_")[-1])
    context.user_data["pessoa_id_to_remove"] = pessoa_id
    db = next(get_db())
    pessoa = db_get_pessoa_by_id(db, pessoa_id)
    db.close()

    if not pessoa:
        await query.edit_message_text("⚠️ Pessoa não encontrada. Pode ter sido removida.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Voltar ao Menu Pessoas", callback_data="pessoas_menu_refresh")]]))
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(f"🗑️ SIM, remover '{pessoa.nome}'", callback_data=f"confirm_remove_{pessoa_id}")],
        [InlineKeyboardButton("❌ NÃO, cancelar", callback_data="cancel_operation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"🚨 *ATENÇÃO* 🚨\nTem certeza que deseja remover '{pessoa.nome}'?\n"
        "Todos os empréstimos e pagamentos associados a esta pessoa também serão apagados.\n"
        "*Esta ação é irreversível!*",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    return CONFIRM_PESSOA_REMOVE

# Remover Pessoa - Executar Remoção
async def remove_pessoa_execute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pessoa_id = int(query.data.split("_")[-1]) # confirm_remove_ID
    
    # Segurança extra: verificar se o ID no callback corresponde ao ID em user_data
    if context.user_data.get("pessoa_id_to_remove") != pessoa_id:
        await query.edit_message_text("⚠️ Erro de confirmação. Operação cancelada por segurança.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Voltar ao Menu Pessoas", callback_data="pessoas_menu_refresh")]]))
        if "pessoa_id_to_remove" in context.user_data: del context.user_data["pessoa_id_to_remove"]
        return ConversationHandler.END

    db = next(get_db())
    pessoa_removida = db_get_pessoa_by_id(db, pessoa_id) # Pega o nome antes de remover
    nome_removido = pessoa_removida.nome if pessoa_removida else "Pessoa desconhecida"
    
    sucesso = db_remove_pessoa(db, pessoa_id)
    db.close()

    if sucesso:
        await query.edit_message_text(f"🗑️ Pessoa '{nome_removido}' e todos os seus dados foram removidos com sucesso.")
    else:
        await query.edit_message_text(f"⚠️ Não foi possível remover '{nome_removido}'. Pode já ter sido removida ou ocorreu um erro.")
    
    if "pessoa_id_to_remove" in context.user_data: del context.user_data["pessoa_id_to_remove"]
    await query.message.reply_text("Use /pessoas para mais opções.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ir para Menu Pessoas", callback_data="pessoas_menu_refresh")]]))
    return ConversationHandler.END


# --- Transações (Empréstimos e Pagamentos) ---
async def transaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE, transaction_type: str) -> int:
    """Inicia o fluxo de empréstimo ou pagamento."""
    context.user_data["transaction_type"] = transaction_type
    db = next(get_db())
    reply_markup = get_pessoas_keyboard(callback_prefix=f"trans_sel_p", db_session=db) # trans_sel_p_ID
    db.close()

    action_verb = "um empréstimo" if transaction_type == "emprestimo" else "um pagamento"
    icon = "💸" if transaction_type == "emprestimo" else "💰"

    if not reply_markup or not db_get_all_pessoas(next(get_db())):
        message_text = f"🚫 Nenhuma pessoa cadastrada para registrar {action_verb}.\nAdicione uma pessoa primeiro usando /pessoas."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(message_text)
        else:
            await update.message.reply_text(message_text)
        return ConversationHandler.END

    message_text = f"{icon} Para quem você deseja registrar {action_verb}?"
    if update.callback_query: # Se vindo de um menu, por exemplo
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else: # Se vindo de um comando direto
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    return SELECT_PESSOA_TRANSACAO

async def emprestimos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await transaction_start(update, context, "emprestimo")

async def pagamentos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await transaction_start(update, context, "pagamento")

# Transação - Pessoa Selecionada
async def transaction_person_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pessoa_id = int(query.data.split("_")[-1]) # trans_sel_p_ID
    context.user_data["selected_person_id"] = pessoa_id
    
    db = next(get_db())
    pessoa = db_get_pessoa_by_id(db, pessoa_id)
    db.close()

    if not pessoa:
        await query.edit_message_text("⚠️ Pessoa não encontrada. Tente novamente.")
        return SELECT_PESSOA_TRANSACAO # Volta para a seleção

    transaction_type = context.user_data["transaction_type"]
    action_verb = "empréstimo" if transaction_type == "emprestimo" else "pagamento"
    icon = "💸" if transaction_type == "emprestimo" else "💰"
    
    await query.edit_message_text(
        f"{icon} Registrando {action_verb} para *{pessoa.nome}*.\n\n"
        "Por favor, digite os detalhes em linguagem natural. Exemplo:\n"
        f"`{ 'Emprestei 150.50 reais ontem para o lanche' if transaction_type == 'emprestimo' else 'Ela pagou 100 reais hoje referente à fatura' }`",
        parse_mode=ParseMode.MARKDOWN
    )
    return TYPING_TRANSACAO_DETALHES

# Transação - Detalhes Recebidos (Linguagem Natural)
async def transaction_details_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    transaction_type = context.user_data["transaction_type"]
    
    await update.message.reply_chat_action(ChatAction.TYPING) # Informa que está processando
    extracted_data = extract_transaction_data(user_text, transaction_type)

    if extracted_data.get("error"):
        await update.message.reply_text(
            f"⚠️ Erro ao processar sua mensagem com a IA:\n`{extracted_data['error']}`\n\n"
            "Por favor, tente novamente com mais clareza. Exemplo:\n"
            f"`{ 'Emprestei 150.50 reais ontem para o lanche' if transaction_type == 'emprestimo' else 'Ela pagou 100 reais hoje referente à fatura' }`",
            parse_mode=ParseMode.MARKDOWN
        )
        return TYPING_TRANSACAO_DETALHES # Volta para pedir detalhes

    context.user_data["extracted_transaction_data"] = extracted_data
    
    # Preparar resumo para confirmação
    db = next(get_db())
    pessoa = db_get_pessoa_by_id(db, context.user_data["selected_person_id"])
    db.close()

    try:
        data_obj = datetime.strptime(extracted_data['data'], "%Y-%m-%d").date()
        data_formatada = data_obj.strftime("%d/%m/%Y")
    except ValueError:
        data_formatada = extracted_data['data'] # Mantém como string se não puder formatar

    resumo_msg = (
        f"📝 *Confirme os Dados do {transaction_type.capitalize()}*\n\n"
        f"👤 *Pessoa:* {pessoa.nome}\n"
        f"💰 *Valor:* R$ {float(extracted_data['valor']):.2f}\n"
        f"🗓️ *Data:* {data_formatada}\n"
        f"🧾 *Descrição:* {extracted_data.get('descricao', 'N/A')}\n\n"
        "Salvar esta transação?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Salvar", callback_data="trans_confirm_save")],
        [InlineKeyboardButton("✏️ Editar Novamente", callback_data="trans_edit_again")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_operation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(resumo_msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_TRANSACAO

# Transação - Confirmação para Salvar
async def transaction_confirm_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    extracted_data = context.user_data.get("extracted_transaction_data")
    pessoa_id = context.user_data.get("selected_person_id")
    transaction_type = context.user_data.get("transaction_type")

    if not all([extracted_data, pessoa_id is not None, transaction_type]):
        await query.edit_message_text("⚠️ Erro: Dados da transação perdidos. Tente novamente.")
        # Limpar dados da conversa mesmo em caso de erro antes de sair
        keys_to_clear = ['transaction_type', 'selected_person_id', 'extracted_transaction_data']
        for key in keys_to_clear:
            if key in context.user_data:
                del context.user_data[key]
        return ConversationHandler.END

    db = next(get_db())
    try:
        if transaction_type == "emprestimo":
            db_add_emprestimo(db, pessoa_id, float(extracted_data['valor']), extracted_data['data'], extracted_data.get('descricao'))
            icon = "💸"
        elif transaction_type == "pagamento":
            db_add_pagamento(db, pessoa_id, float(extracted_data['valor']), extracted_data['data'], extracted_data.get('descricao'))
            icon = "💰"
        else:
            await query.edit_message_text("⚠️ Tipo de transação desconhecido.")
            db.close()
            # Limpar dados da conversa
            keys_to_clear = ['transaction_type', 'selected_person_id', 'extracted_transaction_data']
            for key in keys_to_clear:
                if key in context.user_data:
                    del context.user_data[key]
            return ConversationHandler.END
        
        pessoa = db_get_pessoa_by_id(db, pessoa_id) # Para pegar o nome
        await query.edit_message_text(f"{icon} {transaction_type.capitalize()} para *{pessoa.nome}* salvo com sucesso!", parse_mode=ParseMode.MARKDOWN)
        
        # Limpar dados da conversa ANTES de chamar o main_menu
        keys_to_clear = ['transaction_type', 'selected_person_id', 'extracted_transaction_data']
        for key in keys_to_clear:
            if key in context.user_data:
                del context.user_data[key]
        
        # Pausa curta para o usuário ler a mensagem de sucesso
        await asyncio.sleep(2) # Pausa de 2 segundos

        # Chamar o menu principal
        # A função main_menu_callback espera 'update' e 'context'.
        # O 'update' que temos aqui é o da CallbackQuery, que main_menu_callback pode manipular.
        return await main_menu_callback(update, context) # main_menu_callback já retorna ConversationHandler.END

    except ValueError as ve: # Erro de conversão de data/valor no DB
        logger.error(f"Erro ao salvar transação no DB (ValueError): {ve}")
        await query.edit_message_text(f"⚠️ Erro ao salvar: {str(ve)}. Verifique os dados e tente novamente.")
        # Limpar dados da conversa
        keys_to_clear = ['transaction_type', 'selected_person_id', 'extracted_transaction_data']
        for key in keys_to_clear:
            if key in context.user_data:
                del context.user_data[key]
        return ConversationHandler.END # Encerra a conversa aqui em caso de erro de valor
    except Exception as e:
        logger.error(f"Erro genérico ao salvar transação no DB: {e}")
        await query.edit_message_text(f"⚠️ Ocorreu um erro inesperado ao salvar o {transaction_type}. Tente novamente mais tarde.")
        # Limpar dados da conversa
        keys_to_clear = ['transaction_type', 'selected_person_id', 'extracted_transaction_data']
        for key in keys_to_clear:
            if key in context.user_data:
                del context.user_data[key]
        return ConversationHandler.END # Encerra a conversa aqui em caso de erro genérico
    finally:
        db.close()

    # Se o fluxo chegar aqui por algum motivo inesperado (não deveria com o return await main_menu_callback),
    # certifique-se de limpar e encerrar.
    # keys_to_clear = ['transaction_type', 'selected_person_id', 'extracted_transaction_data']
    # for key in keys_to_clear:
    #     if key in context.user_data:
    #         del context.user_data[key]
    # return ConversationHandler.END

# Transação - Editar Novamente
async def transaction_edit_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    transaction_type = context.user_data["transaction_type"]
    db = next(get_db())
    pessoa = db_get_pessoa_by_id(db, context.user_data["selected_person_id"])
    db.close()

    action_verb = "empréstimo" if transaction_type == "emprestimo" else "pagamento"
    icon = "💸" if transaction_type == "emprestimo" else "💰"

    await query.edit_message_text(
        f"{icon} Editando {action_verb} para *{pessoa.nome}*.\n\n"
        "Por favor, digite os detalhes novamente em linguagem natural:",
        parse_mode=ParseMode.MARKDOWN
    )
    # Não limpe 'transaction_type' e 'selected_person_id'
    if 'extracted_transaction_data' in context.user_data:
        del context.user_data['extracted_transaction_data'] # Limpa os dados anteriores para nova extração
    return TYPING_TRANSACAO_DETALHES


# --- Comando /status ---
async def status_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = next(get_db())
    reply_markup = get_pessoas_keyboard(callback_prefix="status_sel_p", db_session=db)
    db.close()

    if not reply_markup or not db_get_all_pessoas(next(get_db())) :
        message_text = "🚫 Nenhuma pessoa cadastrada para ver o status.\nAdicione uma pessoa primeiro usando /pessoas."
        if update.callback_query: # Se vindo de um menu de refresh
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(message_text)
        else:
            await update.message.reply_text(message_text)
        return ConversationHandler.END

    message_text = "📊 Selecione a pessoa para ver o status financeiro:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    return SELECT_PESSOA_STATUS

async def status_person_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pessoa_id = int(query.data.split("_")[-1]) # status_sel_p_ID

    db = next(get_db())
    pessoa = db_get_pessoa_by_id(db, pessoa_id)
    if not pessoa:
        await query.edit_message_text("⚠️ Pessoa não encontrada.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Tentar Novamente", callback_data="status_refresh")]]))
        db.close()
        return SELECT_PESSOA_STATUS # Volta para seleção


    emprestimos, pagamentos = db_get_transacoes_pessoa(db, pessoa_id)
    db.close()

    message_text = f"📊 *Status Financeiro de {pessoa.nome}*\n\n"
    total_emprestimos = sum(e.valor for e in emprestimos)
    total_pagamentos = sum(p.valor for p in pagamentos)
    saldo_devedor = total_emprestimos - total_pagamentos

    message_text += "💸 *EMPRÉSTIMOS CONCEDIDOS:*\n"
    if emprestimos:
        for e in sorted(emprestimos, key=lambda x: x.data): # Ordenar por data
            data_fmt = e.data.strftime('%d/%m/%Y') if isinstance(e.data, DateObject) else e.data
            message_text += f"- R$ {e.valor:.2f} em {data_fmt} ({e.descricao or 'Sem descrição'})\n"
    else:
        message_text += "_Nenhum empréstimo registrado._\n"
    message_text += f"*Total Emprestado:* R$ {total_emprestimos:.2f}\n\n"

    message_text += "💰 *PAGAMENTOS RECEBIDOS:*\n"
    if pagamentos:
        for p_obj in sorted(pagamentos, key=lambda x: x.data): # Ordenar por data
            data_fmt = p_obj.data.strftime('%d/%m/%Y') if isinstance(p_obj.data, DateObject) else p_obj.data
            message_text += f"- R$ {p_obj.valor:.2f} em {data_fmt} ({p_obj.descricao or 'Sem descrição'})\n"
    else:
        message_text += "_Nenhum pagamento registrado._\n"
    message_text += f"*Total Pago:* R$ {total_pagamentos:.2f}\n\n"

    message_text += "⚖️ *SALDO ATUAL:*\n"
    if saldo_devedor > 0:
        message_text += f"*{pessoa.nome} deve R$ {saldo_devedor:.2f}*"
    elif saldo_devedor < 0:
        message_text += f"*Você tem um crédito de R$ {abs(saldo_devedor):.2f} com {pessoa.nome}*"
    else:
        message_text += f"*Não há saldo pendente para {pessoa.nome}. Quite!*"
    
    message_text += "\n" # Adiciona uma linha em branco ao final para melhor espaçamento

    keyboard = [[InlineKeyboardButton("↩️ Ver status de outra pessoa", callback_data="status_refresh")],
                [InlineKeyboardButton("🏠 Voltar ao Menu Principal", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Verifica se a mensagem é muito longa para o Telegram
    if len(message_text) > 4096:
        # Se for muito longa, envia em partes ou um resumo
        await query.edit_message_text("O histórico desta pessoa é muito longo. Mostrando um resumo:\n"
                                      f"Total Emprestado: R$ {total_emprestimos:.2f}\n"
                                      f"Total Pago: R$ {total_pagamentos:.2f}\n"
                                      f"Saldo Devedor: R$ {saldo_devedor:.2f}", reply_markup=reply_markup)
    else:
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    return SELECT_PESSOA_STATUS # Permite selecionar outra pessoa ou voltar ao menu


# --- Funções de Cancelamento e Retorno ---
async def cancel_operation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    message_text = "❌ Operação cancelada."
    
    # Limpar user_data relevantes para evitar contaminação de fluxos
    keys_to_clear = [
        "pessoa_id_to_edit", "pessoa_id_to_remove",
        "transaction_type", "selected_person_id", "extracted_transaction_data"
    ]
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]

    if query:
        await query.answer()
        # Tenta editar a mensagem, se falhar (ex: mensagem original não é mais editável), envia nova
        try:
            await query.edit_message_text(text=message_text)
        except Exception:
             if query.message: await query.message.reply_text(text=message_text)
    elif update.message: # Se o cancelamento veio de um comando /cancel
        await update.message.reply_text(text=message_text)

    # Re-exibir o menu principal pode ser uma boa UX após cancelar
    # Chamando uma função que simula o /start ou um menu principal de botões inline
    # await start_command(update, context) # Cuidado: start_command espera update.message
    # Por agora, apenas encerra a conversa. O usuário pode usar /start novamente.
    return ConversationHandler.END

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Retorna ao menu principal (simulando /start com botões)."""
    query = update.callback_query
    if query: await query.answer()
    
    # Limpa qualquer estado de conversa pendente
    keys_to_clear = [
        "pessoa_id_to_edit", "pessoa_id_to_remove",
        "transaction_type", "selected_person_id", "extracted_transaction_data"
    ]
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]

    user = update.effective_user
    message_text = (
        rf"Olá, {user.mention_html()}! 👋"
        "\nO que você gostaria de fazer agora?"
        "\n\nUse os comandos ou botões abaixo:"
        "\n/pessoas - 🧍 Gerenciar pessoas"
        "\n/emprestimos - 💸 Registrar empréstimo"
        "\n/pagamentos - 💰 Registrar pagamento"
        "\n/status - 📊 Ver status"
    )
    # Reutilizar o menu de /pessoas para uma navegação mais fluida via botões
    keyboard = [
        [InlineKeyboardButton("🧍 Gerenciar Pessoas", callback_data="pessoas_menu_refresh")],
        [InlineKeyboardButton("💸 Registrar Empréstimo", callback_data="start_emprestimo")], # Precisa de um entry point
        [InlineKeyboardButton("💰 Registrar Pagamento", callback_data="start_pagamento")],   # Precisa de um entry point
        [InlineKeyboardButton("📊 Ver Status", callback_data="status_refresh")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        try:
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e: # Se a mensagem não puder ser editada
            logger.warning(f"Não foi possível editar mensagem para main_menu: {e}")
            if query.message: await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else: # Fallback se query.message não existir (improvável para callback)
                effective_chat_id = update.effective_chat.id
                await context.bot.send_message(chat_id=effective_chat_id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    elif update.message: # Se chamado por um comando /menu por exemplo
         await update.message.reply_html(message_text, reply_markup=reply_markup)

    return ConversationHandler.END # Encerra qualquer conversa ativa


# --- Configuração dos Handlers ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Comando /start
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))


    # ConversationHandler para Pessoas
    pessoas_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("pessoas", pessoas_menu_command),
            CallbackQueryHandler(pessoas_menu_command, pattern="^pessoas_menu_refresh$"),
            CallbackQueryHandler(add_pessoa_start_callback, pattern="^add_pessoa_start$"),
            CallbackQueryHandler(edit_pessoa_select_callback, pattern="^edit_pessoa_select$"),
            CallbackQueryHandler(remove_pessoa_select_callback, pattern="^remove_pessoa_select$"),
        ],
        states={
            TYPING_PESSOA_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pessoa_receive_name)],
            SELECT_PESSOA_TO_EDIT: [CallbackQueryHandler(edit_pessoa_ask_new_name_callback, pattern="^edit_p_id_\\d+$")],
            CONFIRM_PESSOA_EDIT_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pessoa_receive_new_name)],
            SELECT_PESSOA_TO_REMOVE: [CallbackQueryHandler(remove_pessoa_confirm_callback, pattern="^remove_p_id_\\d+$")],
            CONFIRM_PESSOA_REMOVE: [CallbackQueryHandler(remove_pessoa_execute_callback, pattern="^confirm_remove_\\d+$")],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_operation_callback, pattern="^cancel_operation$"),
            CommandHandler("cancel", cancel_operation_callback), # Comando /cancel global
            CommandHandler("start", start_command) # /start também pode cancelar e levar ao menu
        ],
        map_to_parent={ # Para sair da conversa e voltar ao fluxo normal ou outra conversa
            ConversationHandler.END: ConversationHandler.END
        }
    )
    application.add_handler(pessoas_conv_handler)
    application.add_handler(CallbackQueryHandler(list_pessoas_callback, pattern="^list_pessoas$")) # Handler simples, não parte de conv

    # ConversationHandler para Transações (Empréstimos/Pagamentos)
    transaction_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("emprestimos", emprestimos_command),
            CommandHandler("pagamentos", pagamentos_command),
            CallbackQueryHandler(emprestimos_command, pattern="^start_emprestimo$"), # Para botão do menu principal
            CallbackQueryHandler(pagamentos_command, pattern="^start_pagamento$"),   # Para botão do menu principal
        ],
        states={
            SELECT_PESSOA_TRANSACAO: [CallbackQueryHandler(transaction_person_selected_callback, pattern="^trans_sel_p_\\d+$")],
            TYPING_TRANSACAO_DETALHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_details_received)],
            CONFIRM_TRANSACAO: [
                CallbackQueryHandler(transaction_confirm_save_callback, pattern="^trans_confirm_save$"),
                CallbackQueryHandler(transaction_edit_again_callback, pattern="^trans_edit_again$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_operation_callback, pattern="^cancel_operation$"),
            CommandHandler("cancel", cancel_operation_callback),
            CommandHandler("start", start_command)
        ]
    )
    application.add_handler(transaction_conv_handler)

    # ConversationHandler para Status
    status_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("status", status_command_start),
            CallbackQueryHandler(status_command_start, pattern="^status_refresh$") # Para botão de "ver outra pessoa"
        ],
        states={
            SELECT_PESSOA_STATUS: [CallbackQueryHandler(status_person_selected_callback, pattern="^status_sel_p_\\d+$")]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_operation_callback, pattern="^cancel_operation$"), # Reutilizar cancelamento
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"), # Botão para menu principal
            CommandHandler("cancel", cancel_operation_callback),
            CommandHandler("start", start_command)
        ]
    )
    application.add_handler(status_conv_handler)

    # Handler para callbacks não tratados (ex: no_pessoas_found)
    async def unhandled_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if query:
            await query.answer("Esta opção não leva a lugar nenhum ou é apenas informativa.")

    application.add_handler(CallbackQueryHandler(unhandled_callback, pattern="^no_pessoas_found$"))


    logger.info("Bot em execução...")
    application.run_polling()

if __name__ == "__main__":
    main()