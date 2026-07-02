# fichar.py

Automatitza el fitxatge mensual a **FactorialHR**. Crea els torns d'un mes sencer —o de uns quants de cop— i salta festius, caps de setmana i absències sense que hagis de moure un dit. Tu poses el mes; ell posa les hores.

> `factorialsucks` va morir el dia que Factorial es va passar al login SSO (`id.factorialhr.com`): el seu inici de sessió per email+contrasenya ja no existeix i tot petava amb un `401` disfressat de "període no disponible". Descansi en pau. 🪦
>
> Aquest script no perd el temps trucant a portes tancades: agafa una **cookie de sessió** del teu navegador i clava els fitxatges directament contra l'API. Sense floritures.

## Requisits

**Python 3** i prou. Cap `pip install`, cap dependència externa: només `urllib` de la biblioteca estàndard. Com aquí fora, com menys coses depenguis, més aguantes.

## Autenticació (cookie de sessió)

El login SSO només se supera des del navegador, així que li passem la sessió ja feta:

1. Entra a **app.factorialhr.com** amb el teu compte.
2. Obre **DevTools** (`F12`) → pestanya **Network** → filtre **Fetch/XHR**.
3. Ves a **Assistència / Fitxatges** perquè es disparin crides a l'API.
4. Botó dret sobre una petició a `api.factorialhr.com/attendance/*` → **Copy → Copy as cURL**.
5. Enganxa **tot** aquell bloc `curl ...` al fitxer de sessió (per defecte `~/Setup/factorial_session.txt`).

D'aquí en surten sols la **cookie**, el teu `access_id` i el teu `employee_id` (aquest últim viu dins el JWT `_factorial_id`). Res hardcodejat, res a mà.

> ⚠️ La cookie es panseix en ~2h; al sol dura encara menys. Si et surt un `HTTP 401`, torna a copiar el cURL i endavant.

## Ús

```bash
python3 fichar.py -m <mes>          # dry-run: ensenya el pla, no escriu res
python3 fichar.py -m <mes> --go     # fitxa de debò
```

Per defecte fa **dry-run**: mira però no toca. Fins que no hi poses `--go`, no passa res. Amb calma, que no marxa enlloc.

### Flags

| Flag | Descripció |
|------|------------|
| `-m`, `--month` | Mes o mesos a processar (ex: `6` o `4,5,6`). Per defecte, el mes actual. |
| `-y`, `--year` | Any. Per defecte, l'any actual. |
| `--ci` | Hora d'entrada (`HH:MM`). Per defecte `09:00`. |
| `--co` | Hora de sortida (`HH:MM`). Per defecte `18:00`. |
| `-s`, `--session` | Ruta del fitxer amb el cURL de sessió. Per defecte `~/Setup/factorial_session.txt`. |
| `--go` | Fitxa de debò. Sense aquest flag, només fa dry-run. |

Cada dia laborable es fitxa amb **un únic torn** `--ci`–`--co` (per defecte 09:00–18:00). Vols un altre horari? Doncs `--ci`/`--co` i au.

### Exemples

```bash
# Previsualitzar el juny (dry-run)
python3 fichar.py -m 6

# Fitxar el juny de debò
python3 fichar.py -m 6 --go

# Fitxar abril, maig i juny de cop
python3 fichar.py -m 4,5,6 --go

# Fitxar el juliol amb un altre horari
python3 fichar.py -m 7 --ci 08:00 --co 17:00 --go

# Fitxar un mes d'un any concret
python3 fichar.py -m 5 -y 2026 --go
```

## Com funciona

1. Llegeix la sessió del fitxer cURL i en extreu cookie, `access_id` i `employee_id`.
2. Per a cada mes consulta el **període** (`/attendance/periods`); si no existeix o no està en estat `pending` (editable), el salta.
3. Obté el **calendari laboral** del mes (`/attendance/calendar`), amb festius i absències inclosos.
4. Mira els torns **ja existents** (`/attendance/shifts`) per no duplicar dies.
5. Crea (`POST /attendance/shifts`) un torn per cada dia laborable que falti, saltant caps de setmana, festius i vacances/baixes.
6. En acabar, verifica i mostra els `worked_minutes` reals del mes.

Festius i absències es detecten automàticament des de Factorial: no cal configurar res a mà.

## Seguretat

El fitxer de sessió (`factorial_session.txt`) conté una **cookie viva**: és un secret. **No el pugis mai al repositori.** Fica'l al `.gitignore`:

```gitignore
factorial_session.txt
.env
```

## Inspirat en

[alejoar/factorialsucks](https://github.com/alejoar/factorialsucks) — que descansi en pau.
