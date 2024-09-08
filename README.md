# WhatsappIA

## EJECUTA ESTE COMANDO PARA INICIAR CHROME CON EL PUERTO DE DEBUGGING

- WINDOWS

```bash
C:\Program Files\Google\Chrome\Application\chrome.exe --remote-debugging-port=9222 --user-data-dir="C:/ChromeDevUser"
```

- LINUX

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="C:/ChromeDevUser"
```

- MAC

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="C:/ChromeDevUser"
```

## ABRE WHATSAPP WEB Y ESCANEA EL CODIGO QR

```bash
https://web.whatsapp.com/
```

## ISNTALA LAS DEPENDENCIAS

```bash
pip install -r requirements.txt
```

## CERA UN ENTORNO VIRTUAL PARA LOS DISTINTOS SISTEMAS OPERATIVOS

- WINDOWS

```bash
python -m venv env
```

- LINUX

```bash
python3 -m venv env
```

- MAC

```bash
python3 -m venv env
```

## INCIA EL ENTORNO VIRTUAL PARA LOS DISTINTOS SIRVE PARA LOS DISTINTOS SISTEMAS OPERATIVOS

- WINDOWS

```bash
.\env\Scripts\activate
```

- LINUX

```bash
source env/bin/activate
```

- MAC

```bash
source env/bin/activate
```

## EJECUTA EL ARCHIVO PRINCIPAL

```bash
python watsappIA.py
```
