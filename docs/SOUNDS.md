# 🎤➡️🎹 Guía de Creación de Sonidos

```
╔═╗╔═╗╦ ╦╔╗╔╔╦╗╔═╗  ╔═╗╦ ╦╔═╗╔╦╗╔═╗╔╦╗
╚═╗║ ║║ ║║║║ ║║╚═╗  ║  ║ ║╚═╗ ║ ║ ║║║║
╚═╝╚═╝╚═╝╝╚╝═╩╝╚═╝  ╚═╝╚═╝╚═╝ ╩ ╚═╝╩ ╩
```

> Aprende a crear instrumentos personalizados para VozACosa

---

## 📁 Archivo de Instrumentos

Todos los instrumentos se definen en:

```
instruments/instruments.json
```

Este archivo JSON es **abierto y extensible**. Podés agregar tus propios instrumentos!

---

## 🎹 Estructura de un Instrumento

### Ejemplo básico (Wavetable)

```json
{
  "mi_synth": {
    "name": "Mi Synth Personalizado",
    "category": "synth",
    "type": "wavetable",
    "waveform": "sawtooth",
    "envelope": {
      "attack": 0.01,
      "decay": 0.1,
      "sustain": 0.7,
      "release": 0.3
    },
    "description": "Mi primer sintetizador"
  }
}
```

### Campos obligatorios

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | string | Nombre para mostrar |
| `category` | string | keyboard, synth, bass, strings, winds, drums |
| `type` | string | wavetable, soundfont, karplus_strong, additive |

---

## 🎛️ Tipos de Síntesis

### 1. Wavetable (más simple)

```json
{
  "type": "wavetable",
  "waveform": "sine",  // sine, square, sawtooth, triangle
  "envelope": {
    "attack": 0.01,    // segundos para subir
    "decay": 0.1,      // segundos para bajar a sustain
    "sustain": 0.7,    // nivel durante nota (0-1)
    "release": 0.3     // segundos para apagar
  }
}
```

**Waveforms disponibles:**
- `sine` - Suave, sin armónicos
- `square` - Hueco, tipo 8-bit
- `sawtooth` - Brillante, tipo lead
- `triangle` - Suave con algo de brillo

---

### 2. Karplus-Strong (cuerdas punteadas)

```json
{
  "type": "karplus_strong",
  "damping": 0.5,       // 0-1 (más alto = más corto)
  "brightness": 0.7     // 0-1 (más alto = más brillante)
}
```

Ideal para: guitarras, arpas, pizzicato

---

### 3. SoundFont (instrumentos reales)

```json
{
  "type": "soundfont",
  "soundfont": "GeneralUser_GS.sf2",
  "bank": 0,
  "preset": 0
}
```

**Presets comunes (General MIDI):**
| Preset | Instrumento |
|--------|-------------|
| 0 | Piano |
| 25 | Guitarra acústica |
| 33 | Bajo eléctrico |
| 40 | Violín |
| 48 | Cuerdas |
| 56 | Trompeta |
| 73 | Flauta |

---

### 4. Additive (órganos)

```json
{
  "type": "additive",
  "drawbars": [8, 8, 8, 0, 0, 0, 0, 0, 0],
  "vibrato": {
    "enabled": true,
    "depth": 0.3,
    "rate": 6.0
  }
}
```

---

## 🥁 Drum Kits

```json
{
  "drum_kits": {
    "mi_kit": {
      "name": "Mi Batería",
      "type": "soundfont",
      "soundfont": "GeneralUser_GS.sf2",
      "bank": 128,
      "preset": 0,
      "mapping": {
        "kick": 36,
        "snare": 38,
        "hihat_closed": 42,
        "hihat_open": 46
      }
    }
  }
}
```

---

## 🎨 Ejemplos Completos

### Lead Retro 80s

```json
{
  "lead_80s": {
    "name": "Lead Retro 80s",
    "category": "synth",
    "type": "wavetable",
    "waveform": "sawtooth",
    "envelope": {
      "attack": 0.005,
      "decay": 0.2,
      "sustain": 0.6,
      "release": 0.4
    },
    "description": "Lead synth estilo Stranger Things"
  }
}
```

### Bass Sub Profundo

```json
{
  "deep_sub": {
    "name": "Deep Sub Bass",
    "category": "bass",
    "type": "wavetable",
    "waveform": "sine",
    "envelope": {
      "attack": 0.001,
      "decay": 0.5,
      "sustain": 0.0,
      "release": 0.8
    },
    "description": "Sub bass profundo tipo trap"
  }
}
```

### Guitarra Acústica

```json
{
  "acoustic_guitar": {
    "name": "Guitarra Acústica",
    "category": "strings",
    "type": "karplus_strong",
    "damping": 0.3,
    "brightness": 0.8,
    "description": "Cuerda de guitarra punteada"
  }
}
```

---

## 🧪 Probar tu Instrumento

Después de agregar tu instrumento al JSON:

```bash
# Ver que aparezca en la lista
python cli.py instruments

# Probarlo con notas
python cli.py test-instrument mi_synth --notes "C4,E4,G4,C5"

# Escuchar el resultado
open output/test.wav  # macOS
```

---

## 💡 Tips

1. **Empieza simple** - Usa wavetable con sine primero
2. **Experimenta con ADSR** - El envelope define el carácter del sonido
3. **Copia y modifica** - Usa los instrumentos existentes como base
4. **Nombres descriptivos** - Usa IDs en snake_case sin espacios

---

## 📚 Recursos

- [MIDI Preset Numbers](https://en.wikipedia.org/wiki/General_MIDI#Program_change_events)
- [ADSR Envelope Explained](https://en.wikipedia.org/wiki/ADSR_envelope)
- [SoundFonts Gratis](https://musical-artifacts.com/artifacts?formats=sf2)

---

[← Volver al README principal](../README.md)
