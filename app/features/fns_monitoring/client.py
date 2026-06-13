"""Проверка блокировок расчётных счетов через сервис ФНС."""

from __future__ import annotations

import asyncio
import base64
import json
import logging

import aiohttp
from core.config import config
from yarl import URL

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "Referer": "https://service.nalog.ru/bi.do",
    "X-Requested-With": "XMLHttpRequest",
}


def _fns_proxy() -> str | None:
    """Возвращает прокси для запросов к ФНС или ``None`` (прямое соединение)."""
    return config.fns_proxy or None


async def _get_captcha_token(
    session: aiohttp.ClientSession, proxy: str | None
) -> str:
    """Получает токен капчи от сервиса ФНС.

    Args:
        session: Активная aiohttp-сессия.
        proxy: Прокси для запроса (или ``None``).

    Returns:
        Строка токена капчи.

    """
    async with session.get(
        "https://service.nalog.ru/static/captcha.bin", proxy=proxy
    ) as resp:
        resp.raise_for_status()
        token = (await resp.text()).strip()
    logger.debug("captchaToken: %s", token)
    return token


async def _download_captcha_image(
    session: aiohttp.ClientSession, token: str, proxy: str | None
) -> bytes:
    """Скачивает изображение капчи.

    Args:
        session: Активная aiohttp-сессия.
        token: Токен капчи.
        proxy: Прокси для запроса (или ``None``).

    Returns:
        Байты изображения капчи.

    """
    async with session.get(
        "https://service.nalog.ru/static/captcha.bin",
        params={"a": token, "version": "2"},
        proxy=proxy,
    ) as resp:
        resp.raise_for_status()
        image = await resp.read()
    logger.debug("Капча скачана (%d байт)", len(image))
    return image


def _api_key() -> str:
    """Возвращает ключ 2captcha или бросает исключение если не задан."""
    key = config.captcha_api_key
    if not key:
        raise RuntimeError("CAPTCHA_API_KEY не задан в .env")
    return key


async def _report_bad_captcha(captcha_id: str) -> None:
    """Сообщает 2captcha о неверно решённой капче.

    Args:
        captcha_id: Идентификатор задания в 2captcha.

    """
    async with aiohttp.ClientSession() as s:
        async with s.get(
            "http://2captcha.com/res.php",
            params={
                "key": _api_key(),
                "action": "reportbad",
                "id": captcha_id,
                "json": "1",
            },
        ):
            pass
    logger.warning("Сообщили 2captcha об ошибке (ID: %s)", captcha_id)



async def _poll_2captcha(captcha_id: str) -> str:
    """Ждёт решения от 2captcha и возвращает ответ.

    Args:
        captcha_id: ID задания в 2captcha.

    Returns:
        Текст решённой капчи.

    Raises:
        RuntimeError: При ошибке API 2captcha.
        TimeoutError: Если капча не решена за отведённое время.

    """
    async with aiohttp.ClientSession() as s:
        for attempt in range(24):
            await asyncio.sleep(5)
            async with s.get(
                "http://2captcha.com/res.php",
                params={
                    "key": _api_key(),
                    "action": "get",
                    "id": captcha_id,
                    "json": "1",
                },
            ) as resp:
                result = await resp.json(content_type=None)

            if result.get("status") == 1:
                answer: str = result["request"]
                logger.info("Капча решена 2captcha: '%s' (ID: %s)", answer, captcha_id)
                return answer
            elif result.get("request") == "CAPCHA_NOT_READY":
                logger.info("2captcha ещё думает... (%d/24)", attempt + 1)
            else:
                raise RuntimeError(f"2captcha ошибка: {result}")

    raise TimeoutError("Капча не решена за отведённое время")


