# 🎤 VOZ-A-COSA

```
╦  ╦╔═╗╔═╗   ╔═╗   ╔═╗╔═╗╔═╗╔═╗
╚╗╔╝║ ║╔═╝───╠═╣───║  ║ ║╚═╗╠═╣
 ╚╝ ╚═╝╚═╝   ╩ ╩   ╚═╝╚═╝╚═╝╩ ╩
```

> **Voice → MIDI → Synth** | Transforma tu voz en instrumentos musicales con IA.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](LICENSE)

---

## ✨ ¿Qué es VOZ-A-COSA?

**VOZ-A-COSA** es una herramienta creativa que utiliza inteligencia artificial (SOTA) para convertir melodías cantadas, tarareadas o silbadas en música sintetizada de alta calidad.

A diferencia de los conversores de audio tradicionales, utiliza **CREPE** (un modelo de deep learning) para una detección de pitch ultra-precisa, permitiendo capturar matices expresivos como vibrato y glissando.

### 🌟 Novedades v1.0

*   **GUI Moderna:** Interfaz web oscura, intuitiva y paso a paso.
*   **Visualizador de Afinación:** Gráfico interactivo tipo "Piano Roll" para ver tu voz sobre la escala musical.
*   **Corrección Post-Grabación:** ¿La IA se equivocó de escala? Escuchá referencias, ajustá la nota raíz y re-procesa al instante sin volver a grabar.
*   **Gestión de Sesiones:** Graba múltiples tomas, guárdalas automáticamente, recupéralas o elimínalas cuando quieras.
*   **Previews de Instrumentos:** Escuchá cómo suena cada sintetizador antes de aplicarlo.

---

## 🚀 Flujo de Trabajo

1.  **🎤 Grabar:**
    *   **Modo Simple:** Afinación automática y filtro de ruido listos para usar.
    *   **Modo Avanzado:** Control total sobre el umbral de ruido (gate) y la agresividad de la afinación (tune amount).
2.  **🧠 Analizar & Ajustar:**
    *   El sistema detecta las notas y la escala probable.
    *   **Visualizá** tu curva de voz sobre la rejilla musical.
    *   **Escuchá** tonos de referencia ("Do Mayor", "La Menor", etc.) para asegurar la armonía correcta.
    *   **Re-procesá** si es necesario con un solo clic.
3.  **🎹 Sintetizar:**
    *   Elegí entre 8 instrumentos (Pianos, Bajos, Sínteis, Vientos).
    *   ¡Exportá a **MIDI**, **WAV** y **MP3**!

---

## 🛠️ Instalación

### Requisitos del sistema

Necesitarás `fluidsynth` y `portaudio` para el manejo de audio en tiempo real.

**macOS:**
```bash
brew install fluidsynth portaudio
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install fluidsynth libportaudio2
```

### Instalación del proyecto

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/vozacosa.git
cd vozacosa

# 2. Crear entorno virtual (Recomendado)
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## 💻 Uso

La forma recomendada de usar VOZ-A-COSA es a través de su interfaz web.

```bash
# Asegurate de tener el entorno activado
source venv/bin/activate

# Iniciar el servidor
python server.py
```

El navegador se abrirá automáticamente en `http://localhost:5001`.

---

## 🎹 Instrumentos Incluidos

| Instrumento | Categoría | Descripción |
|-------------|-----------|-------------|
| **Piano Cálido** | Acoustic | Piano suave ideal para acordes y melodías emotivas. |
| **Synth Lead** | Electronic | Sintetizador ochentero penetrante para solos. |
| **Bass 808** | Bass | Sub-bajo profundo estilo Trap/Hip-Hop. |
| **Synth Pad** | Atmospheric | Sonido ambiental y espacial. |
| **Pluck** | Plucked | Sonido percusivo tipo cuerda punteada. |
| **Cuerdas** | Orchestral | Ensamble de violines y cellos. |
| **Flauta** | Wind | Flauta dulce melódica. |
| **Órgano Rock** | Keyboards | Clásico sonido Hammond B3 con distorsión. |

---

## 📁 Estructura del Proyecto

```
vozacosa/
├── app.py              # Versión CLI (Terminal)
├── server.py           # Servidor Flask (Backend Web)
├── web/                # Frontend
│   └── index.html      # Aplicación Single Page (HTML/JS/CSS)
├── vozacosa/           # Núcleo Python
│   ├── analyzer.py     # Motor de detección (CREPE)
│   ├── synthesizer.py  # Motores de audio
│   ├── instruments.py  # Gestión de presets
│   └── session.py      # Gestor de archivos y estado
├── instruments/        # Definiciones JSON + SoundFonts (.sf2)
├── sessions/           # 💾 Tus grabaciones se guardan aquí
└── output/             # Exportaciones temporales
```

---

## 🤝 Contribuir

¡Tus ideas son bienvenidas!

1.  Haz un Fork del proyecto.
2.  Crea una rama (`git checkout -b feature/nueva-idea`).
3.  Commit tus cambios (`git commit -m 'Agregué visualizador 3D'`).
4.  Push a la rama (`git push origin feature/nueva-idea`).
5.  Abre un Pull Request.

---

## 📄 Licencia

[CC BY-SA 4.0](LICENSE) — © Vladimiro Bellini ([vlasvlasvlas](https://github.com/vlasvlasvlas)). Ver [LICENSE](LICENSE) para los términos completos.

© 2026 VOZ-A-COSA Team
## License

[CC BY-SA 4.0](LICENSE) — © Vladimiro Bellini ([vlasvlasvlas](https://github.com/vlasvlasvlas)). Ver [LICENSE](LICENSE) para los términos completos.
