# 💸 PayTrack

**PayTrack** é um bot inteligente para **gerenciamento de devedores**, desenvolvido em **Python** com integração à IA **Gemini**. Ideal para acompanhar cobranças, registrar dívidas e facilitar o controle financeiro — tudo direto no **Telegram**.

---

## 🚀 Funcionalidades

* 📌 **Cadastro de devedores**
* 🔎 **Consulta de informações devedoras**
* 💰 **Registro de pagamentos de dívidas**
* 🤖 **Respostas inteligentes com IA Gemini**
* 💾 **Persistência de dados em banco de dados SQLite**
* 💬 **Interação simples e rápida via Telegram Bot**

---

## 📁 Estrutura do Projeto

```
paytrack-bot/
├── bot.py              # Lógica principal do bot e comunicação com o usuário
├── database.py         # Gerenciamento e persistência dos dados
├── gemini_service.py   # Integração com a API Gemini (IA generativa)
├── requirements.txt    # Lista de dependências do projeto
└── README.md           # Documentação do projeto
```

---

## ⚙️ Instalação

1. **Clone o repositório:**

```bash
git clone https://github.com/j0aoarthur/paytrack-bot.git
cd paytrack-bot
```

2. **Crie e ative um ambiente virtual:**

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate     # Windows
```

3. **Instale as dependências:**

```bash
pip install -r requirements.txt
```

---

## 🔐 Variáveis de Ambiente

Antes de rodar o bot, configure as seguintes variáveis de ambiente:

| Variável             | Descrição                     |
| -------------------- | ----------------------------- |
| `TELEGRAM_BOT_TOKEN` | Token do bot do Telegram      |
| `GEMINI_API_KEY`     | Chave da API do Google Gemini |

### Exemplo (Linux/macOS):

```bash
export TELEGRAM_BOT_TOKEN='seu_token_aqui'
export GEMINI_API_KEY='sua_api_key_aqui'
```

> 💡 No Windows, utilize `set` em vez de `export`.

---

## ▶️ Como Usar

Após configurar as variáveis, execute o bot com:

```bash
python bot.py
```

Abra o Telegram, procure pelo seu bot e comece a gerenciar seus devedores com facilidade!

---

## 🧠 Integração com IA Gemini

O bot utiliza **Gemini**, IA generativa do Google, para interpretar mensagens e fornecer interações mais naturais e eficientes, como:

* Sugestões de cobrança
* Respostas personalizadas
* Análise de contexto de dívida

---

## 📌 Contribua com o Projeto

Achou um bug? Tem uma ideia para melhorar o bot? Colabore abrindo uma issue ou um pull request. Toda contribuição é bem-vinda!