async def _keepalive_fns(
    fns_session: aiohttp.ClientSession,
    stop: asyncio.Event,
    proxy: str | None,
) -> None:
    """Поддерживает FNS-сессию живой, пока решается капча.

    Использует нейтральный запрос к bi.do — не трогает состояние капчи.

    Args:
        fns_session: Активная FNS-сессия (с JSESSIONID).
        stop: Событие остановки.
        proxy: Прокси для запроса (или ``None``).

    """
    while not stop.is_set():
        await asyncio.sleep(10)
        if stop.is_set():
            break
        try:
            async with fns_session.get(
                "https://service.nalog.ru/bi.do", proxy=proxy
            ) as resp:
                logger.debug("FNS keepalive: HTTP %d", resp.status)
        except Exception as e:
            logger.debug("FNS keepalive ошибка: %s", e)


async def _solve_captcha(
    image_bytes: bytes,
    fns_session: aiohttp.ClientSession,
    proxy: str | None,
) -> tuple[str, str]:
    """Отправляет капчу в 2captcha и ждёт решения, поддерживая FNS-сессию живой.

    Args:
        image_bytes: Байты изображения капчи.
        fns_session: Активная FNS-сессия для keepalive-запросов.
        proxy: Прокси для keepalive-запросов к ФНС (или ``None``).

    Returns:
        Кортеж (текст_капчи, captcha_id).

    Raises:
        RuntimeError: При ошибке API 2captcha.
        TimeoutError: Если капча не решена за отведённое время.

    """
    b64 = base64.b64encode(image_bytes).decode()

    async with aiohttp.ClientSession() as s:
        async with s.post(
            "http://2captcha.com/in.php",
            data={
                "key": _api_key(),
                "method": "base64",
                "body": b64,
                "json": "1",
                "numeric": "1",
                "min_len": "4",
                "max_len": "6",
            },
        ) as resp:
            upload_data = await resp.json(content_type=None)

    if upload_data.get("status") != 1:
        raise RuntimeError(f"2captcha ошибка загрузки: {upload_data}")

    captcha_id: str = upload_data["request"]
    logger.info("Капча отправлена в 2captcha, ID: %s", captcha_id)

    stop = asyncio.Event()
    poll_task = asyncio.create_task(_poll_2captcha(captcha_id))
    keepalive_task = asyncio.create_task(_keepalive_fns(fns_session, stop, proxy))

    try:
        answer = await poll_task
    finally:
        stop.set()
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

    return answer, captcha_id


