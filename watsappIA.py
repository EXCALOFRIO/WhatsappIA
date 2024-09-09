import os
import time
import logging
from colorama import Fore, Style, init
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import google.generativeai as genai
from selenium.common.exceptions import WebDriverException, TimeoutException
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import random
import datetime

# Inicializa colorama
init(autoreset=True)
# Lista de colores disponibles
COLORES_DISPONIBLES = [
    Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.WHITE
]

# Diccionario para almacenar el color asignado a cada usuario
colores_usuarios = {}

# Función para asignar colores aleatorios a los usuarios, asegurando que sean únicos
def asignar_color_usuario(remitente):
    if remitente not in colores_usuarios:
        colores_disponibles_copia = COLORES_DISPONIBLES[:]  # Copia de la lista de colores
        # Si ya se han asignado todos los colores, reiniciar la lista
        if len(colores_usuarios) >= len(COLORES_DISPONIBLES):
            colores_usuarios.clear()
        # Eliminar colores ya asignados
        for color in colores_usuarios.values():
            if color in colores_disponibles_copia:
                colores_disponibles_copia.remove(color)
        # Asignar un color aleatorio de los disponibles
        colores_usuarios[remitente] = random.choice(colores_disponibles_copia)
    return colores_usuarios[remitente]

# Función para eliminar la palabra "Editado" de la hora
def limpiar_hora(hora):
    return hora.replace("Editado", "").strip()

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicializa el modelo Gemini Flash directamente
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('models/gemini-1.5-flash-001')

def filtrar_caracteres_no_bmp(texto):
    return "".join(c for c in texto if ord(c) < 0x10000)

def iniciar_navegador(max_intentos=5, tiempo_espera=15):
    for intento in range(max_intentos):
        try:
            logging.info(f"{Fore.YELLOW}Intento {intento + 1} de iniciar el navegador...")
            
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Esperar a que se cargue la página de WhatsApp Web, buscando un elemento específico
            WebDriverWait(driver, tiempo_espera).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#pane-side"))  # ID del panel lateral de WhatsApp
            )
            
            logging.info(f"{Fore.GREEN}Conectado exitosamente a la instancia de Chrome...")
            return driver
        except WebDriverException as e:
            logging.error(f"{Fore.RED}Error al iniciar el WebDriver: {e}")
        except TimeoutException:
            logging.error(f"{Fore.RED}Tiempo de espera agotado al cargar WhatsApp Web")
        except Exception as e:
            logging.error(f"{Fore.RED}Error inesperado al iniciar el navegador: {e}")
        
        if intento < max_intentos - 1:
            tiempo_espera_reinicio = (intento + 1) * 5
            logging.info(f"{Fore.YELLOW}Esperando {tiempo_espera_reinicio} segundos antes de reintentar...")
            time.sleep(tiempo_espera_reinicio)
    
    logging.error(f"{Fore.RED}No se pudo iniciar el navegador después de {max_intentos} intentos.")
    return None

def obtener_datos_chat(driver, limite=None):
    try:
        logging.info(f"{Fore.YELLOW}Obteniendo datos del chat...")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='row']"))
        )

        mensajes = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
        if limite:
            mensajes = mensajes[-limite:]
        datos_chat = []

        try:
            nombre_conversacion = driver.find_element(By.CSS_SELECTOR, "header ._amig ._ao3e").text
        except:
            nombre_conversacion = "Nombre no disponible"

        ultimo_remitente = None

        for mensaje in mensajes:
            try:
                # Primero intenta obtener el remitente por aria-label
                remitente_label = mensaje.find_element(By.CSS_SELECTOR, "div._amk6._amlo span[aria-label]").get_attribute("aria-label")
                if remitente_label and remitente_label.startswith("Tú:"):
                    remitente = "Tú"
                else:
                    remitente = remitente_label.split(":")[0] if ":" in remitente_label else None

                # Si no se encuentra aria-label, busca por span._ahxt
                if remitente is None:
                    remitente = mensaje.find_element(By.CSS_SELECTOR, "span._ahxt").text

                ultimo_remitente = remitente
            except:
                # Si no se encuentra remitente por los métodos anteriores, intenta por data-id
                data_id = mensaje.get_attribute("data-id")
                if data_id and data_id.startswith("true_"):
                    remitente = "Tú"
                else:
                    remitente = ultimo_remitente if ultimo_remitente is not None else nombre_conversacion

            try:
                # Primero intenta obtener la hora por span.x1rg5ohu
                hora = mensaje.find_element(By.CSS_SELECTOR, "div[role='row'] span.x1rg5ohu[dir='auto']").text
            except:
                try:
                    # Si no se encuentra, intenta obtenerla de data-pre-plain-text
                    texto_pre_plain = mensaje.find_element(By.CSS_SELECTOR, "div.copyable-text").get_attribute("data-pre-plain-text")
                    hora = texto_pre_plain.split("[")[1].split("]")[0]
                except:
                    hora = "Hora no disponible"

            try:
                texto = mensaje.find_element(By.CSS_SELECTOR, "span.selectable-text").text
                # Eliminar mensajes con "Mensaje sin texto"
                if texto == "Mensaje sin texto":
                    continue 
            except:
                texto = ""  # Si no hay texto, dejarlo vacío

            datos_chat.append({
                "conversacion": nombre_conversacion,
                "remitente": remitente,
                "hora": hora,
                "texto": texto
            })

        logging.info(f"{Fore.YELLOW}Datos del chat obtenidos: {len(datos_chat)} mensajes.")
        return datos_chat

    except Exception as e:
        logging.error(f"{Fore.RED}Error al obtener datos del chat: {e}")
        return []

