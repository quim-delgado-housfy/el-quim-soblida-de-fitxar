#!/usr/bin/env python3
"""
fichar.py — Fitxa a Factorial en lot, perquè omplir 56 caselles a mà és de masoquistes.

El diví binari `factorialsucks` va morir el dia que Factorial va decidir que el login
d'abans ja no molava (hola, SSO). Així que ho fem a pèl: robem la cookie del navegador
i li clavem els fitxatges directament a l'API. Elegant no és, però funciona.

--------------
1) Entra a app.factorialhr.com. DevTools (F12) -> Network -> Fetch/XHR.
   Botó dret sobre una petició a api.factorialhr.com/attendance/* -> Copy -> Copy as cURL.
2) Enganxa TOT aquell bloc al fitxer de sessió (per defecte: ~/Setup/factorial_session.txt).
3) Dry-run:                     python3 fichar.py -m 6
   Fichaje ahí ueno ueno:       python3 fichar.py -m 6 --go
   Diversos mesos de cop:       python3 fichar.py -m 4,5,6 --go

La cookie caduca en ~2h (factorialsucks). Si veus un 401,
torna a copiar el cURL i repeteix. Salta caps de setmana, festius i absències tot solet,
i no repeteix dies ja fitxats.
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.factorialhr.com"
DEFAULT_SESSION = os.path.expanduser("~/Setup/factorial_session.txt")
MESOS = {1: "GENER", 2: "FEBRER", 3: "MARÇ", 4: "ABRIL", 5: "MAIG", 6: "JUNY",
         7: "JULIOL", 8: "AGOST", 9: "SETEMBRE", 10: "OCTUBRE", 11: "NOVEMBRE", 12: "DESEMBRE"}


def die(msg):
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def parse_session(path):
    """Espigola la cookie, l'access_id i l'employee_id del cURL enganxat del navegador."""
    if not os.path.exists(path):
        die(f"No existeix el fitxer de sessió: {path}\n"
            f"   Enganxa-hi el 'Copy as cURL' d'una petició a api.factorialhr.com/attendance/*, ")
    text = open(path).read().strip()
    if not text:
        die(f"El fitxer de sessió està buit gandul!: {path}")

    # Cookie: pot venir com -H 'Cookie: ...' o -b '...'
    m = re.search(r"-H\s+(['\"])[Cc]ookie:\s*(.*?)\1", text, re.S)
    if not m:
        m = re.search(r"-b\s+(['\"])(.*?)\1", text, re.S)
    if not m:
        die("No trobo la cookie enlloc. Segur que has enganxat el cURL sencer i no alguna merda?")
    cookie = m.group(2).strip()

    # X-Factorial-Access (capçalera). Si no hi és, se'l dedueix de la cookie _factorial_data.
    ma = re.search(r"-H\s+(['\"])[Xx]-[Ff]actorial-[Aa]ccess:\s*(.*?)\1", text, re.S)
    access = ma.group(2).strip() if ma else cookie_access_id(cookie)

    emp = employee_id_from_cookie(cookie)
    if not emp:
        die("No he pogut treure l'employee_id del JWT _factorial_id. Cookie rara, aquesta.")
    return cookie, access, emp


def _cookie_value(cookie, name):
    m = re.search(rf"(?:^|;\s*){re.escape(name)}=([^;]+)", cookie)
    return m.group(1) if m else None


def cookie_access_id(cookie):
    raw = _cookie_value(cookie, "_factorial_data")
    if not raw:
        return None
    try:
        data = json.loads(urllib.parse.unquote(raw))
        return str(data.get("access_id") or "")
    except Exception:
        return None


def employee_id_from_cookie(cookie):
    """El JWT _factorial_id porta l'employee_id al camp 'eid'."""
    jwt = _cookie_value(cookie, "_factorial_id")
    if not jwt or "." not in jwt:
        return None
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # farciment base64url
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return int(claims["eid"])
    except Exception:
        return None