async def check_blocking(inn: str) -> dict:
    """Выполняет один запрос к ФНС для проверки блокировок счетов.

    Args:
        inn: ИНН организации.

    Returns:
        JSON-ответ сервиса ФНС.

    Raises:
        ValueError: Если капча решена неверно (BAD_CAPTCHA).
        aiohttp.ClientResponseError: При HTTP-ошибках, кроме неверной капчи.

    """
    proxy = _fns_proxy()
    if proxy:
        logger.info("FNS-запросы идут через proxy")

    async with aiohttp.ClientSession(headers=_HEADERS) as session:
        # Открываем страницу как обычный браузер (без X-Requested-With) — FNS ставит JSESSIONID.
        async with session.get(
            "https://service.nalog.ru/bi.do",
            headers={"User-Agent": _HEADERS["User-Agent"]},
            proxy=proxy,
        ) as resp:
            cookies = {c.key: c.value for c in session.cookie_jar.filter_cookies(URL("https://service.nalog.ru")).values()}
            logger.info("bi.do: HTTP %d, cookies: %s", resp.status, cookies)

        token = await _get_captcha_token(session, proxy)
        logger.info("captchaToken: '%s'", token)
        image = await _download_captcha_image(session, token, proxy)
        captcha_text, captcha_id = await _solve_captcha(image, fns_session=session, proxy=proxy)
        logger.info("2captcha ответ: inn=%s captcha='%s'", inn, captcha_text)

        # Шаг 1: валидируем ответ через captcha-proc.json (браузерный диалог-флоу).
        # Возвращает JSON-строку с валидированным токеном.
        async with session.post(
            "https://service.nalog.ru/static/captcha-proc.json",
            data={"captcha": captcha_text, "captchaToken": token},
            proxy=proxy,
        ) as resp:
            proc_raw = await resp.text()
            if resp.status != 200:
                logger.warning("captcha-proc.json HTTP %d: %s", resp.status, proc_raw)
                await _report_bad_captcha(captcha_id)
                raise ValueError("BAD_CAPTCHA")
            try:
                validated_token = json.loads(proc_raw)
            except json.JSONDecodeError:
                validated_token = proc_raw.strip()
            if not isinstance(validated_token, str):
                logger.warning("captcha-proc.json вернул ошибку: %s", proc_raw)
                await _report_bad_captcha(captcha_id)
                raise ValueError("BAD_CAPTCHA")
            logger.info("captcha-proc.json OK, валидированный токен: %s…", validated_token[:20])

        # Шаг 2: отправляем запрос с валидированным токеном.
        async with session.post(
            "https://service.nalog.ru/bi2-proc.json",
            data={
                "requestType": "FINDPRS",
                "innPRS": inn,
                "bikPRS": "000000000",
                "fileName": "",
                "bik": "",
                "innSmev": "",
                "kodTU": "",
                "dateSAFN": "",
                "bikAFN": "",
                "dateAFN": "",
                "fileNameED": "",
                "captcha": "",
                "captchaToken": validated_token,
            },
            proxy=proxy,
        ) as resp:
            logger.debug("HTTP %d", resp.status)

            if resp.status == 400:
                body = await resp.json(content_type=None)
                errors = body.get("ERRORS", {})
                if "captcha" in errors:
                    logger.warning(
                        "ФНС отклонила капчу | inn=%s answer='%s' | ФНС ответ: %s",
                        inn, captcha_text, body,
                    )
                    await _report_bad_captcha(captcha_id)
                    raise ValueError("BAD_CAPTCHA")
                if "innPRS" in errors:
                    raise ValueError(f"INVALID_INN:{errors['innPRS']}")
                logger.warning("Неизвестная ошибка ФНС 400: %s", body)
                resp.raise_for_status()

            return await resp.json(content_type=None)


def parse_result(result: dict) -> None:
    """Выводит результат проверки блокировок в лог.

    Args:
        result: JSON-ответ сервиса ФНС.

    """
    rows = result.get("rows", [])

    if not rows:
        logger.info("Блокировок не найдено")
        return

    logger.info(
        "Найдено блокировок: %d | %s | ИНН: %s",
        len(rows),
        rows[0].get("NAIM"),
        rows[0].get("INN"),
    )
    for row in rows:
        saldo = row.get("SALDOENS", "").strip()
        logger.info(
            "[%2s] БИК: %s | Решение №%s от %s | Сумма: %s",
            row["R"],
            row["BIK"],
            row["NOMER"],
            row["DATA"],
            saldo or "—",
        )


async def run(inn: str, retries: int = 5) -> dict:
    """Проверяет ИНН на блокировки с повторными попытками при плохой капче.

    Args:
        inn: ИНН организации.
        retries: Максимальное число попыток.

    Returns:
        JSON-ответ ФНС или ``None``, если все попытки исчерпаны.

    """
    logger.info("─" * 60)
    logger.info("▶ ИНН: %s", inn)
    for attempt in range(1, retries + 1):
        logger.info("Попытка %d/%d", attempt, retries)
        try:
            result = await check_blocking(inn)
        except ValueError as e:
            msg = str(e)
            if msg == "BAD_CAPTCHA":
                logger.warning("Неверная капча, повторяем...")
                continue
            if msg.startswith("INVALID_INN:"):
                raise ValueError(msg) from e
            raise
        except aiohttp.ClientConnectionError as e:
            raise RuntimeError(f"connection_error: {e}") from e
        except TimeoutError as e:
            raise RuntimeError(f"timeout: {e}") from e

        parse_result(result)
        logger.info("✓ ИНН %s — готово\n", inn)
        return result

    logger.error("✗ ИНН %s — капча не решена\n", inn)
    raise RuntimeError("captcha_failed: не удалось решить капчу за все попытки")
