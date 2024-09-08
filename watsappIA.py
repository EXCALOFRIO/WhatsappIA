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

# Inicializa colorama
init(autoreset=True)

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicializa el modelo Gemini Flash directamente
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('models/gemini-1.5-flash-001')


def filtrar_caracteres_no_bmp(texto):
    return "".join(c for c in texto if ord(c) < 0x10000)


def iniciar_navegador():
    try:
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        logging.info(f"{Fore.GREEN}Conectado a la instancia de Chrome ya abierta...")
        return driver
    except Exception as e:
        logging.error(f"{Fore.RED}Error al iniciar el navegador: {e}")
        return None


def obtener_datos_chat(driver):
    try:
        logging.info(f"{Fore.YELLOW}Obteniendo datos del chat...")

        # Esperar a que se cargue al menos un mensaje
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='row']"))
        )

        mensajes = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
        datos_chat = []

        # Obtener el nombre de la conversación
        try:
            nombre_conversacion = driver.find_element(By.CSS_SELECTOR, "header ._amig ._ao3e").text
        except:
            nombre_conversacion = "Nombre no disponible"

        ultimo_remitente = None  # Variable para almacenar el último remitente conocido

        for mensaje in mensajes:
            # Determinar el tipo de mensaje (usando aria-label y data-id como respaldo)
            try:
                remitente_label = mensaje.find_element(By.CSS_SELECTOR, "div._amk6._amlo span[aria-label]").get_attribute("aria-label")
                if remitente_label and remitente_label.startswith("Tú:"):
                    remitente = "Tú"
                    ultimo_remitente = remitente  # Actualizar el último remitente
                else:
                    # Intentar obtener el nombre del remitente del aria-label (para chats grupales)
                    remitente = remitente_label.split(":")[0] if ":" in remitente_label else None

                    # Si no se puede obtener del aria-label, intentar con la clase _ahxt
                    if remitente is None:
                        remitente = mensaje.find_element(By.CSS_SELECTOR, "span._ahxt").text
                    
                    ultimo_remitente = remitente  # Actualizar el último remitente

            except:
                # Si no se encuentra el aria-label ni la clase _ahxt, usar data-id como último recurso
                data_id = mensaje.get_attribute("data-id")
                if data_id and data_id.startswith("true_"):
                    remitente = "Tú"
                    ultimo_remitente = remitente  # Actualizar el último remitente
                else:
                    # Si no se puede determinar el remitente, usar el último remitente conocido
                    remitente = ultimo_remitente if ultimo_remitente is not None else nombre_conversacion

            # Extraer la hora
            try:
                hora = mensaje.find_element(By.CSS_SELECTOR, "div[role='row'] span.x1rg5ohu[dir='auto']").text
            except:
                try:
                    texto_pre_plain = mensaje.find_element(By.CSS_SELECTOR, "div.copyable-text").get_attribute(
                        "data-pre-plain-text")
                    hora = texto_pre_plain.split("[")[1].split("]")[0]
                except:
                    hora = "Hora no disponible"

            # Extraer el texto
            try:
                texto = mensaje.find_element(By.CSS_SELECTOR, "span.selectable-text").text
            except:
                texto = "Mensaje sin texto"

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
def enviar_mensaje(driver, mensaje):
    try:
        mensaje_filtrado = filtrar_caracteres_no_bmp(mensaje)
        input_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//footer//div[@contenteditable='true']"))
        )
        input_box.send_keys(mensaje_filtrado + Keys.ENTER)
        logging.info(f"{Fore.CYAN}Mensaje enviado: {mensaje_filtrado}")
    except Exception as e:
        logging.error(f"{Fore.RED}Error al enviar mensaje: {e}")


def imprimir_historial(datos_chat):
    logging.info("\n--- Historial del chat ---")
    for mensaje in datos_chat:
        color = Fore.CYAN if mensaje['remitente'] == "Tú" else Fore.GREEN
        logging.info(f"{color}{mensaje['hora']} - {mensaje['remitente']}: {mensaje['texto']}")
    logging.info("--- Fin del historial ---\n")


