# fichar.py

Script per automatitzar el fichatge mensual a **FactorialHR**. Crea o elimina els torns d'un mes sencer respectant festius, caps de setmana i absències/vacances registrades a Factorial.

## Horari configurat

| Dies | Torn 1 | Torn 2 |
|------|--------|--------|
| Dilluns – Dijous | 09:00 – 14:00 | 15:00 – 18:30 |
| Divendres | 09:00 – 15:30 | — |

## Requisits

```bash
pip install requests
```

## Ús

```bash
python3 fichar.py --fichar    --soc-un-liao-ficham-el <mes>
python3 fichar.py --desfichar --soc-un-liao-ficham-el <mes>
```

### Flags

| Flag | Descripció |
|------|------------|
| `--fichar` | Crea els fichatges que falten al mes indicat |
| `--desfichar` | Elimina tots els fichatges del mes indicat |
| `--soc-un-liao-ficham-el <mes>` | Mes a processar (vegeu formats acceptats) |
| `--dry-run` | Simula l'operació sense fer cap canvi real |

### Formats de mes acceptats

```bash
--soc-un-liao-ficham-el 4        # número
--soc-un-liao-ficham-el abril    # nom en castellà
--soc-un-liao-ficham-el 2026-04  # any-mes
```

### Exemples

```bash
# Fichar l'abril
python3 fichar.py --fichar --soc-un-liao-ficham-el 4

# Simular el fichatge sense fer canvis
python3 fichar.py --fichar --soc-un-liao-ficham-el abril --dry-run

# Eliminar tots els fichatges de març
python3 fichar.py --desfichar --soc-un-liao-ficham-el 3

# Fichar un mes d'un any concret
python3 fichar.py --fichar --soc-un-liao-ficham-el 2026-05
```

## Com funciona

1. Fa login a FactorialHR mitjançant sessió web (no requereix API key)
2. Obté el calendari laboral del mes des de la pròpia API (festius i absències inclosos)
3. Per a `--fichar`: crea els torns que falten, saltant els dies ja fitxats, festius, caps de setmana i dies de vacances/baixa
4. Per a `--desfichar`: elimina tots els torns del mes

Els dies no laborables i les absències es detecten automàticament des de Factorial, no cal configurar res manualment.

## Credencials

El script busca un arxiu `.env` al mateix directori amb el format:

```
User: el.teu.email@empresa.com
Password: la_teva_contrasenya
```

Si no existeix, demana les credencials de forma interactiva. L'arxiu `.env` està inclòs al `.gitignore` i mai es pujarà al repositori.

## Inspirat en

[alejoar/factorialsucks](https://github.com/alejoar/factorialsucks)