class Factorial:
    def __init__(self, cookie, access, emp):
        self.emp = emp
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://app.factorialhr.com/",
            "Origin": "https://app.factorialhr.com",
            "X-Factorial-Origin": "web",
            "X-Deployment-Phase": "default",
            "X-Factorial-BigInt-Support": "true",
            "content-type": "application/json",
            "Cookie": cookie,
        }
        if access:
            self.headers["X-Factorial-Access"] = str(access)

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw else None), ""
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:200]
            if e.code == 401:
                die("Sessió caducada o invàlida (HTTP 401). Factorial t'ha enviat a la shiat.\n"
                    "   Copia un cURL fresquet del navegador al fitxer de sessió i torna-hi.")
            return e.code, None, err

    def periode(self, year, month):
        _, data, _ = self._req("GET", f"/attendance/periods?year={year}&month={month}&employee_id={self.emp}")
        return data[0] if data else None

    def calendari(self, year, month):
        _, data, _ = self._req("GET", f"/attendance/calendar?id={self.emp}&year={year}&month={month}")
        return data or []

    def shifts(self, year, month):
        _, data, _ = self._req("GET", f"/attendance/shifts?employee_id={self.emp}&year={year}&month={month}")
        return data or []

    def crea_shift(self, year, month, day, ci, co):
        date = f"{year}-{month:02d}-{day:02d}"
        body = {"clock_in": ci, "clock_out": co, "day": day, "employee_id": self.emp,
                "workable": True, "minutes": None, "date": date, "source": "desktop",
                "reference_date": date}
        code, _, err = self._req("POST", "/attendance/shifts", body)
        return code, err


def dies_laborables(cal):
    return [d["day"] for d in cal if d.get("is_laborable") and not d.get("is_leave")]


def dies_saltats(cal):
    out = []
    for d in cal:
        if d.get("is_leave"):
            nom = d.get("leave_name") or (d["leaves"][0].get("name") if d.get("leaves") else "") or "absència"
            out.append(f"{d['day']}({nom})")
    return out


def main():
    avui = dt.date.today()
    ap = argparse.ArgumentParser(
        description="Fitxa a Factorial en lot, que la vida són quatre dies (laborables).")
    ap.add_argument("-m", "--month", default=str(avui.month),
                    help="Mes o mesos (ex: 6 o 4,5,6). Per defecte, el mes que patim ara.")
    ap.add_argument("-y", "--year", type=int, default=avui.year,
                    help="Any (per defecte l'actual, no som viatgers del temps).")
    ap.add_argument("--ci", default="09:00", help="Hora d'entrada (per defecte 09:00, quin remei).")
    ap.add_argument("--co", default="18:00", help="Hora de sortida (per defecte 18:00, la llibertat).")
    ap.add_argument("-s", "--session", default=DEFAULT_SESSION,
                    help="Fitxer amb el cURL de sessió robat del navegador.")
    ap.add_argument("--go", action="store_true",
                    help="Fitxar real no fake.")
    args = ap.parse_args()

    try:
        mesos = sorted({int(x) for x in args.month.split(",") if x.strip()})
    except ValueError:
        die(f"Mes invàlid: {args.month!r}. Prova amb -m 6 o -m 4,5,6, que no és tan difícil.")
    if not all(1 <= mth <= 12 for mth in mesos):
        die("Els mesos van de l'1 al 12...")

    cookie, access, emp = parse_session(args.session)
    fac = Factorial(cookie, access, emp)
    mode = "FITXANT DE DEBÒ" if args.go \
        else "DRY-RUN (no toco res, respira tranquil)"
    print(f"Treballador {emp} · {args.year} · {args.ci}-{args.co} · {mode}\n")

    total_ok = 0
    for mth in mesos:
        per = fac.periode(args.year, mth)
        if not per:
            print(f"⚠ {MESOS[mth]} {args.year}: no hi ha període. Passo.\n")
            continue
        if per.get("state") != "pending":
            print(f"⚠ {MESOS[mth]} {args.year}: període en estat '{per.get('state')}' "
                  f"Passo.\n")
            continue
        cal = fac.calendari(args.year, mth)
        laborables = dies_laborables(cal)
        ja = {s.get("day") for s in fac.shifts(args.year, mth)}
        pendents = [d for d in laborables if d not in ja]
        saltats = dies_saltats(cal)

        print(f"=== {MESOS[mth]} {args.year} ===")
        print(f"  laborables: {len(laborables)} | ja fitxats: {len(laborables) - len(pendents)} | per fitxar: {len(pendents)}")
        if saltats:
            print(f"  festius/absències: {', '.join(saltats)}")
        print(f"  dies per fitxar: {', '.join(map(str, pendents)) or 'no ian dies per fitxar :('}")

        if args.go:
            ok = 0
            for day in pendents:
                code, err = fac.crea_shift(args.year, mth, day, args.ci, args.co)
                if code == 201:
                    ok += 1
                else:
                    print(f"    ❌ dia {day}: HTTP {code} {err}")
            per2 = fac.periode(args.year, mth) or {}
            wm = per2.get("worked_minutes", 0)
            print(f"  ✅ creats {ok}/{len(pendents)} · total del mes: {wm} min (~{wm/60:.1f}h de glòria)")
            total_ok += ok
        print()

    if not args.go:
        print("Això era un dry-run. Posa-hi --go quan vulguis fitxar de debò")
    else:
        print(f"Fet. Fitxatges clavats: {total_ok}. Ja pots fer veure que has treballat.")


if __name__ == "__main__":
    main()
