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

def format_duration(duration):
    """Форматирует продолжительность в минутах"""
    if not duration or duration == '-' or duration is None:
        return '-'
    try:
        minutes = int(duration)
        if minutes <= 0:
            return '-'
        return str(minutes)
    except (ValueError, TypeError):
        return str(duration) if duration else '-'

def format_vote_count(vote_count):
    """Форматирует количество голосов"""
    if not vote_count or vote_count == '-' or vote_count is None:
        return '-'
    try:
        count = int(vote_count)
        if count <= 0:
            return '-'
        # Форматируем с разделителями тысяч
        return f"{count:,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(vote_count) if vote_count else '-'

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
    
    try:
        # Очищаем данные от проблемных символов
        cleaned_film_data = {}
        for key, value in film_data.items():
            if isinstance(value, str):
                # Удаляем или заменяем проблемные символы
                cleaned_value = value.replace('\x00', '').replace('\ufeff', '')
                # Ограничиваем длину для Excel (максимум 32767 символов в ячейке)
                if len(cleaned_value) > 32000:
                    cleaned_value = cleaned_value[:32000] + "..."
                cleaned_film_data[key] = cleaned_value
            else:
                cleaned_film_data[key] = value
        
        # Основные данные фильма
        df_main = pd.DataFrame([cleaned_film_data])
        
        # Данные о касте
        cast_list = []
        for line in cast_data:
            if ';' in line:
                name, staff_id = line.split(';', 1)
                # Очищаем имя от проблемных символов
                clean_name = name.strip().replace('\x00', '').replace('\ufeff', '')
                if len(clean_name) > 255:  # Ограничение для имен
                    clean_name = clean_name[:255]
                cast_list.append({'Имя': clean_name, 'ID': staff_id.strip()})
            else:
                clean_name = line.strip().replace('\x00', '').replace('\ufeff', '')
                if len(clean_name) > 255:
                    clean_name = clean_name[:255]
                cast_list.append({'Имя': clean_name, 'ID': ''})
        
        df_cast = pd.DataFrame(cast_list)
        
        # Записываем в Excel с правильными настройками
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Записываем основную информацию
            df_main.to_excel(writer, sheet_name='Основная информация', index=False)
            
            # Записываем данные о касте
            df_cast.to_excel(writer, sheet_name='Актеры и съемочная группа', index=False)
            
            # Получаем workbook и worksheet для настройки
            workbook = writer.book
            worksheet_main = writer.sheets['Основная информация']
            worksheet_cast = writer.sheets['Актеры и съемочная группа']
            
            # Настраиваем ширину столбцов
            worksheet_main.set_column('A:A', 25)  # Названия полей
            worksheet_main.set_column('B:B', 50)  # Значения
            
            worksheet_cast.set_column('A:A', 40)  # Имена
            worksheet_cast.set_column('B:B', 15)  # ID
            
            # Добавляем форматирование заголовков
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            # Применяем форматирование к заголовкам
            for col_num, value in enumerate(df_main.columns.values):
                worksheet_main.write(0, col_num, value, header_format)
            
            for col_num, value in enumerate(df_cast.columns.values):
                worksheet_cast.write(0, col_num, value, header_format)
        
        output.seek(0)
        return output
        
    except Exception as e:
        # Если произошла ошибка, возвращаем улучшенную версию CSV
        st.error(f"Ошибка при создании Excel файла: {e}")
        return create_improved_csv_file(film_data, cast_data)

def create_improved_csv_file(film_data, cast_data):
    """Создает улучшенный CSV файл как альтернатива Excel"""
    output = io.BytesIO()
    
    # Создаем временный файл в памяти
    temp_output = io.StringIO()
    
    try:
        # Очищаем данные
        cleaned_film_data = {}
        for key, value in film_data.items():
            if isinstance(value, str):
                cleaned_value = value.replace('\x00', '').replace('\ufeff', '').replace('\n', ' ').replace('\r', ' ')
                cleaned_film_data[key] = cleaned_value
            else:
                cleaned_film_data[key] = value
        
        # Создаем DataFrame для основной информации
        df_main = pd.DataFrame([cleaned_film_data])
        
        # Создаем DataFrame для актеров
        cast_list = []
        for line in cast_data:
            if ';' in line:
                name, staff_id = line.split(';', 1)
                clean_name = name.strip().replace('\x00', '').replace('\ufeff', '').replace('\n', ' ').replace('\r', ' ')
                cast_list.append({'Имя': clean_name, 'ID': staff_id.strip()})
            else:
                clean_name = line.strip().replace('\x00', '').replace('\ufeff', '').replace('\n', ' ').replace('\r', ' ')
                cast_list.append({'Имя': clean_name, 'ID': ''})
        
        df_cast = pd.DataFrame(cast_list)
        
        # Записываем в CSV с правильной кодировкой
        temp_output.write("=== ОСНОВНАЯ ИНФОРМАЦИЯ ===\n")
        df_main.to_csv(temp_output, index=False, encoding='utf-8', sep=';', quoting=1)
        
        temp_output.write("\n=== АКТЕРЫ И СЪЕМОЧНАЯ ГРУППА ===\n")
        df_cast.to_csv(temp_output, index=False, encoding='utf-8', sep=';', quoting=1)
        
        # Получаем содержимое и кодируем с BOM для Excel
        content = temp_output.getvalue()
        temp_output.close()
        
        # Возвращаем байтовый поток с правильной кодировкой
        final_content = '\ufeff' + content
        output.write(final_content.encode('utf-8'))
        output.seek(0)
        
        return output
        
    except Exception as e:
        st.error(f"Ошибка при создании CSV файла: {e}")
        return None

