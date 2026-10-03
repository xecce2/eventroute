# EventRoute: описание данных и экранов для фронтенда

Этот файл можно целиком вставить в чат с Claude и попросить сделать дизайн и компоненты. Источник правды по контрактам остаётся `CLAUDE.md`, раздел 4. Если что-то расходится, прав `CLAUDE.md`.

## Что за продукт

Участник хакатона HackYeah 2026 (Tauron Arena, Краков, 4 октября, старт 10:00, быть у входа к 09:30) выбирает станцию, откуда едет, и получает до трёх планов дороги: поезд или автобус до Кракова, затем трамвай и пешком до входа. Для каждого плана показана вероятность успеть. Кнопка «поезд опоздал на 25 минут» пересчитывает план. Отдельный экран показывает организатору и городу волну прибытий.

Язык интерфейса и всех текстов API: **английский**. Время приходит в ISO 8601 с поясом (`2026-10-04T08:48:00+02:00`), показывать в зоне Europe/Warsaw. Деньги в злотых (`price_pln`).

## Как подключаться

- Бэкенд: `http://localhost:8000`, документация со схемами: `http://localhost:8000/docs`.
- Пока бэкенд недоступен или эндпоинт ещё не готов, работай на моках в формате ниже.

## Экраны

1. **Форма регистрации.** Выбор станции отправления из списка (сейчас четыре: `Wrocław Główny`, `Warszawa Centralna`, `Poznań Główny`, `Katowice`), необязательные «arrive by» и бюджет. Для демо по умолчанию Вроцлав.
2. **Планы.** От 1 до 3 карточек. Одна карточка может нести несколько меток сразу (`safest`, `fastest`, `cheapest`). На карточке: метки, вероятность успеть (главный элемент, например шкала), запас времени в минутах, цена или «price on site» если `null`, значок поезда или автобуса, бейдж «overnight stay», кнопка «Buy on Koleo» (`buy_url`), короткое объяснение (`explanation`), бейдж источника данных (см. ниже).
3. **Таймлайн и карта.** Вертикальный таймлайн дороги: отправление поезда, прибытие, пешком, трамвай, пешком, вход, плюс «быть у входа к 09:30». Карта (Leaflet/OSM) с маршрутом после высадки: маркеры вокзала и арены, линия по точкам `local_legs[].path`, у каждого участка свой стиль (пешком пунктир, трамвай сплошная с номером линии).
4. **Перепланирование.** Кнопка «Train delayed 25 min». Показывает «было / стало»: вероятность, запас, время прибытия, и текст `message`. Если альтернатив нет (массив `plans` пустой или без лучшего варианта), сказать об этом явно.
5. **Экран города.** Столбчатый график волны прибытий по слотам 15 минут, список узлов с уровнем нагрузки (`low | medium | high`), откуда едут (`origins`), рекомендации с важностью. Эндпоинта пока нет, делать на моках.

## Данные

### События
`GET /api/events/ev_hackyeah2026`:
```json
{"id": "ev_hackyeah2026", "name": "HackYeah 2026", "venue": "Tauron Arena Kraków",
 "venue_station": "Kraków Główny", "city": "Kraków", "start": "2026-10-04T10:00:00+02:00",
 "checkin_buffer_min": 30, "lat": 50.0675, "lon": 19.9917}
```

### Запрос планов
`POST /api/plan`, тело `{"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "arrive_by": null, "budget_pln": null, "mode_pref": null}`. Ответ `{request_id, plans: Plan[], status: "ok" | "no_options"}`. При `no_options` показать понятное «no suitable options».

Реальный пример (Вроцлав), точки `path` сокращены:
```json
{
  "id": "pl_066e7559",
  "labels": ["safest", "fastest"],
  "train": {
    "id": "tr_wro_1004_0510", "source": "fixture", "mode": "train", "category": "IC", "train": "IC",
    "from": "Wrocław Główny", "to": "Kraków Główny",
    "dep": "2026-10-04T05:10:00+02:00", "arr": "2026-10-04T08:15:00+02:00",
    "price_pln": 64.0, "changes": 0, "known_delay_min": 0,
    "delay_model": {"p_on_time": 0.7, "mean_delay_min": 6, "p95_delay_min": 25},
    "url": "https://koleo.pl/rozklad-pkp/wroclaw-glowny/krakow-glowny/04-10-2026_05:10/all/all"
  },
  "local_legs": [
    {"mode": "walk", "from": "Kraków Główny", "to": "Dworzec Główny Tunel",
     "dep": "2026-10-04T08:20:00+02:00", "arr": "2026-10-04T08:23:00+02:00",
     "duration_min": 3, "std_min": 1, "line": null, "path": [[50.0677, 19.9479], "..."]},
    {"mode": "tram", "from": "Dworzec Główny Tunel", "to": "TAURON Arena Kraków Wieczysta",
     "dep": "2026-10-04T08:23:00+02:00", "arr": "2026-10-04T08:36:00+02:00",
     "duration_min": 13, "std_min": 3, "line": "15", "path": [[50.068199, 19.947649], "..."]},
    {"mode": "walk", "from": "TAURON Arena Kraków Wieczysta", "to": "Tauron Arena Kraków",
     "dep": "2026-10-04T08:36:00+02:00", "arr": "2026-10-04T08:48:00+02:00",
     "duration_min": 12, "std_min": 2, "line": null, "path": [[50.071785, 19.983839], "..."]}
  ],
  "venue_target": "2026-10-04T09:30:00+02:00",
  "arrival_at_venue": "2026-10-04T08:48:00+02:00",
  "buffer_min": 42,
  "p_on_time": 0.983,
  "price_pln": 64.0,
  "overnight_stay": false,
  "explanation": "Most reliable, fastest. 42 min to spare, 98% chance of arriving on time.",
  "buy_url": "https://koleo.pl/rozklad-pkp/wroclaw-glowny/krakow-glowny/04-10-2026_05:10/all/all"
}
```

