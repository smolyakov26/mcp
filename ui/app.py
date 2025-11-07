import streamlit as st
import requests
import pandas as pd
import json

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
    st.session_state.messages = [
        {"role": "assistant", "content": "Привет! Я ваш SQL ассистент. Задайте вопрос о данных на естественном языке, и я сгенерирую SQL запрос и покажу результаты."}
    ]

# Боковая панель
with st.sidebar:
    st.header("ℹ️ О приложении")
    st.caption("AI-ассистент для работы с базами данных через естественный язык")
    
    st.divider()
    
    st.header("💡 Примеры запросов")
    examples = [
        "Покажи топ-5 клиентов",
        "Сколько всего заказов?",
        "Выведи список товаров",
        "Покажи последние 10 транзакций"
    ]
    
    for example in examples:
        if st.button(example, use_container_width=True, key=f"example_{hash(example)}"):
            # Добавляем пример в историю чата
            st.session_state.messages.append({"role": "user", "content": example})
            # Обрабатываем запрос сразу
            st.session_state.pending_question = example
            st.rerun()
    
    st.divider()
    
    if st.button("🗑️ Очистить историю", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "История очищена. Чем могу помочь?"}
        ]
        st.rerun()
    
    # Информация о подключении
    st.caption("🌐 API: mcp-server:3001")

# Функция для обработки запросов к API
def process_question(question):
    """Обрабатывает вопрос через API и возвращает результат"""
    try:
        # Подготавливаем данные для запроса
        payload = {
            "question": question,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(
            API_URL, 
            json=payload, 
            headers=headers,
            timeout=30
        )
        
        # Проверяем статус ответа
        if response.status_code == 200:
            return response.json(), None
        else:
            error_msg = f"Ошибка API ({response.status_code}): {response.text}"
            return None, error_msg
            
    except requests.exceptions.ConnectionError:
        return None, "❌ Не удалось подключиться к серверу API. Проверьте, запущен ли сервер."
    except requests.exceptions.Timeout:
        return None, "⏰ Превышено время ожидания ответа от сервера."
    except requests.exceptions.RequestException as e:
        return None, f"🌐 Ошибка сети: {str(e)}"
    except json.JSONDecodeError:
        return None, "❌ Неверный формат ответа от сервера."
    except Exception as e:
        return None, f"❌ Непредвиденная ошибка: {str(e)}"

# Основной интерфейс
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("💭 Чат")
    
    # Отображение истории чата
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            content = message["content"]
            
            # Форматируем SQL код
            if "```sql" in content:
                parts = content.split("```sql")
                if parts[0].strip():
                    st.write(parts[0].strip())
                
                if len(parts) > 1:
                    sql_code = parts[1].split("```")[0].strip()
                    with st.expander("📋 Показать SQL запрос", expanded=False):
                        st.code(sql_code, language="sql")
                    
                    # Остальная часть сообщения после SQL
                    remaining = parts[1].split("```")[1] if len(parts[1].split("```")) > 1 else ""
                    if remaining.strip():
                        st.write(remaining.strip())
            else:
                st.write(content)

with col2:
    st.subheader("📊 Результаты")
    
    # Показываем табличные результаты
    table_messages = [m for m in st.session_state.messages if m.get("type") == "table"]
    
    if table_messages:
        latest_table = table_messages[-1]
        df = latest_table["content"]
        
        st.success(f"✅ Найдено записей: {len(df)}")
        st.dataframe(df, use_container_width=True, height=400)
        
        # Кнопки для работы с данными
        col_download, col_stats = st.columns(2)
        with col_download:
            csv = df.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Скачать CSV",
                data=csv,
                file_name="query_results.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_stats:
            if st.button("📈 Статистика", use_container_width=True):
                numeric_df = df.select_dtypes(include=['number'])
                if not numeric_df.empty:
                    st.write("**Статистика:**")
                    st.dataframe(numeric_df.describe(), use_container_width=True)
                else:
                    st.info("Нет числовых данных для статистики")
    else:
        st.info("Результаты SQL запросов появятся здесь")

# Обработка ввода через chat_input
if prompt := st.chat_input("Задайте вопрос о данных..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.pending_question = prompt
    st.rerun()

# Обработка pending вопросов (из chat_input или примеров)
if hasattr(st.session_state, 'pending_question'):
    question = st.session_state.pending_question
    del st.session_state.pending_question
    
    # Показываем спиннер
    with st.spinner("🤖 Анализирую запрос и генерирую SQL..."):
        data, error = process_question(question)
        
        if error:
            st.session_state.messages.append({"role": "assistant", "content": error})
            st.error(error)
        else:
            if "error" in data:
                error_msg = f"❌ Ошибка в ответе API: {data['error']}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                st.error(error_msg)
            else:
                # Формируем сообщение ассистента
                sql_code = data.get('sql', 'Не удалось сгенерировать SQL')
                row_count = data.get('row_count', 0)
                
                assistant_msg = f"Запрос обработан успешно! 🎉\n\n```sql\n{sql_code}\n```\n\nНайдено строк: {row_count}"
                st.session_state.messages.append({"role": "assistant", "content": assistant_msg})

                # Добавляем таблицу с данными
                if row_count > 0 and 'data' in data:
                    df = pd.DataFrame(data['data'])
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"Данные загружены ({row_count} строк)",
                        "type": "table",
                        "content": df
                    })
                    st.success(f"✅ Успешно! Получено {row_count} строк")
                
                st.rerun()

# Отладочная информация (можно убрать в продакшене)
with st.sidebar:
    st.divider()
    if st.checkbox("🔧 Показать отладочную информацию"):
        st.write("**Последние сообщения:**")
        for i, msg in enumerate(st.session_state.messages[-3:]):
            role_icon = "👤" if msg["role"] == "user" else "🤖"
            st.write(f"{role_icon} {msg['content'][:50]}...")
        
        st.write("**Статус API:**")
        try:
            # Простой ping для проверки доступности
            response = requests.get(API_URL.replace('/ask', ''), timeout=5)
            if response.status_code == 200:
                st.success("✅ API доступен")
            else:
                st.warning(f"⚠️ API отвечает с кодом {response.status_code}")
        except:
            st.error("❌ API недоступен")