def create_simple_csv_file(film_data, cast_data):
    """Создает простой CSV файл для универсального использования"""
    output = io.StringIO()
    
    # Создаем DataFrame для основной информации
    df_main = pd.DataFrame([film_data])
    
    # Создаем DataFrame для актеров
    cast_list = []
    for line in cast_data:
        if ';' in line:
            name, staff_id = line.split(';', 1)
            cast_list.append({'Имя': name.strip(), 'ID': staff_id.strip()})
        else:
            cast_list.append({'Имя': line.strip(), 'ID': ''})
    
    df_cast = pd.DataFrame(cast_list)
    
    # Записываем основную информацию
    output.write("=== ОСНОВНАЯ ИНФОРМАЦИЯ ===\n")
    df_main.to_csv(output, index=False, encoding='utf-8')
    
    output.write("\n=== АКТЕРЫ И СЪЕМОЧНАЯ ГРУППА ===\n")
    df_cast.to_csv(output, index=False, encoding='utf-8')
    
    content = output.getvalue()
    output.close()
    
    # Возвращаем с UTF-8 BOM для корректного отображения
    return io.BytesIO(('\ufeff' + content).encode('utf-8'))

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
                        'Рейтинг IMDB': safe(data.get('ratingImdb')),
                        'Рейтинг Кинопоиска': safe(data.get('ratingKinopoisk')),
                        'Кол-во голосов КП': format_vote_count(data.get('ratingKinopoiskVoteCount')),
                        'Описание': safe(data.get('description')),
                        'Продолжительность (мин)': format_duration(data.get('filmLength'))
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
            st.metric("Рейтинг IMDB", st.session_state.film_data.get('Рейтинг IMDB', '-'))
            st.metric("Премьера в РФ", st.session_state.film_data.get('Премьера в РФ', '-'))
            st.metric("Премьера мировая", st.session_state.film_data.get('Премьера мировая', '-'))
        
        with col_info2:
            st.metric("Оригинальное название", st.session_state.film_data.get('Оригинальное название', '-'))
            st.metric("Страна", st.session_state.film_data.get('Страна', '-'))
            st.metric("Рейтинг Кинопоиска", st.session_state.film_data.get('Рейтинг Кинопоиска', '-'))
            st.metric("Кол-во голосов КП", st.session_state.film_data.get('Кол-во голосов КП', '-'))
            st.metric("Продолжительность (мин)", st.session_state.film_data.get('Продолжительность (мин)', '-'))
        
        # Жанры отдельно на всю ширину
        st.metric("Жанры", st.session_state.film_data.get('Жанры', '-'))
        
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
        
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            if st.button("📊 Скачать Excel файл"):
                try:
                    with st.spinner("Создание Excel файла..."):
                        excel_file = create_excel_file(st.session_state.film_data, st.session_state.cast_data)
                        
                        if excel_file:
                            filename = f"film_{film_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                            
                            st.download_button(
                                label="⬇️ Скачать Excel",
                                data=excel_file,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="excel_download"
                            )
                            st.success("Excel файл готов к скачиванию!")
                        else:
                            st.error("Не удалось создать Excel файл")
                            
                except Exception as e:
                    st.error(f"Ошибка при создании Excel файла: {e}")
                    st.info("Попробуйте скачать CSV файл")
        
        with col_export2:
            # Создаем два варианта CSV
            csv_col1, csv_col2 = st.columns(2)
            
            with csv_col1:
                if st.button("📄 CSV (для Excel)"):
                    try:
                        with st.spinner("Создание CSV файла..."):
                            csv_file = create_improved_csv_file(st.session_state.film_data, st.session_state.cast_data)
                            
                            if csv_file:
                                filename = f"film_{film_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                
                                st.download_button(
                                    label="⬇️ Скачать CSV",
                                    data=csv_file,
                                    file_name=filename,
                                    mime="text/csv",
                                    key="csv_download_1"
                                )
                                st.success("CSV файл готов к скачиванию!")
                            else:
                                st.error("Не удалось создать CSV файл")
                                
                    except Exception as e:
                        st.error(f"Ошибка при создании CSV файла: {e}")
            
            with csv_col2:
                if st.button("📋 CSV (простой)"):
                    try:
                        with st.spinner("Создание простого CSV файла..."):
                            csv_file = create_simple_csv_file(st.session_state.film_data, st.session_state.cast_data)
                            
                            if csv_file:
                                filename = f"film_{film_id}_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                
                                st.download_button(
                                    label="⬇️ Скачать CSV",
                                    data=csv_file,
                                    file_name=filename,
                                    mime="text/csv",
                                    key="csv_download_2"
                                )
                                st.success("Простой CSV файл готов к скачиванию!")
                            else:
                                st.error("Не удалось создать простой CSV файл")
                                
                    except Exception as e:
                        st.error(f"Ошибка при создании простого CSV файла: {e}")
        
        # Дополнительные советы по экспорту
        with st.expander("💡 Советы по экспорту"):
            st.markdown("""
            **Если возникают проблемы с Excel файлом:**
            1. Попробуйте скачать CSV файл вместо Excel
            2. При открытии CSV в Excel выберите разделитель "точка с запятой" (;)
            3. Убедитесь, что у вас установлены все необходимые библиотеки
            
            **Форматы файлов:**
            - **Excel**: Удобен для просмотра и редактирования
            - **CSV для Excel**: Совместим с Excel, использует точку с запятой
            - **CSV простой**: Универсальный формат для любых программ
            
            **Для установки недостающих библиотек:**
            ```
            pip install xlsxwriter openpyxl
            ```
            """)
        
    else:
        st.info("👈 Введите ID фильма и нажмите 'Получить информацию'")

# Футер
st.markdown("---")
st.markdown("**Создано с помощью Streamlit** • [Кинопоиск API](https://kinopoiskapiunofficial.tech/)")