Правила чтения полей:
- `train.mode`: `train` или `bus` (FlixBus). У автобуса свой значок. `train.category`: `IC`, `TLK`, `EIP`, `EIC`, `LEO`, `FLIX`, `PR`, `KŚ`, `KM`; у маршрутов с пересадкой через плюс, например `IC+EIP`.
- `price_pln` может быть `null`: показать «price on site». Такой план не бывает `cheapest`.
- `buffer_min` может быть отрицательным: опаздываешь, показать красным «X min late».
- `p_on_time` от 0 до 1. Пороги для цвета придумать в дизайне, ориентир: от 0.9 надёжно, от 0.7 нормально, ниже рискованно.
- `overnight_stay: true`: поезд приезжает накануне или ночью, нужна ночёвка. Показывать предупреждением, такой план не может быть `fastest` или `cheapest`.
- Если участок `local_legs[].path` равен `null`, карта рисует прямую между точками вокзала (50.0677, 19.9479) и арены (`Event.lat/lon`).
- Порядок координат в `path`: `[lat, lon]`, как в Leaflet.
- `known_delay_min` больше 0 означает, что поезд уже опаздывает; плановое `arr` при этом не меняется.

### Статусы поиска
`GET /api/plan/{request_id}/stream` (SSE). События `event: status` с `data: {"step": "search|found|local|reliability|done", "message": "Searching for trains…"}` и в конце `event: done`. Показывать как короткую ленту состояний под формой, пока считается.

### Задержка
`POST /api/simulate/disruption`, тело `{"plan_id": "pl_066e7559", "train_delay_min": 25}`. Ответ:
```json
{"affected_plan": { "...Plan, train.known_delay_min = 25, p_on_time 0.899, buffer_min 17, arrival_at_venue 09:13" },
 "plans": [ "...пересчитанные планы" ],
 "notified": false,
 "message": "IC 05:10 is delayed by 25 min. You will arrive around 09:13, 90% chance of arriving on time."}
```
`affected_plan` нужен для «было / стало» (сравнить с исходным планом). `notified: false` значит, что Telegram не отправлен, тогда показать `message` самим в интерфейсе как уведомление.

### Экран города (пока моки)
```json
{"event_id": "ev_hackyeah2026", "participants_total": 420,
 "arrivals_by_slot": [{"slot": "2026-10-04T08:45:00+02:00", "count": 112}],
 "nodes": [{"name": "Kraków Główny", "lat": 50.0677, "lon": 19.9479, "peak_count": 140,
            "peak_slot": "2026-10-04T09:15:00+02:00", "load": "low|medium|high"}],
 "origins": [{"station": "Warszawa Centralna", "count": 150}],
 "recommendations": [{"type": "stagger_checkin|add_trams",
                      "text": "Add trams on line 15 from 9:10 to 9:40", "severity": "low|medium|high"}]}
```
Слоты по 15 минут. Это синтетические участники, не реальные люди (так и написать на экране мелким текстом).

## Источник данных: «live» или «recorded» (запланировано)

Мы не хотим, чтобы демо выглядело как работа живого агента, когда на самом деле подставлены записанные данные. Поэтому источник данных должен быть всегда виден.

- Уже есть: `plan.train.source`. Значения `koleo` и `playwright` означают живой поиск, `fixture` означает записанные данные Koleo от 3 октября. Сегодня везде `fixture`.
- **Бейдж на карточке плана:** `fixture` показывать как «Recorded data» (спокойный серый), `koleo` и `playwright` как «Live» (акцентный цвет). Бейдж не должен быть мелким и спрятанным: это часть честной подачи.
- **Запланировано, пока не реализовано (делать на моках):**
  - в ответе `POST /api/plan` поля `data_source: "live" | "recorded" | "mixed"` и `fallback_reason: string | null` (например «live search failed: rate limit», при `null` откатов не было). При `fallback_reason` над планами показать однострочную плашку «Live search failed, showing recorded data».
  - в SSE новый шаг `step: "fallback"` с причиной в `message`.
  - `GET /api/providers/status` возвращает `{requests_total, live_ok, fallback, last_fallback_reason}`. Для служебного экрана или маленького индикатора в углу.

## Что нужно от дизайна

Чистый современный интерфейс для демо на сцене: читается с расстояния, не перегружен, вероятность и время «когда выходить» самые заметные элементы. Светлая и тёмная темы не обязательны. Мобильная раскладка нужна (участник пользуется телефоном), экран города в первую очередь для ноутбука или проектора.
