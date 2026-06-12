"""Точка входа: проверить все ИНН из БД на блокировки ФНС."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from recerence import run
from repository import FnsRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REPORT_DIR = Path(__file__).parent / "reports"
_CONCURRENCY = 1


async def _check_one(
    inn: str, sem: asyncio.Semaphore, report: dict[str, dict], report_path: Path
) -> None:
    """Проверяет один ИНН, обновляет отчёт и сразу сохраняет его на диск.

    Args:
        inn: ИНН организации.
        sem: Семафор для ограничения параллелизма.
        report: Общий словарь результатов (изменяется на месте).
        report_path: Путь к JSON-файлу отчёта.

    """
    try:
        async with sem:
            result = await run(inn, retries=1)
    except ValueError as e:
        msg = str(e)
        report[inn] = {"status": "skipped", "error": msg}
        logger.warning("ИНН %s пропущен: %s", inn, msg)
    except RuntimeError as e:
        msg = str(e)
        report[inn] = {"status": "failed", "error": msg}
        logger.error("ИНН %s: %s", inn, msg)
    else:
        rows = result.get("rows", [])
        report[inn] = {
            "status": "blocked" if rows else "clean",
            "checked_at": result.get("datePRS"),
            "rows": rows,
        }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Сохранено [%d/%d]: %s", len(report), len(report), report_path.name)
    print("\n")


async def main() -> None:
    """Загружает все ИНН из БД, проверяет параллельно и сохраняет отчёт."""
    inns = await FnsRepository.get_all_inns()
    logger.info("Найдено ИНН для проверки: %d (параллельность: %d)", len(inns), _CONCURRENCY)

    _REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = _REPORT_DIR / f"fns_report_{ts}.json"

    report: dict[str, dict] = {}
    sem = asyncio.Semaphore(_CONCURRENCY)
    await asyncio.gather(*[_check_one(inn, sem, report, report_path) for inn in inns])
    logger.info("Готово. Итоговый отчёт: %s (%d ИНН)", report_path, len(report))


if __name__ == "__main__":
    asyncio.run(main())