def enviar_mensaje(driver, mensaje, delay=0.1):
    try:
        mensaje_filtrado = filtrar_caracteres_no_bmp(mensaje)
        input_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//footer//div[@contenteditable='true']"))
        )
        input_box.send_keys(mensaje_filtrado + Keys.ENTER)
        logging.info(f"{Fore.CYAN}Mensaje enviado: {mensaje_filtrado}")
        time.sleep(delay * len(mensaje_filtrado))  # Delay por cada letra del mensaje
    except Exception as e:
        logging.error(f"{Fore.RED}Error al enviar mensaje: {e}")

def generar_respuesta(historial, nuevos_mensajes, nombre_contacto):
    nuevos_mensajes_texto = "\n".join([f"{nombre_contacto}: {msg['texto']}" for msg in nuevos_mensajes])
    
    prompt = f"""
    Estás en un grupo de WhatsApp con tus amigos.
    Eres Alejandro Ramirez, un joven de 22 años, y hablas como tal.
    Mantén un tono informal, coloquial, y usa jerga y abreviaturas comunes entre la gente de tu edad.
    Incorpora emojis de forma natural para expresar emociones o añadir humor.

    **Responde como lo harías en WhatsApp, con mensajes cortos y directos, a veces separados en varios mensajes.**
    **Inspírate en el formato de estos ejemplos de respuesta, pero NO uses el contenido o las ideas específicas. Simplemente sigue el estilo.**

    Ejemplo 1:
    **Incorrecto:** ¡Wow, qué bien te quedó! Lo hiciste genial. 😎
    **Correcto:**
    Uff brutal
    De locos

    Ejemplo 2:
    **Incorrecto:** No puedo creer lo que pasó. ¿En serio? 😱
    **Correcto:**
    Aah no te creo
    q fuertee 😱

    Ejemplo 3:
    **Incorrecto:** ¡Qué risa me dio eso! 😂
    **Correcto:**
    Jajajaja 
    me memeoo

    Ejemplo 4:
    **Incorrecto:** Me sorprendió mucho lo que me contaste. ¡Impresionante! 🤯
    **Correcto:**
    Ufff q locura
    me quedé flipando 🤯
    
    Ejemplo 5:
    **Incorrecto:** Me sorprendió mucho lo que me contaste. ¡Impresionante! 🤯
    **Correcto:**
    Brooo
    Estoy en shock
    
    Ejemplo 6:
    **Incorrecto:** ¡Qué risa me dio eso! 😂
    **Correcto:**
    JAJAJAJAJAA 
    buena esaaa 😂
    
    Ejemplo 7:
    **Incorrecto:** No puedo creer lo que pasó. ¿En serio? 😱
    **Correcto:**
    Q dicess
    Cuenta cuentaa
    
    Ejemplo 8:
    **Incorrecto:** ¡Wow, qué bien te quedó! Lo hiciste genial. 😎
    **Correcto:**
    Lo has hecho tu??
    esta finisimoo
    
    Ejemplo 9:
    **Incorrecto:** ¿Al final cúando sera la barbacoa?
    **Correcto:**
    Oyee
    la barbacoa cuando??
    
    Ejemplo 10:
    **Incorrecto:** ¿Quieres salir de fiesta?
    **Correcto:**
    Salimos
    ???

    **Recuerda:**
    ** SOLO RESPONDE A LOS MENSAJES NUEVOS, NO A LOS ANTERIORES. **
    - Usa onomatopeyas como "jajaja", "uff", "ahh", "xd" para reaccionar.
    - Usa abrebiaturas como "q" en lugar de "que", "x" en lugar de "por", "tb" en lugar de "también".
    - No uses signos de puntuación al final de las frases, a menos que sea una pregunta.
    - No uses la interrogación de apertura (¿) ni la exclamación de apertura (¡).
    - Varía la capitalización y ortografía para dar naturalidad, como "JAJAJA" o "jaja".
    - Los mensajes deben ser cortos, directos, a veces en varias líneas.
    - No te preocupes por una gramática perfecta, refleja cómo alguien joven escribiría rápido en WhatsApp.
    - Usa @nombre para mencionar a alguien en el grupo, para hacer preguntas o responder a mensajes específicos.

    Aquí tienes la conversación reciente, no tienes que responder a estos mensajes, puedes usarlo como ejemplo, o para saber que ha pasado en la conversación:
    {historial}

    **NUEVOS MENSAJES A LOS CUALES TIENES QUE RESPONDER, SOLAMENTE A ESTOS:**
    {nuevos_mensajes_texto}
    """

    logging.info(f"{Fore.MAGENTA}\n--- Prompt enviado a Gemini ---\n{prompt}\n--- Fin del prompt ---\n")
    logging.info(f"{Fore.MAGENTA}Generando respuesta con Gemini...")

    try:
        response = model.generate_content(
            prompt,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
            },
            generation_config=genai.types.GenerationConfig(
                temperature=1,
                max_output_tokens=450
            )
        )
        return response.text
    except Exception as e:
        logging.error(f"{Fore.RED}Error al generar respuesta: {e}")
        return None

