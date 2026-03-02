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
EXCEL_ENTRADA = "excel_formato.xlsx"
EXCEL_SALIDA = "resultado_excel_formato.xlsx"
USER_DATA_DIR = "./instagram_session" 

client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

async def procesar_con_groq(nombre, info_contexto, lista_posts):
    contexto_posts = "\n".join([f"- {p[:300]}" for p in lista_posts if p])
    
    prompt = f"""
    Redacta una descripción corporativa técnica y directa para un directorio profesional sobre esta cuenta de instagram.
    
    ENTIDAD: {nombre} 
    CONTEXTO (Bio/Ubicación): {info_contexto} 
    TENDENCIAS RECIENTES (Usa solo para inferir el rubro): {contexto_posts}
    
    REGLAS:
    1. LONGITUD: Estrictamente entre 300 y 400 caracteres.
    2. ESTILO: Redacción en PROSA CONTINUA. Sin listas ni etiquetas.
    3. TONO: Ejecutivo y asertivo. Empieza directo con la actividad.
    4. ENFOQUE: No te limites a los temas de los posts recientes; úsalos solo para identificar el SECTOR profesional. La descripción debe definir la IDENTIDAD GENERAL de la entidad.
    5. PROHIBICIONES: No menciones temas específicos de los posts como si fueran lo único que hace. No digas "parece ser", "en Instagram" o "recientemente".
    6. IDIOMA: Español.

    ENTREGA JSON:
    {{
      "pais": "ISO-3166-1 ALPHA-3",
      "descripcion": "Descripción generalista y profesional de 300-400 caracteres aquí."
    }}
    """
    try:
        response = client.chat.completions.create(
            # model="llama-3.1-8b-instant"
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Eres un analista de mercado experto. Tu misión es sintetizar la identidad de una entidad basándote en su presencia digital, evitando caer en descripciones anecdóticas de sus últimas publicaciones."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        texto = response.choices[0].message.content.strip()
        inicio, fin = texto.find('{'), texto.rfind('}') + 1
        res = json.loads(texto[inicio:fin])
        return res
    except:
        return {"pais": "POR DEFINIR", "descripcion": "Error en síntesis de información"}

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

                # 4. MUESTREO DE 4 POSTS (Selector Universal de Instagram)
                await page.mouse.wheel(0, 500)
                await page.wait_for_timeout(2000)
                
                captions = []
                fechas_encontradas = []
                
                # Este selector es la clave: busca cualquier link que sea un post, un reel o video
                # El "singular" /reel/ era lo que nos faltaba
                posts_selector = "a[href*='/p/'], a[href*='/reel/']"
                posts_links = page.locator(posts_selector)
                
                # IMPORTANTE: Instagram a veces pone links ocultos, filtramos por los que tienen imagen
                imagenes_posts = posts_links.locator("img")
                count = await posts_links.count()

                if count == 0:
                    df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "SI", "Sin publicaciones visibles"
                else:
                    # A. Extraer textos vía ALT (Rápido y sin clics)
                    for j in range(min(4, count)):
                        try:
                            alt = await imagenes_posts.nth(j).get_attribute("alt")
                            if alt: captions.append(alt)
                        except: pass

                    # B. Verificar fechas (Entrando con cuidado)
                    cuenta_activa = False
                    for j in range(min(4, count)):
                        try:
                            # 1. Hacemos scroll al post para que Instagram lo "active"
                            target_post = posts_links.nth(j)
                            await target_post.scroll_into_view_if_needed()
                            await page.wait_for_timeout(500)
                            
                            # 2. Clic para abrir el diálogo
                            await target_post.click()
                            
                            # 3. Esperar que el tag 'time' aparezca
                            # Si es un REEL, a veces el diálogo tarda más, subimos a 8s
                            await page.wait_for_selector("time", timeout=5000)
                            
                            elemento_tiempo = page.locator("time").first
                            f_iso = await elemento_tiempo.get_attribute("datetime")
                            
                            if f_iso:
                                fecha_p = datetime.fromisoformat(f_iso.split('T')[0])
                                fechas_encontradas.append(fecha_p)
                                
                                # Cerrar diálogo
                                await page.keyboard.press("Escape")
                                await page.wait_for_timeout(800)

                                if fecha_p >= FECHA_LIMITE:
                                    cuenta_activa = True
                                    break 
                        except Exception as e:
                            # Si falla, cerramos lo que haya abierto y seguimos
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(500)
                            continue

                    # 5. DECISIÓN FINAL
                    if not cuenta_activa:
                        txt_f = f"Inactiva (Reciente: {max(fechas_encontradas).date()})" if fechas_encontradas else "Inactiva (Sin fechas leídas)"
                        df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "SI", txt_f
                    else:
                        df.at[i, 'eliminar'], df.at[i, 'observaciones'] = "NO", ""
                        info_ctx = f"PAÍS: {pais_oficial} | BIO: {bio_txt} | UBI: {ubi_bio}"
                        res_ia = await procesar_con_groq(row['name'], info_ctx, captions)
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