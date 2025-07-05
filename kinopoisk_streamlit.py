import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import io

# Настройка страницы
st.set_page_config(
    page_title="Кинопоиск Парсер",
    page_icon="🎬",
    layout="wide"
)

# API URLs
API_URL = 'https://kinopoiskapiunofficial.tech/api/v2.2/films/{}'
API_URL_STAFF = 'https://kinopoiskapiunofficial.tech/api/v1/staff?filmId={}'
API_URL_BOXOFFICE = 'https://kinopoiskapiunofficial.tech/api/v2.2/films/{}/box_office'
API_URL_DISTRIBUTIONS = 'https://kinopoiskapiunofficial.tech/api/v2.2/films/{}/distributions'

def get_headers(api_key):
    return {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json',
    }

def format_money(value):
    if not value or value == '-' or value is None:
        return '-'
    parts = str(value).split()
    if not parts or not parts[0].replace(',', '').replace(' ', '').isdigit():
        return value
    try:
        num = int(parts[0].replace(' ', '').replace(',', ''))
        currency = parts[1] if len(parts) > 1 and parts[1] else 'USD'
        formatted = f"{num:,}".replace(",", " ")
        return f"{formatted} {currency}".strip()
    except Exception as e:
        return value

def format_date(date_str):
    if not date_str or date_str == '-':
        return '-'
    try:
        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return dt.strftime('%d.%m.%Y')
    except Exception as e:
        return date_str

def get_film_info(film_id, api_key):
    url = API_URL.format(film_id)
    try:
        response = requests.get(url, headers=get_headers(api_key), timeout=10)
        if response.status_code != 200:
            return None, f'Ошибка: {response.status_code} — {response.text}'
        return response.json(), None
    except Exception as e:
        return None, f'Ошибка запроса: {e}'

