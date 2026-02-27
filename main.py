import json
import asyncio
import pandas as pd
import random
import os
from dotenv import load_dotenv
from datetime import datetime
from openai import OpenAI
from playwright.async_api import async_playwright

# --- CONFIGURACIÓN ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Verificación de seguridad básica
if not GROQ_API_KEY:
    raise ValueError("¡Error! No se encontró GROQ_API_KEY en el archivo .env")
EXCEL_ENTRADA = "archivo.xlsx"
EXCEL_SALIDA = "resultado_archivo.xlsx"
USER_DATA_DIR = "./instagram_session" 

client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

async def procesar_con_groq(nombre, info_contexto, lista_posts):
    contexto_posts = "\n".join([f"- {p[:300]}" for p in lista_posts if p])
    
    prompt = f"""
    Redacta una descripción corporativa técnica y directa para un directorio profesional de esta cuenta de Instagram.
    
    ENTIDAD: {nombre} 
    CONTEXTO: {info_contexto} 
    CONTENIDO ANALIZADO: {contexto_posts}
    
    REGLAS:
    1. LONGITUD: Estrictamente entre 300 y 400 caracteres.
    2. ESTILO: Redacción en PROSA CONTINUA (un solo párrafo fluido). No uses listas, ni etiquetas como 'Sector:' o 'Servicios:'.
    3. TONO: Empieza directo con la actividad de la entidad. Usa un lenguaje ejecutivo y asertivo.
    4. PROHIBICIONES: No digas "parece ser", "esta cuenta", "en Instagram", "según sus posts", "bio" o "links". 
    5. CONTENIDO: Define el sector, servicios y enfoque estratégico integrados en el texto.
    6. IDIOMA: Español.

    ENTREGA JSON:
    {{
      "pais": "ISO-3166-1 ALPHA-3",
      "descripcion": "Descripción asertiva de 250 a 300 caracteres aquí."
    }}
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Eres un redactor de élite para revistas de negocios. Tu estilo es sobrio, asertivo y redactas párrafos profesionales sin usar esquemas de puntos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        texto = response.choices[0].message.content.strip()
        inicio, fin = texto.find('{'), texto.rfind('}') + 1
        res = json.loads(texto[inicio:fin])
        
        return res
    except:
        return {"pais": "POR DEFINIR", "descripcion": "POR DEFINIR"}

async def ejecutar():

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR, headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        df = pd.read_excel(EXCEL_ENTRADA)
        for col in ['pais', 'eliminar', 'descripción', 'observaciones']:
            df[col] = df[col].astype(object)

        FECHA_LIMITE = datetime(2026, 2, 1)

        for i, row in df.iterrows():
            ahora = datetime.now().strftime("%H:%M:%S")
            url = str(row['url']).strip()
            print(f"[{ahora}] [{i+1}/{len(df)}] Analizando: {url}")
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)

                # 1. VERIFICAR SI EXISTE O ES PRIVADA
                if await page.get_by_text("Esta página no está disponible").is_visible():
                    df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "SI", "No encontrada"
                    await page.close()
                    continue
                
                if await page.get_by_text("Esta cuenta es privada").is_visible():
                    df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "SI", "Cuenta Privada"
                    await page.close()
                    continue

                # 2. EXTRAER PAÍS OFICIAL (Clic en el Username/Header)
                pais_oficial = "No disponible"
                try:
                    # Seleccionamos el h2 que contiene el nombre de usuario
                    # Usamos un selector que evite el círculo de la historia
                    username_header = page.locator("header h2").first
                    
                    if await username_header.is_visible():
                        await username_header.click()
                        # Esperamos a que aparezca el diálogo de "Información sobre esta cuenta"
                        # Usamos el texto del Navbar que me pasaste como señal de que abrió
                        try:
                            await page.wait_for_selector("text='Información sobre esta cuenta'", timeout=5000)
                            
                            # Buscamos específicamente el bloque de "Ubicación de la cuenta"
                            # Tu HTML muestra que el país está en un span dentro del mismo Flexbox
                            nodo_ubicacion = page.get_by_text("Ubicación de la cuenta")
                            if await nodo_ubicacion.is_visible():
                                # Subimos al contenedor padre que tiene el título y el país
                                # y extraemos todo el texto para limpiarlo
                                bloque_texto = await page.locator("div[data-bloks-name='bk.components.Flexbox']").filter(has_text="Ubicación de la cuenta").last.inner_text()
                                
                                # Limpieza: Si el bloque dice "Ubicación de la cuentaBrasil", quitamos el título
                                pais_oficial = bloque_texto.replace("Ubicación de la cuenta", "").strip()
                                print(f"   ✓ País detectado: {pais_oficial}")
                            
                            # Cerramos el diálogo con la tecla Escape o el botón Cerrar
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(500)
                        except:
                            print("   ! El diálogo de información no se abrió o tardó mucho.")
                except Exception as e:
                    print(f"   ! Error al intentar abrir info de cuenta: {e}")

                # 3. EXTRAER BIO Y UBICACIÓN DE BIO (Respaldo)
                bio_txt = ""
                try: bio_txt = await page.locator("span._ap3a._aaco._aacu._aacx._aad7._aade").first.inner_text()
                except: bio_txt = "Sin bio"
                
                ubi_bio = ""
                try: ubi_bio = await page.locator("h1._ap3a._aaco._aacu._aacy._aad6._aade").inner_text()
                except: ubi_bio = ""

                # 4. MUESTREO DE 4 POSTS (Para saltar PINS)
                await page.mouse.wheel(0, 500)
                await page.wait_for_timeout(1500)
                
                fechas_encontradas = []
                captions = []
                posts_locators = page.locator("a[href*='/p/']")
                total_posts = await posts_locators.count()

                if total_posts == 0:
                    df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "SI", "Sin publicaciones"
                else:
                    for j in range(min(4, total_posts)):
                        try:
                            await posts_locators.nth(j).click()
                            await page.wait_for_selector("time", timeout=5000)
                            f_iso = await page.locator("time").first.get_attribute("datetime")
                            fechas_encontradas.append(datetime.fromisoformat(f_iso.split('T')[0]))
                            
                            cap = await page.locator("div[role='dialog'] span").first.inner_text()
                            captions.append(cap)
                            
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(500)
                        except: continue

                    # 5. DECISIÓN FINAL
                    if not fechas_encontradas:
                        df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "SI", "Error lectura posts"
                    else:
                        fecha_mas_joven = max(fechas_encontradas)
                        if fecha_mas_joven < FECHA_LIMITE:
                            df.at[i, 'eliminar'] = "SI"
                            df.at[i, 'observaciones'] = f"Inactiva (Reciente: {fecha_mas_joven.date()})"
                        else:
                            df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "NO", ""
                            # Enviamos todo el contexto a la IA
                            info_contexto = f"PAÍS OFICIAL: {pais_oficial} | BIO: {bio_txt} | UBI BIO: {ubi_bio}"
                            res_ia = await procesar_con_groq(row['name'], info_contexto, captions)
                            
                            df.at[i, 'pais'] = res_ia.get('pais', 'POR DEFINIR')
                            df.at[i, 'descripción'] = res_ia.get('descripcion', bio_txt)

            except Exception as e:
                df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "SI", "Error carga"
                print(f"Error: {e}")

            await page.close()
            await asyncio.sleep(random.randint(3, 6))
            if i % 3 == 0: df.to_excel(EXCEL_SALIDA, index=False)

        await context.close()
        df.to_excel(EXCEL_SALIDA, index=False)
        print(f"\nFinalizado con éxito.")

if __name__ == "__main__":
    asyncio.run(ejecutar())