def iniciar_bot():
    driver = iniciar_navegador()
    if not driver:
        return

    try:
        # Cargar el historial completo al iniciar
        historial_completo = obtener_datos_chat(driver)
        if historial_completo:
            nombre_contacto = historial_completo[0]['conversacion']
            logging.info(f"{Fore.GREEN}Chat abierto con: {nombre_contacto}")

            # Imprimir el historial completo en la primera carga
            historial_texto_inicial = "\n".join([f"{limpiar_hora(msg['hora'])} - {asignar_color_usuario(msg['remitente'])}{msg['remitente']}{Fore.RESET}: {msg['texto']}" for msg in historial_completo])
            logging.info(f"{Fore.YELLOW}Historial completo inicial:\n{historial_texto_inicial}")

        # Crear un conjunto de identificadores únicos para los mensajes ya vistos
        mensajes_vistos = set()
        for msg in historial_completo:
            mensaje_id = (msg['hora'], msg['remitente'], msg['texto'])
            mensajes_vistos.add(mensaje_id)

        while True:
            nuevos_mensajes = []
            time.sleep(25)  # Esperar 25 segundos

            # Obtener los últimos 30 mensajes
            historial_actual = obtener_datos_chat(driver, limite=30)

            # Iterar sobre los mensajes actuales
            for msg in historial_actual:
                mensaje_id = (msg['hora'], msg['remitente'], msg['texto'])
                # Si el mensaje no ha sido visto antes, es nuevo
                if mensaje_id not in mensajes_vistos:
                    # Si el mensaje es de "Tú", agregarlo al historial pero no a nuevos_mensajes
                    if msg['remitente'] == "Tú":
                        # Comprobar si el mensaje ya existe en el historial (NUEVA COMPROBACIÓN)
                        if msg not in historial_completo:
                            historial_completo.append(msg)
                    # Si el remitente es el nombre del grupo, se considera mensaje del sistema (NUEVA COMPROBACIÓN)
                    elif msg['remitente'] == nombre_contacto:
                        # Comprobar si el mensaje ya existe en el historial (NUEVA COMPROBACIÓN)
                        if msg not in historial_completo:
                            historial_completo.append(msg)
                    else:
                        nuevos_mensajes.append(msg)
                    mensajes_vistos.add(mensaje_id)  # Agregar a mensajes vistos

            if nuevos_mensajes:
                # Imprimir el historial completo actualizado
                historial_texto_actualizado = "\n".join([f"{limpiar_hora(msg['hora'])} - {asignar_color_usuario(msg['remitente'])}{msg['remitente']}{Fore.RESET}: {msg['texto']}" for msg in historial_completo])
                logging.info(f"{Fore.YELLOW}Historial completo actualizado:\n{historial_texto_actualizado}")

                logging.info(f"{Fore.YELLOW}Nuevos mensajes detectados, enviando a Gemini...")

                # Convertir los nuevos mensajes en texto para el prompt
                ultimos_mensajes = "\n".join([f"{limpiar_hora(msg['hora'])} - {asignar_color_usuario(msg['remitente'])}{msg['remitente']}{Fore.RESET}: {msg['texto']}" for msg in nuevos_mensajes])

                # Imprimir los nuevos mensajes (para depuración)
                logging.info(f"{Fore.YELLOW}Nuevos mensajes detectados:\n{ultimos_mensajes}")

                # Generar la respuesta usando Gemini
                respuesta_gemini = generar_respuesta(historial_texto_actualizado, nuevos_mensajes, nombre_contacto)

                if respuesta_gemini:
                    # Enviar la respuesta, mensaje por mensaje
                    for mensaje in respuesta_gemini.strip().split("\n"):
                        if mensaje.strip():  # Evitar enviar mensajes vacíos
                            enviar_mensaje(driver, mensaje)
                            # Agregar la respuesta de Gemini al historial completo con la hora actual (SOLO AQUÍ)
                            hora_actual = datetime.datetime.now().strftime("%H:%M")
                            nuevo_mensaje = {
                                "conversacion": nombre_contacto,
                                "remitente": "Tú",
                                "hora": hora_actual,
                                "texto": mensaje
                            }
                            # Comprobar si el mensaje ya existe en el historial
                            if nuevo_mensaje not in historial_completo:
                                historial_completo.append(nuevo_mensaje)

    except Exception as e:
        logging.error(f"{Fore.RED}Error en el bot: {e}")
    finally:
        if driver:
            driver.quit()
            logging.info(f"{Fore.GREEN}El navegador se ha cerrado correctamente.")


if __name__ == "__main__":
    iniciar_bot()