# 💸 PayTrack: Seu Assistente Inteligente para Gerenciar Devedores no Telegram 🤖

**PayTrack** é um bot para Telegram, desenvolvido em **Python** e integrado com a IA **Gemini** do Google. Ele foi criado para simplificar o acompanhamento de cobranças, registrar dívidas e pagamentos, e facilitar seu controle financeiro sobre valores a receber — tudo de forma conversacional e diretamente no Telegram.

---

## ✨ Funcionalidades Principais

*   📌 **Gerenciamento Completo de Devedores**:
    *   Adicione novas pessoas à sua lista de devedores.
    *   Edite informações de contatos existentes.
    *   Remova devedores e todos os seus registros associados de forma segura.
    *   Liste todas as pessoas cadastradas.
*   💸 **Registro Inteligente de Empréstimos**:
    *   Informe um novo empréstimo em linguagem natural (ex: "Emprestei 150 para o João ontem para o lanche").
    *   A IA Gemini extrai o valor, data e descrição automaticamente.
    *   Confirme os dados antes de salvar.
*   💰 **Registro Facilitado de Pagamentos**:
    *   Registre pagamentos recebidos da mesma forma intuitiva (ex: "Maria pagou 50 reais hoje referente à dívida do livro").
    *   A IA processa os detalhes para você.
    *   Verifique e confirme antes do registro final.
*   📊 **Consulta de Status Financeiro por Devedor**:
    *   Veja um resumo detalhado das transações (empréstimos e pagamentos) de uma pessoa específica.
    *   Saiba o saldo devedor atualizado.
*   🤖 **Respostas Inteligentes com IA Gemini**:
    *   Interpretação de linguagem natural para registro de transações.
    *   Extração automática de valor, data e descrição.
*   💾 **Persistência de Dados Segura**:
    *   Todas as informações são salvas em um banco de dados SQLite (`debt_manager.db`).
*   💬 **Interface Amigável no Telegram**:
    *   Interação através de comandos e botões inline para uma navegação fácil e rápida.
    *   Mensagens formatadas e uso de emojis para melhor experiência.
*   ❌ **Cancelamento de Operações**:
    *   Cancele a qualquer momento a operação atual com o comando `/cancel` ou botões de cancelamento.

---

## 🤖 Comandos Disponíveis

*   `/start`: Mostra a mensagem de boas-vindas e o menu principal de ações.
*   `/pessoas`: Abre o menu para gerenciar devedores (adicionar, editar, remover, listar).
*   `/emprestimos`: Inicia o fluxo para registrar um novo empréstimo concedido.
*   `/pagamentos`: Inicia o fluxo para registrar um pagamento recebido.
*   `/status`: Permite selecionar um devedor para visualizar seu status financeiro detalhado.
*   `/cancel`: Cancela a operação atual que está sendo realizada com o bot.

Além dos comandos, o bot guia o usuário através de menus com botões inline para a maioria das operações.

---

## 📁 Estrutura do Projeto

```
paytrack-bot/
├── .env                # Arquivo para variáveis de ambiente (NÃO versionar)
├── bot.py              # Lógica principal do bot, handlers de comando e conversa
├── database.py         # Definição do schema do banco de dados (SQLAlchemy) e funções CRUD
├── gemini_service.py   # Integração com a API Gemini para processamento de linguagem natural
├── requirements.txt    # Lista de dependências Python
├── debt_manager.db     # Arquivo do banco de dados SQLite (criado na primeira execução)
└── README.md           # Esta documentação
```

---

## ⚙️ Instalação

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/j0aoarthur/paytrack-bot.git
    cd paytrack-bot
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate   # Linux/macOS
    # venv\Scripts\activate     # Windows
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

---

## 🔐 Variáveis de Ambiente

Antes de rodar o bot, crie um arquivo chamado `.env` na raiz do projeto (no mesmo nível que `bot.py`) e adicione as seguintes variáveis:

```env
// filepath: .env
TELEGRAM_BOT_TOKEN="SEU_TOKEN_AQUI_DO_BOTFATHER"
GEMINI_API_KEY="SUA_API_KEY_AQUI_DO_GOOGLE_AI_STUDIO"
DATABASE_URL="sqlite:///./debt_manager.db" # Opcional, padrão já definido
```

| Variável             | Descrição                                                                 |
| -------------------- | ------------------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | Token do seu bot do Telegram (obtido via [BotFather](https://t.me/botfather)). |
| `GEMINI_API_KEY`     | Sua chave de API para o Google Gemini (obtenha no [Google AI Studio](https://aistudio.google.com/app/apikey)). |
| `DATABASE_URL`       | String de conexão do banco de dados. O padrão é usar `debt_manager.db`.   |


### Exemplo de configuração (Linux/macOS):

Se não for usar o arquivo `.env`, você pode exportar as variáveis no seu terminal:
```bash
export TELEGRAM_BOT_TOKEN='seu_token_aqui'
export GEMINI_API_KEY='sua_api_key_aqui'
```
> 💡 No Windows, utilize `set` em vez de `export` se não estiver usando um arquivo `.env`.

---

## ▶️ Como Executar o Bot

Após configurar o ambiente e as variáveis, execute o bot com o seguinte comando:

```bash
python bot.py
```
O bot irá inicializar o banco de dados (se ainda não existir) e começará a escutar por mensagens e comandos no Telegram. Abra a conversa com seu bot no Telegram e use `/start` para começar!

---

## 🧠 Integração com IA Gemini

O PayTrack utiliza a IA **Gemini** do Google para:

*   **Processar Linguagem Natural**: Ao registrar empréstimos ou pagamentos, você pode descrever a transação em linguagem natural.
*   **Extrair Dados**: A IA identifica e extrai automaticamente o **valor**, a **data** (interpretando termos como "hoje", "ontem" ou datas específicas) e a **descrição** da transação a partir do seu texto.
*   **Facilitar a Interação**: Torna o processo de entrada de dados mais rápido e intuitivo, sem a necessidade de preencher formulários complexos.

Isso permite uma experiência de usuário mais fluida e eficiente.

---

## 📌 Contribua com o Projeto

Achou um bug? Tem uma ideia para melhorar o bot? Sua colaboração é muito bem-vinda!
Sinta-se à vontade para abrir uma *issue* ou um *pull request* no repositório do projeto.