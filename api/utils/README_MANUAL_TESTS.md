# Utilitats de Testing Manual

Aquest directori conté scripts d'utilitat per fer tests manuals que **NO** són tests automatitzats amb pytest.

## 📁 Fitxers

### `firebase_auth_manual_test.py`

Script interactiu per testejar l'autenticació Firebase JWT amb l'API.

**No és un test automàtic** - requereix interacció manual i un token JWT real de Firebase.

#### Com utilitzar-lo:

```bash
# Assegura't que el servidor Django està executant-se
python manage.py runserver

# En un altre terminal, executa el script
python api/utils/firebase_auth_manual_test.py
```

El script et guiarà per:
1. Testejar endpoints públics (no requereixen autenticació)
2. Testejar endpoints amb autenticació (necessites proporcionar un token JWT real)
3. Verificar que els endpoints protegits rebutgen peticions sense token

#### Requisits per tests amb autenticació:
- Un usuari creat a Firebase Authentication
- Un token JWT vàlid obtingut des del frontend o Firebase Console
- El servidor Django executant-se

---

## ⚠️ Nota Important

Els fitxers d'aquest directori **NO** són executats per pytest i no contribueixen al coverage dels tests automatitzats.

Per executar els **tests automatitzats**, utilitza:
```bash
pytest api/tests/
```

Per més informació sobre tests automatitzats, consulta `TESTING_GUIDE.md` i `TESTING_SUMMARY.md` a l'arrel del projecte.
