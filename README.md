# 🎤 VozACosa

```
╦  ╦╔═╗╔═╗╔═╗╔═╗╔═╗╔═╗╔═╗
╚╗╔╝║ ║╔═╝╠═╣║  ║ ║╚═╗╠═╣
 ╚╝ ╚═╝╚═╝╩ ╩╚═╝╚═╝╚═╝╩ ╩
```

> **Voice → MIDI → Synth** | Convierte tu voz cantada a instrumentos sintetizados

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ ¿Qué es VozACosa?

VozACosa es una herramienta **SOTA** (State-of-the-Art) que:

1. 🎤 **Graba** tu voz cantando, tarareando o haciendo sonidos
2. 🎵 **Detecta** el pitch usando **CREPE** (deep learning CNN)
3. 🎹 **Cuantiza** las notas a escalas musicales
4. 🔊 **Sintetiza** con instrumentos personalizables
5. 📦 **Exporta** a MIDI, WAV y MP3

Similar a **Waves OVox** o **VocalSynth**, pero **100% Python** y **open source**.

---

## 🚀 Instalación

### Requisitos del sistema

```bash
# macOS
brew install fluidsynth portaudio

# Linux
sudo apt install fluidsynth libportaudio2
```

### Instalación Python

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/vozacosa.git
cd vozacosa

# 2. Crear entorno virtual
python3 -m venv venv

# 3. Activar entorno virtual
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# 4. Instalar dependencias
pip install -r requirements.txt
```

> ⚠️ **Importante:** Siempre activá el venv antes de usar VozACosa:
> ```bash
> source venv/bin/activate
> ```

---

## 💻 Uso Rápido

> Asegurate de tener el venv activado (`source venv/bin/activate`)

### Grabar y convertir tu voz

```bash
python cli.py record
```

Te pedirá:
1. **Escala** (major, minor, pentatonic, blues...)
2. **Nota raíz** (C, D, E...)
3. **Tolerancia** (0=estricto, 50=libre)

Luego presiona ENTER para grabar y ENTER para detener.

### Convertir un archivo de audio

```bash
python cli.py convert mi_canto.wav --scale pentatonic_major --root C
```

### Listar comandos disponibles

```bash
python cli.py --help
```

---

## 🎹 Instrumentos

VozACosa incluye **8 instrumentos** pre-configurados:

| Instrumento | Tipo | Sonido |
|-------------|------|--------|
| `synth_lead` | Wavetable | Lead synth 80s |
| `synth_pad` | Wavetable | Pad atmosférico |
| `bass_808` | Wavetable | Sub bass 808 |
| `pluck` | Karplus-Strong | Cuerda punteada |
| `piano_warm` | SoundFont | Piano acústico |
| `strings_ensemble` | SoundFont | Cuerdas orquestales |
| `flute` | SoundFont | Flauta traversa |
| `organ_rock` | Additive | Hammond B3 |

### Probar un instrumento

```bash
python cli.py test-instrument synth_lead --notes "C4,E4,G4,C5"
```

### Crear tus propios instrumentos

📖 **[Guía de Creación de Sonidos](docs/SOUNDS.md)** - Aprende a definir instrumentos personalizados en JSON

---

## 🎼 Escalas Soportadas

```bash
python cli.py scales
```

- **Mayores/Menores**: major, natural_minor, harmonic_minor, melodic_minor
- **Pentatónicas**: pentatonic_major, pentatonic_minor
- **Modos**: dorian, phrygian, lydian, mixolydian, locrian
- **Otras**: blues, chromatic, whole_tone, diminished

---

## 🔧 Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                        VOZACOSA                              │
├─────────────────┬───────────────────────────────────────────┤
│  🎤 RECORDER    │  sounddevice (grabación tiempo real)      │
├─────────────────┼───────────────────────────────────────────┤
│  🔍 ANALYZER    │  CREPE (CNN pitch detection)              │
│                 │  librosa (onset, tempo)                   │
├─────────────────┼───────────────────────────────────────────┤
│  🎼 QUANTIZER   │  15 escalas musicales                     │
│                 │  Tolerancia configurable en cents         │
├─────────────────┼───────────────────────────────────────────┤
│  🎹 SYNTH       │  Wavetable, Karplus-Strong, FluidSynth    │
│                 │  Instrumentos JSON extensibles            │
├─────────────────┼───────────────────────────────────────────┤
│  📦 EXPORTER    │  MIDI (pretty_midi), WAV, MP3             │
└─────────────────┴───────────────────────────────────────────┘
```

---

## 📁 Estructura del Proyecto

```
vozacosa/
├── vozacosa/                # Módulos core
│   ├── models.py            # Dataclasses
│   ├── scales.py            # Escalas musicales
│   ├── recorder.py          # Grabación
│   ├── analyzer.py          # CREPE pitch detection
│   ├── synthesizer.py       # Síntesis básica
│   ├── instruments.py       # Sistema de instrumentos JSON
│   └── exporter.py          # Export MIDI/WAV/MP3
├── instruments/
│   ├── instruments.json     # Definiciones de instrumentos
│   └── soundfonts/          # Archivos .sf2
├── docs/
│   └── SOUNDS.md            # Guía de creación de sonidos
├── output/                  # Archivos exportados
├── cli.py                   # Interfaz CLI
└── requirements.txt
```

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Podés:

- 🎹 Agregar nuevos instrumentos en `instruments/instruments.json`
- 🎵 Mejorar la detección de percusión
- 🌐 Crear una interfaz web
- 📝 Mejorar la documentación

---

## 📄 Licencia

MIT © 2024