def get_film_cast(film_id, api_key):
    url = API_URL_STAFF.format(film_id)
    try:
        response = requests.get(url, headers=get_headers(api_key), timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        cast = []
        for p in data:
            profession = (p.get('professionText') or p.get('profession') or '').lower()
            if any(x in profession for x in ['монтажер', 'художник']):
                continue
            name = p.get('nameRu') or p.get('nameEn') or '-'
            staff_id = p.get('staffId')
            if staff_id:
                cast.append(f"{name};{staff_id}")
            else:
                cast.append(f"{name}")
        return cast
    except Exception as e:
        return []

def get_film_boxoffice(film_id, api_key):
    url = API_URL_BOXOFFICE.format(film_id)
    try:
        response = requests.get(url, headers=get_headers(api_key), timeout=10)
        if response.status_code != 200:
            return {}
        data = response.json()
        currency_symbols = {
            'USD': '$', 'RUB': '₽', 'EUR': '€', 'GBP': '£',
            'CNY': '¥', 'JPY': '¥', 'KZT': '₸', 'UAH': '₴',
            'BYN': 'Br', 'INR': '₹',
        }
        result = {}
        for item in data.get('items', []):
            amount = item.get('amount')
            currency = item.get('currencyCode', 'USD')
            symbol = currency_symbols.get(currency, currency)
            val = f"{amount} {symbol}" if amount else '-'
            if item['type'] == 'BUDGET':
                result['budget'] = val
            elif item['type'] == 'WORLD':
                result['world'] = val
            elif item['type'] == 'RUS':
                result['russia'] = val
            elif item['type'] == 'USA':
                result['usa'] = val
            elif item['type'] == 'MARKETING':
                result['marketing'] = val
        return result
    except Exception as e:
        return {}

def get_film_premieres(film_id, api_key):
    url = API_URL_DISTRIBUTIONS.format(film_id)
    try:
        response = requests.get(url, headers=get_headers(api_key), timeout=10)
        if response.status_code != 200:
            return '-', '-'
        data = response.json()
        premiere_rf = '-'
        premiere_world = '-'
        for item in data.get('items', []):
            t = item.get('type', '').upper()
            date = item.get('date', '-')
            country_obj = item.get('country')
            if t == 'WORLD_PREMIER':
                premiere_world = format_date(date)
            if t == 'COUNTRY_SPECIFIC' and country_obj:
                country_name = country_obj.get('country', '').lower()
                if country_name in ('россия', 'russia'):
                    premiere_rf = format_date(date)
        return premiere_rf, premiere_world
    except Exception as e:
        return '-', '-'

def create_excel_file(film_data, cast_data):
    """Создает Excel файл с данными о фильме"""
    output = io.BytesIO()
    
    # Основные данные фильма
    df_main = pd.DataFrame([film_data])
    
    # Данные о касте
    cast_list = []
    for line in cast_data:
        if ';' in line:
            name, staff_id = line.split(';', 1)
            cast_list.append({'Имя': name.strip(), 'ID': staff_id.strip()})
        else:
            cast_list.append({'Имя': line.strip(), 'ID': ''})
    
    df_cast = pd.DataFrame(cast_list)
    
    # Записываем в Excel
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_main.to_excel(writer, sheet_name='Основная информация', index=False)
        df_cast.to_excel(writer, sheet_name='Актеры и съемочная группа', index=False)
    
    output.seek(0)
    return output

# Инициализация сессии
if 'film_data' not in st.session_state:
    st.session_state.film_data = {}
if 'cast_data' not in st.session_state:
    st.session_state.cast_data = []

# Заголовок
st.title("🎬 Кинопоиск Парсер")
st.markdown("Получение информации о фильмах и сериалах через API Кинопоиска")

# Боковая панель для настроек
with st.sidebar:
    st.header("⚙️ Настройки")
    api_key = st.text_input("API-ключ:", type="password", help="Введите ваш API-ключ от Кинопоиска")
    
    if st.button("ℹ️ Как получить API-ключ?"):
        st.info("""
        1. Зарегистрируйтесь на kinopoiskapiunofficial.tech
        2. Получите бесплатный API-ключ
        3. Вставьте его в поле выше
        """)

# Основной интерфейс
col1, col2 = st.columns([1, 3])

with col1:
    st.header("🔍 Поиск")
    film_id = st.text_input("ID фильма/сериала:", placeholder="Например: 326")
    
    if st.button("🎯 Получить информацию", type="primary"):
        if not api_key:
            st.error("⚠️ Введите API-ключ в боковой панели!")
        elif not film_id.isdigit():
            st.error("⚠️ Введите корректный числовой ID!")
        else:
            with st.spinner("Загрузка данных..."):
                # Получаем основную информацию
                data, error = get_film_info(film_id, api_key)
                
                if error or not data:
                    st.error(f"❌ {error or 'Нет данных'}")
                else:
                    # Собираем всю информацию
                    def safe(val):
                        return '-' if val is None or val == '' else val
                    
                    # Основная информация
                    film_info = {
                        'Название (RU)': safe(data.get('nameRu')),
                        'Оригинальное название': safe(data.get('nameOriginal')),
                        'Год': safe(data.get('year')),
                        'Жанры': safe(', '.join([g['genre'] for g in data.get('genres', [])]) if data.get('genres') else '-'),
                        'Страна': safe(', '.join([c['country'] for c in data.get('countries', []) if c.get('country')])),
                        'Рейтинг Кинопоиска': safe(data.get('ratingKinopoisk')),
                        'Описание': safe(data.get('description'))
                    }
                    
                    # Касса
                    boxoffice = get_film_boxoffice(film_id, api_key)
                    film_info.update({
                        'Бюджет': format_money(boxoffice.get('budget', '-')) if boxoffice else '-',
                        'Касса (мир)': format_money(boxoffice.get('world', '-')) if boxoffice else '-',
                        'Касса (РФ)': format_money(boxoffice.get('russia', '-')) if boxoffice else '-',
                        'Касса (США)': format_money(boxoffice.get('usa', '-')) if boxoffice else '-'
                    })
                    
                    # Премьеры
                    premiere_rf, premiere_world = get_film_premieres(film_id, api_key)
                    film_info.update({
                        'Премьера в РФ': safe(premiere_rf),
                        'Премьера мировая': safe(premiere_world)
                    })
                    
                    # Актеры и съемочная группа
                    cast = get_film_cast(film_id, api_key)
                    
                    st.session_state.film_data = film_info
                    st.session_state.cast_data = cast
                    
                    st.success("✅ Данные успешно загружены!")

with col2:
    st.header("📊 Результаты")
    
    if st.session_state.film_data:
        # Основная информация
        st.subheader("🎭 Основная информация")
        
        # Отображаем информацию в виде метрик и полей
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.metric("Название (RU)", st.session_state.film_data.get('Название (RU)', '-'))
            st.metric("Год", st.session_state.film_data.get('Год', '-'))
            st.metric("Рейтинг Кинопоиска", st.session_state.film_data.get('Рейтинг Кинопоиска', '-'))
            st.metric("Премьера в РФ", st.session_state.film_data.get('Премьера в РФ', '-'))
        
        with col_info2:
            st.metric("Оригинальное название", st.session_state.film_data.get('Оригинальное название', '-'))
            st.metric("Страна", st.session_state.film_data.get('Страна', '-'))
            st.metric("Жанры", st.session_state.film_data.get('Жанры', '-'))
            st.metric("Премьера мировая", st.session_state.film_data.get('Премьера мировая', '-'))
        
        # Описание
        st.subheader("📝 Описание")
        st.write(st.session_state.film_data.get('Описание', '-'))
        
        # Финансы
        st.subheader("💰 Финансы")
        col_money1, col_money2 = st.columns(2)
        
        with col_money1:
            st.metric("Бюджет", st.session_state.film_data.get('Бюджет', '-'))
            st.metric("Касса (мир)", st.session_state.film_data.get('Касса (мир)', '-'))
        
        with col_money2:
            st.metric("Касса (РФ)", st.session_state.film_data.get('Касса (РФ)', '-'))
            st.metric("Касса (США)", st.session_state.film_data.get('Касса (США)', '-'))
        
        # Актеры и съемочная группа
        st.subheader("🎬 Актеры и съемочная группа")
        
        if st.session_state.cast_data:
            # Создаем DataFrame для отображения
            cast_display = []
            for line in st.session_state.cast_data:
                if ';' in line:
                    name, staff_id = line.split(';', 1)
                    cast_display.append({'Имя': name.strip(), 'ID': staff_id.strip()})
                else:
                    cast_display.append({'Имя': line.strip(), 'ID': ''})
            
            if cast_display:
                df_cast = pd.DataFrame(cast_display)
                st.dataframe(df_cast, use_container_width=True)
            else:
                st.write("Нет данных о съемочной группе")
        else:
            st.write("Нет данных о съемочной группе")
        
        # Кнопка экспорта
        st.subheader("📥 Экспорт данных")
        
        if st.button("📊 Скачать Excel файл"):
            try:
                excel_file = create_excel_file(st.session_state.film_data, st.session_state.cast_data)
                
                st.download_button(
                    label="⬇️ Скачать Excel",
                    data=excel_file,
                    file_name=f"film_{film_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            except Exception as e:
                st.error(f"Ошибка при создании файла: {e}")
    else:
        st.info("👈 Введите ID фильма и нажмите 'Получить информацию'")

# Футер
st.markdown("---")
st.markdown("**Создано с помощью Streamlit** • [Кинопоиск API](https://kinopoiskapiunofficial.tech/)")
