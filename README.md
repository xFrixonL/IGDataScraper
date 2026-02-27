# IGDataScraper 🚀

IGDataScraper es una potente herramienta de automatización diseñada para extraer, filtrar y enriquecer información de perfiles comerciales de Instagram. Utiliza **Playwright** para una navegación robusta y **Llama 3.3 (vía Groq)** para transformar datos crudos en descripciones corporativas asertivas y profesionales.

## ✨ Características Principales

* **Detección de Ubicación Oficial:** Obtiene el país configurado en la transparencia de la cuenta mediante clics automatizados.
* **Filtro de Inactividad:** Analiza las fechas de las últimas publicaciones para descartar cuentas obsoletas (Fecha límite ajustable).
* **IA de Redacción Corporativa:** Genera reseñas de 300-400 caracteres en prosa continua, eliminando muletillas técnicas de redes sociales.
* **Resiliencia:** Manejo de sesiones persistentes para evitar bloqueos y soporte para cuentas privadas o no encontradas.
* **Estimación de Tiempo Real:** Proyecta el tiempo restante de finalización basado en la velocidad promedio de procesamiento.
* **Auto-guardado:** Exportación incremental a Excel cada 3 registros para asegurar el progreso.

## 🛠️ Requisitos Previos

- Python 3.10 o superior.
- Una API Key de [Groq Cloud](https://console.groq.com/).
- Una sesión activa de Instagram (opcional, para evitar logins constantes).

## 🚀 Instalación

1. **Clona este repositorio:**
   ```
   git clone https://github.com/xFrixonL/IGDataScraper.git
   cd IGDataScraper
    ```

2. **Instala las dependencias necesarias:**
    ```
    pip install -r requirements.txt
    ```

3. **Configura tus credenciales:**
Crea un archivo llamado .env en la carpeta raíz y añade tu clave:
    ```
    GROQ_API_KEY=tu_clave_aqui_gsk_...
    ```

## 📊 Uso
1. Prepara tu archivo de entrada llamado archivo.xlsx con las columnas url y name.
2. Ejecuta el script principal:
    ```
    python main.py
    ```
3. Iniciar sesión en Instagram (la primera vez, luego se usarán las cookies)
3. El script generará un archivo resultado_archivo.xlsx con las columnas enriquecidas: pais, eliminar, descripción y observaciones.

## 📋 Estructura de Archivos
```
IGDataScraper/
│
├── main.py
├── excel_formato.xlsx
├── .env
├── instagram_session/
├── .gitignore
└── requirements.txt
```

- **main.py:** El núcleo del automatismo.
- **.env:** Variables de entorno (ignorado por Git).
- **instagram_session/:** Almacena cookies y datos de navegación (ignorado por Git).
- **excel_formato.xlsx:** Plantilla de ejemplo para el usuario.
- **.gitignore:** Configuración de exclusión de archivos sensibles y temporales.

## ⚠️ Notas Importantes
- Se recomienda usar una cuenta de Instagram secundaria para evitar posibles restricciones.

- Mantén tu archivo .env fuera del control de versiones.

- La velocidad del scraping puede depender de tu conexión y de posibles límites de Instagram.