def generar_respuesta(historial, nuevo_mensaje, nombre_contacto):
    prompt = f"""
    Estás chateando con {nombre_contacto} en WhatsApp. 
    Aquí está el historial de la conversación:
    {historial}

    {nombre_contacto}: {nuevo_mensaje}

    Responde solo con el mensaje que enviarías a {nombre_contacto} como respuesta a su último mensaje.
    No incluyas nada más en tu respuesta. 
    Puedes continuar la conversación actual o introducir un nuevo tema que hayais hablado antes, o relacionado con algo de lo que se está hablando.
    Si no encuentras un tema relevante en el historial, puedes hacer una pregunta relacionada con la conversación.
    La forma en la que respondas tiene que ser de la misma forma con la que he respondido anteriormente, con eso me refiero a que si he respondido con un emoji, usando alguna jerga o alguna forma de hablar en concreto, tienes que hacer lo mismo, para que el mensaje parezca completamente escrito por mí, así que basate en los mensajes que salen etiquetados como Tú.
    Si quieres hacer referencia a alguien, si es una conversacion de grupo, puedes poner @nombre_persona y asi le haces referencia.
    Si no es necesario contestar, mandame un mensaje vacío.
    """
    logging.info(f"{Fore.MAGENTA}\n--- Prompt enviado a Gemini ---\n{prompt}\n--- Fin del prompt ---\n")
    logging.info(f"{Fore.MAGENTA}Generando respuesta con Gemini...")

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=350,
                top_p=1,
                top_k=1,
            )
        )
        return response.text
    except Exception as e:
        logging.error(f"{Fore.RED}Error al generar respuesta: {e}")
        return None


def calcular_latencia_por_palabra(mensaje):
    palabras = mensaje.split()
    latencia = 0.2 * len(palabras)
    logging.info(f"{Fore.YELLOW}Añadiendo latencia de {latencia} segundos antes de enviar el mensaje.")
    time.sleep(latencia)


def comparar_mensajes(historial_anterior, historial_actual, limite=50):
    if len(historial_actual) > len(historial_anterior):
        start_index = max(0, len(historial_actual) - limite)
        nuevos_mensajes = historial_actual[start_index:]

        for i in range(len(nuevos_mensajes)):
            if i >= len(historial_anterior):
                return nuevos_mensajes[i:]
            if nuevos_mensajes[i] != historial_anterior[start_index + i]:
                return nuevos_mensajes[i:]

    return []


def iniciar_bot():
    driver = iniciar_navegador()
    if not driver:
        return

    try:
        logging.info(f"{Fore.YELLOW}WhatsApp Web cargado. Obteniendo datos del chat...")

        while True:
            historial_anterior = obtener_datos_chat(driver)

            if historial_anterior:
                nombre_contacto = historial_anterior[0]['conversacion'] if historial_anterior else "Nombre no disponible"
                logging.info(f"{Fore.GREEN}Chat abierto con: {nombre_contacto}")
                imprimir_historial(historial_anterior)

                mensajes_enviados = []  # Lista para almacenar los mensajes enviados por el bot

                while True:
                    time.sleep(10)  # Esperar 10 segundos

                    historial_actual = obtener_datos_chat(driver)

                    nuevos_mensajes = comparar_mensajes(historial_anterior, historial_actual)

                    if nuevos_mensajes:
                        for mensaje_actual in nuevos_mensajes:
                            logging.info(f"{Fore.GREEN}Nuevo mensaje recibido: {mensaje_actual['texto']}")

                            # Generar la respuesta con Gemini
                            historial_texto = ""
                            for msg in historial_anterior:
                                historial_texto += f"{msg['remitente']}: {msg['texto']}\n"
                            respuesta_gemini = generar_respuesta(historial_texto, mensaje_actual['texto'],
                                                                    nombre_contacto)

                            # Evitar respuestas repetitivas
                            if respuesta_gemini and respuesta_gemini.strip() and respuesta_gemini not in mensajes_enviados:
                                calcular_latencia_por_palabra(respuesta_gemini)
                                enviar_mensaje(driver, respuesta_gemini)
                                mensajes_enviados.append(respuesta_gemini)

                    historial_anterior = historial_actual

    except Exception as e:
        logging.error(f"{Fore.RED}Error inesperado en el bot: {e}")


# Iniciar el bot
iniciar_bot()