"""Streamlit-фронтенд для постановки одной точки на карту.

В этом файле намеренно собрана вся логика приложения:
- поиск адреса через Nominatim / OpenStreetMap;
- выбор одного результата поиска;
- отображение одной точки на Folium-карте.

Маршруты, графы, веса ребер и оптимизацию студенты добавляют самостоятельно.
"""

from __future__ import annotations

import time
from html import escape

import folium
import streamlit as st
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium


APP_TITLE = "Поиск точки интереса по адресу и добавление на карту"
COUNTRY_CODES = "ru"
DEFAULT_CENTER = [55.751244, 37.618423]  # Москва как удобная стартовая точка
DEFAULT_ZOOM = 10
POINT_ZOOM = 16
SEARCH_LIMIT = 5
NOMINATIM_DELAY_SECONDS = 1.1


def init_session_state() -> None:
    """Готовит значения, которые должны переживать перерисовки Streamlit."""
    if "search_results" not in st.session_state:
        st.session_state.search_results = []

    if "selected_point" not in st.session_state:
        st.session_state.selected_point = None

    if "last_query" not in st.session_state:
        st.session_state.last_query = ""


@st.cache_resource
def get_geolocator() -> Nominatim:
    """Создает клиент Nominatim один раз на всю сессию приложения."""
    return Nominatim(user_agent="student_route_planner_streamlit")


@st.cache_data(show_spinner=False, ttl=60 * 60)
def search_address(query: str) -> tuple[list[dict], str | None]:
    """Ищет адрес и возвращает короткий список вариантов.

    Nominatim просит не делать частые запросы. Здесь стоит небольшая задержка,
    а повторные одинаковые поиски дополнительно кешируются Streamlit.
    """
    geolocator = get_geolocator()

    try:
        time.sleep(NOMINATIM_DELAY_SECONDS)
        locations = geolocator.geocode(
            query,
            exactly_one=False,
            limit=SEARCH_LIMIT,
            country_codes=COUNTRY_CODES,
            language="ru",
            addressdetails=True,
            timeout=10,
        )
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as error:
        return [], str(error)

    if not locations:
        return [], None

    results = []
    for location in locations:
        results.append(
            {
                "address": location.address,
                "lat": float(location.latitude),
                "lon": float(location.longitude),
            }
        )

    return results, None


def create_map(point: dict | None) -> folium.Map:
    """Создает карту и добавляет маркер, если точка уже выбрана."""
    if point:
        center = [point["lat"], point["lon"]]
        zoom = POINT_ZOOM
    else:
        center = DEFAULT_CENTER
        zoom = DEFAULT_ZOOM

    map_object = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",
        control_scale=True,
        attribution_control=False,
    )

    if point:
        popup_html = (
            f"<b>Выбранная точка</b><br>"
            f"{escape(point['address'])}<br>"
            f"{point['lat']:.6f}, {point['lon']:.6f}"
        )

        folium.Marker(
            location=[point["lat"], point["lon"]],
            tooltip="Выбранная точка",
            popup=folium.Popup(popup_html, max_width=320),
            icon=folium.Icon(color="red", icon="map-marker"),
        ).add_to(map_object)

    return map_object


def format_result(result: dict) -> str:
    """Делает подпись результата поиска компактной и читаемой."""
    return f"{result['address']} ({result['lat']:.5f}, {result['lon']:.5f})"


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_session_state()

    st.title(APP_TITLE)

    controls_column, map_column = st.columns([0.38, 0.62], gap="large")

    with controls_column:
        st.subheader("Поиск адреса")

        with st.form("address_search_form", clear_on_submit=False):
            query = st.text_input(
                "Адрес",
                placeholder="Например: Невский проспект 1, Санкт-Петербург",
            )
            search_submitted = st.form_submit_button("Найти")

        if search_submitted:
            query = query.strip()
            st.session_state.last_query = query

            if not query:
                st.warning("Введите адрес для поиска.")
                st.session_state.search_results = []
            else:
                with st.spinner("Ищу адрес через OpenStreetMap..."):
                    results, error = search_address(query)

                st.session_state.search_results = results

                if error:
                    st.error(f"Не удалось выполнить поиск: {error}")
                elif not results:
                    st.info("Ничего не найдено. Попробуйте уточнить адрес.")

        if st.session_state.search_results:
            st.divider()
            st.subheader("Результаты")

            selected_index = st.selectbox(
                "Выберите подходящий адрес",
                options=range(len(st.session_state.search_results)),
                format_func=lambda index: format_result(
                    st.session_state.search_results[index]
                ),
            )

            if st.button("Поставить точку на карту", type="primary"):
                result = st.session_state.search_results[selected_index]
                st.session_state.selected_point = {
                    "address": result["address"],
                    "lat": result["lat"],
                    "lon": result["lon"],
                }
                st.success("Точка поставлена на карту.")

        st.divider()
        st.subheader("Текущая точка")

        if st.session_state.selected_point:
            point = st.session_state.selected_point
            st.write(point["address"])
            st.caption(f"Широта: {point['lat']:.6f}, долгота: {point['lon']:.6f}")

            if st.button("Очистить точку"):
                st.session_state.selected_point = None
                st.rerun()
        else:
            st.caption("Точка пока не выбрана.")

    with map_column:
        st.subheader("Карта")
        map_object = create_map(st.session_state.selected_point)
        st_folium(
            map_object,
            height=560,
            use_container_width=True,
            returned_objects=[],
        )


if __name__ == "__main__":
    main()
