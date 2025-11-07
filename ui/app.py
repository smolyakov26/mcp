import streamlit as st
import requests
import pandas as pd

# API всегда внутри Docker
API_URL = "http://mcp-server:3001/ask"

st.set_page_config(
    page_title="SQL Chat Assistant", 
    layout="wide",
    page_icon="💬"
)

st.title("💬 SQL Chat Assistant")

# Инициализация сессии
if "messages" not in st.session_state:
    st.session_state.messages = []

# Боковая панель
with st.sidebar:
    st.header("ℹ️ О приложении")
    st.write("""
    **SQL Chat Assistant** позволяет:
    - Задавать вопросы на естественном языке
    - Автоматически генерировать SQL запросы
    - Просматривать результаты в табличном формате
    - Скачивать данные для анализа
    """)
    
    st.divider()
    
    st.header("💡 Примеры запросов")
    examples = [
        "Покажи топ-5 клиентов по объему продаж",
        "Сколько заказов было за последний месяц?",
        "Выведи список самых популярных товаров",
        "Покажи статистику продаж по регионам"
    ]
    
    for example in examples:
        if st.button(example, use_container_width=True, key=f"example_{example}"):
            if "question_input" not in st.session_state:
                st.session_state.question_input = example
            st.rerun()

# Основной интерфейс - две колонки
col1, col2 = st.columns([1, 1])

# Левая колонка - форма ввода и последний вопрос
with col1:
    st.subheader("🆕 Новый запрос")
    
    # Форма ввода
    with st.form(key="question_form", clear_on_submit=True):
        default_question = st.session_state.get("question_input", "")
        question = st.text_area(
            "Введите ваш вопрос:",
            value=default_question,
            placeholder="Например: 'Покажи топ-5 самых активных клиентов'",
            height=100,
            key="question_input"
        )
        
        col_submit, col_clear = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("🚀 Отправить", use_container_width=True)
        with col_clear:
            clear_clicked = st.form_submit_button("🗑️ Очистить историю", use_container_width=True)
    
    if clear_clicked:
        st.session_state.messages = []
        if "question_input" in st.session_state:
            del st.session_state.question_input
        st.rerun()
    
    # Показываем последний вопрос и ответ сверху
    st.subheader("📝 Последний запрос")
    
    if st.session_state.messages:
        # Берем последние сообщения (пользователь и ассистент)
        recent_messages = []
        for msg in reversed(st.session_state.messages):
            if msg["role"] in ["user", "assistant"]:
                recent_messages.append(msg)
                if len(recent_messages) >= 2:  # Берем последнюю пару вопрос-ответ
                    break
        
        # Отображаем в обратном порядке (последний сверху)
        for msg in reversed(recent_messages):
            if msg["role"] == "user":
                st.info(f"**👤 Вы:** {msg['content']}")
            elif msg["role"] == "assistant":
                # Парсим SQL из сообщения
                content = msg['content']
                if "```sql" in content:
                    sql_part = content.split("```sql")[1].split("```")[0].strip()
                    st.success("**🤖 Ассистент:** Запрос сгенерирован успешно")
                    with st.expander("📋 Показать SQL"):
                        st.code(sql_part, language="sql")
                else:
                    st.success(f"**🤖 Ассистент:** {msg['content']}")
    else:
        st.info("💡 Задайте вопрос чтобы увидеть историю здесь")

# Правая колонка - результаты
with col2:
    st.subheader("📊 Результаты")
    
    # Находим все табличные результаты
    table_messages = [m for m in st.session_state.messages if m["role"] == "table"]
    
    if table_messages:
        # Показываем последнюю таблицу
        latest_table = table_messages[-1]
        df = latest_table["content"]
        
        st.success(f"✅ Найдено записей: {len(df)}")
        
        # Показываем таблицу
        st.dataframe(df, use_container_width=True, height=400)
        
        # Кнопки для работы с данными
        col_download, col_stats = st.columns(2)
        
        with col_download:
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Скачать CSV",
                data=csv,
                file_name="query_results.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_stats:
            if st.button("📈 Статистика", use_container_width=True):
                st.write("**Базовая статистика по числовым столбцам:**")
                numeric_df = df.select_dtypes(include=['number'])
                if not numeric_df.empty:
                    st.write(numeric_df.describe())
                else:
                    st.write("Нет числовых данных для анализа")
    else:
        st.info("🔍 Результаты запросов будут отображаться здесь")

# Обработка отправки формы
if submitted and question:
    # Очищаем пример если использовали
    if "question_input" in st.session_state:
        del st.session_state.question_input
    
    # Добавляем вопрос пользователя
    st.session_state.messages.append({"role": "user", "content": question})
    
    try:
        with st.spinner("🤖 Анализирую запрос и генерирую SQL..."):
            response = requests.post(API_URL, json={"question": question}, timeout=120)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            st.error(f"❌ Ошибка: {data['error']}")
            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"Произошла ошибка при обработке запроса: {data['error']}"
            })
        else:
            # Формируем сообщение ассистента
            assistant_msg = f"SQL запрос:\n```sql\n{data['sql']}\n```\n\nНайдено строк: {data['row_count']}"
            st.session_state.messages.append({"role": "assistant", "content": assistant_msg})

            # Если есть данные — добавляем таблицу
            if data["row_count"] > 0:
                df = pd.DataFrame(data["data"])
                st.session_state.messages.append({"role": "table", "content": df})
                
                # Показываем уведомление об успехе
                st.toast(f"✅ Запрос выполнен! Найдено {data['row_count']} строк", icon="✅")
            else:
                st.warning("⚠️ Запрос выполнен, но данные не найдены")
                
            st.rerun()

    except requests.exceptions.ConnectionError:
        st.error("🔌 Не удалось подключиться к серверу API")
    except requests.exceptions.Timeout:
        st.error("⏰ Превышено время ожидания ответа")
    except Exception as e:
        st.error(f"❌ Произошла ошибка: {str(e)}")

# Показываем полную историю в expander
if len(st.session_state.messages) > 2:
    with st.expander("📜 Вся история диалога"):
        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] == "user":
                st.write(f"**👤 Вопрос {i//2 + 1}:** {msg['content']}")
            elif msg["role"] == "assistant":
                content = msg['content']
                if "```sql" in content:
                    sql_part = content.split("```sql")[1].split("```")[0].strip()
                    with st.expander(f"📝 SQL запрос {i//2 + 1}"):
                        st.code(sql_part, language="sql")
                else:
                    st.write(f"**🤖 Ответ {i//2 + 1}:** {msg['content']}")
            st.divider()