#!/usr/bin/env python3
"""
Ficha / desfiche automático en FactorialHR.

Uso:
  fichar.py --fichar    --soc-un-liao-ficham-el 3
  fichar.py --desfichar --soc-un-liao-ficham-el 3
  fichar.py --fichar    --soc-un-liao-ficham-el 3 --dry-run

Horario:
  Lunes–Jueves: 09:00–14:00 y 15:00–18:30
  Viernes:      09:00–15:30
"""

import argparse
import getpass
import json
import sys
from datetime import date, datetime

from pathlib import Path

import requests

BASE_URL = "https://api.factorialhr.com"
SHIFTS_EP = f"{BASE_URL}/api/2026-04-01/resources/attendance/shifts"

SCHEDULE = {
    0: [("09:00", "14:00"), ("15:00", "18:30")],  # Lunes
    1: [("09:00", "14:00"), ("15:00", "18:30")],  # Martes
    2: [("09:00", "14:00"), ("15:00", "18:30")],  # Miércoles
    3: [("09:00", "14:00"), ("15:00", "18:30")],  # Jueves
    4: [("09:00", "15:30")],                       # Viernes
}

MONTH_NAMES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def to_minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def overlaps(ci: str, co: str, existing: list) -> bool:
    a, b = to_minutes(ci), to_minutes(co)
    for s in existing:
        c, d = to_minutes(s["clock_in"]), to_minutes(s["clock_out"])
        if (a < c < b) or (a < d < b) or (c <= a and d >= b):
            return True
    return False


def login(session: requests.Session, email: str, password: str) -> str | None:
    r = session.get(f"{BASE_URL}/users/sign_in", headers={"Accept": "text/html"})
    r.raise_for_status()
    marker = '<meta name="csrf-token" content="'
    idx = r.text.find(marker)
    csrf = ""
    if idx != -1:
        start = idx + len(marker)
        csrf = r.text[start: r.text.find('" />', start)]

    data = {
        "authenticity_token": csrf,
        "return_host": "factorialhr.es",
        "user[email]": email,
        "user[password]": password,
        "user[remember_me]": "0",
        "commit": "Sign in",
    }
    r = session.post(
        f"{BASE_URL}/users/sign_in",
        data=data,
        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        allow_redirects=True,
    )
    if '<div class="flash flash--wrong">' in r.text or r.status_code not in (200, 201, 302):
        return None
    return csrf


def get_employee_id(session: requests.Session, year: int, month: int) -> int | None:
    r = session.get(f"{BASE_URL}/attendance/periods", params={"year": year, "month": month})
    r.raise_for_status()
    periods = r.json()
    if not periods:
        return None
    p = periods[0] if isinstance(periods, list) else periods
    return p.get("employee_id")


def get_calendar(session: requests.Session, employee_id: int, year: int, month: int) -> list:
    r = session.get(
        f"{BASE_URL}/attendance/calendar",
        params={"id": employee_id, "year": year, "month": month},
    )
    r.raise_for_status()
    return r.json()


def get_shifts(session: requests.Session, employee_id: int, year: int, month: int) -> list:
    r = session.get(SHIFTS_EP, params={"employee_id": employee_id})
    r.raise_for_status()
    data = r.json()
    all_shifts = data.get("data", []) if isinstance(data, dict) else data
    prefix = f"{year}-{month:02d}-"
    return [s for s in all_shifts if s.get("date", "").startswith(prefix)]


def cmd_fichar(session: requests.Session, employee_id: int, year: int, month: int, dry_run: bool):
    calendar = get_calendar(session, employee_id, year, month)
    existing = get_shifts(session, employee_id, year, month)

    shifts_by_day: dict[int, list] = {}
    for s in existing:
        d = int(s["date"].split("-")[2])
        shifts_by_day.setdefault(d, []).append(s)

    created = skipped = errors = 0

    for cal_day in sorted(calendar, key=lambda x: x["day"]):
        day_num = cal_day["day"]
        date_str = f"{year}-{month:02d}-{day_num:02d}"

        if not cal_day.get("is_laborable", True):
            print(f"  {date_str}  ⏭  No laborable")
            continue

        if cal_day.get("is_leave", False):
            leaves = cal_day.get("leaves", [])
            leave_name = leaves[0].get("name", "vacaciones/baja") if leaves else "vacaciones/baja"
            print(f"  {date_str}  ⏭  {leave_name}")
            continue

        weekday = date(year, month, day_num).weekday()
        if weekday >= 5:
            continue

        tramos = SCHEDULE.get(weekday, [])
        day_shifts = shifts_by_day.get(day_num, [])

        for ci, co in tramos:
            label = f"  {date_str}  {ci}-{co}"
            if overlaps(ci, co, day_shifts):
                print(f"{label}  ⏭  Ya fichado")
                skipped += 1
                continue

            if not dry_run:
                r = session.post(
                    SHIFTS_EP,
                    json={"employee_id": employee_id, "date": date_str, "clock_in": ci, "clock_out": co},
                    headers={"Content-Type": "application/json;charset=UTF-8"},
                )
                ok = r.status_code in (200, 201)
                if not ok:
                    print(f"{label}  ❌ {r.status_code}: {r.text[:100]}")
                    errors += 1
                    continue

            tag = "🔍 (dry)" if dry_run else "✅"
            print(f"{label}  {tag}")
            created += 1
            day_shifts.append({"clock_in": ci, "clock_out": co})

    print(f"\n{'=' * 42}")
    print(f"  Creados : {created}")
    print(f"  Saltados: {skipped}")
    print(f"  Errores : {errors}")
    if dry_run:
        print("  ⚠️  Dry-run — ningún cambio guardado")


def cmd_desfichar(session: requests.Session, employee_id: int, year: int, month: int, dry_run: bool):
    shifts = get_shifts(session, employee_id, year, month)
    if not shifts:
        print("  No hay fichajes para este mes.")
        return

    deleted = errors = 0
    for s in shifts:
        label = f"  {s['date']}  {s['clock_in']}-{s['clock_out']}  (id={s['id']})"
        if dry_run:
            print(f"{label}  🔍 (dry)")
            deleted += 1
            continue
        r = session.delete(f"{SHIFTS_EP}/{s['id']}")
        if r.status_code in (200, 204):
            print(f"{label}  🗑️")
            deleted += 1
        else:
            print(f"{label}  ❌ {r.status_code}")
            errors += 1

    print(f"\n{'=' * 42}")
    print(f"  Eliminados: {deleted}")
    print(f"  Errores   : {errors}")
    if dry_run:
        print("  ⚠️  Dry-run — ningún cambio guardado")


def load_credentials() -> tuple[str, str]:
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        email = password = ""
        for line in env_path.read_text().splitlines():
            if line.startswith("User:"):
                email = line.split(":", 1)[1].strip()
            elif line.startswith("Password:"):
                password = line.split(":", 1)[1].strip()
        if email and password:
            print("🔑 Credencials carregades des de .env")
            return email, password
        print("⚠️  Arxiu .env trobat però incomplet, es demanen les credencials manualment.")

    email = input("Email de Factorial: ").strip()
    password = getpass.getpass("Contraseña: ")
    return email, password


def parse_month(value: str) -> tuple[int, int]:
    """Returns (year, month). Accepts '3', '03', 'marzo', '2026-03', etc."""
    now = datetime.now()
    name_to_num = {v: k for k, v in MONTH_NAMES.items()}
    v = value.strip().lower()

    if v in name_to_num:
        return now.year, name_to_num[v]

    if "-" in v:
        parts = v.split("-")
        if len(parts) == 2:
            y, m = int(parts[0]), int(parts[1])
            return y, m

    m = int(v)
    if not 1 <= m <= 12:
        raise ValueError(f"Mes fuera de rango: {m}")
    year = now.year if m >= now.month else now.year
    return year, m


def main():
    parser = argparse.ArgumentParser(description="Fichaje automático FactorialHR")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--fichar", action="store_true", help="Crea los fichajes del mes")
    action.add_argument("--desfichar", action="store_true", help="Elimina todos los fichajes del mes")
    parser.add_argument(
        "--soc-un-liao-ficham-el",
        metavar="MES",
        required=True,
        dest="mes",
        help="Mes a fichar: número (3), nombre (marzo) o año-mes (2026-03)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simula sin hacer cambios")

    args = parser.parse_args()

    try:
        year, month = parse_month(args.mes)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    month_label = f"{MONTH_NAMES.get(month, month)} {year}"
    action_label = "Fichaje" if args.fichar else "Desfichaje"
    print(f"=== {action_label} automático — {month_label} ===\n")

    if args.dry_run:
        print("🔍 MODO DRY-RUN — no se harán cambios reales\n")

    email, password = load_credentials()

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    print("\n🔐 Iniciando sesión...")
    csrf = login(session, email, password)
    if not csrf:
        print("❌ Error de autenticación.")
        sys.exit(1)
    session.headers.update({"X-CSRF-Token": csrf})
    print("✅ Sesión iniciada\n")

    employee_id = get_employee_id(session, year, month)
    if not employee_id:
        print("❌ No se pudo obtener el ID de empleado.")
        sys.exit(1)

    print(f"👤 Employee ID: {employee_id}\n")

    if args.fichar:
        cmd_fichar(session, employee_id, year, month, args.dry_run)
    else:
        cmd_desfichar(session, employee_id, year, month, args.dry_run)


if __name__ == "__main__":
    main()
