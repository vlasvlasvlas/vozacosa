"""
Data models for VozACosa
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import numpy as np


class NoteType(Enum):
    """Tipo de nota detectada"""
    MELODIC = "melodic"       # Nota tonal (cantada)
    PERCUSSIVE = "percussive" # Transiente percusivo


class PercussionType(Enum):
    """Tipos de percusión vocal detectados"""
    KICK = "kick"       # 'tu', 'dum' - baja frecuencia
    SNARE = "snare"     # 'pa', 'ka' - ruido blanco
    HIHAT = "hihat"     # 'ts', 'ch' - alta frecuencia
    UNKNOWN = "unknown"


@dataclass
class Note:
    """
    Representa una nota detectada del audio.
    
    Attributes:
        pitch_hz: Frecuencia detectada en Hz (None para percusión)
        midi_note: Nota MIDI cuantizada (0-127)
        start_time: Tiempo de inicio en segundos
        duration: Duración en segundos
        velocity: Velocidad/volumen MIDI (0-127)
        confidence: Confianza de la detección (0.0-1.0)
        note_type: Tipo de nota (melódica o percusiva)
        percussion_type: Tipo de percusión si aplica
        original_pitch_hz: Pitch original antes de cuantizar
    """
    pitch_hz: Optional[float]
    midi_note: int
    start_time: float
    duration: float
    velocity: int = 100
    confidence: float = 1.0
    note_type: NoteType = NoteType.MELODIC
    percussion_type: Optional[PercussionType] = None
    original_pitch_hz: Optional[float] = None
    
    def cents_deviation(self) -> float:
        """Calcula la desviación en cents de la nota cuantizada"""
        if self.original_pitch_hz is None or self.pitch_hz is None:
            return 0.0
        # 1 semitono = 100 cents
        return 1200 * np.log2(self.original_pitch_hz / self.pitch_hz)


@dataclass
class Recording:
    """
    Representa una grabación de audio.
    
    Attributes:
        audio: Array de samples de audio
        sample_rate: Frecuencia de muestreo
        duration: Duración en segundos
        filepath: Ruta al archivo guardado (si existe)
    """
    audio: np.ndarray
    sample_rate: int
    duration: float
    filepath: Optional[str] = None
    
    @property
    def num_samples(self) -> int:
        return len(self.audio)


@dataclass
class AnalysisResult:
    """
    Resultado del análisis de un audio.
    
    Attributes:
        notes: Lista de notas detectadas
        tempo: BPM estimado
        is_percussive: True si el audio es principalmente percusivo
        pitch_track: Array de pitches detectados por frame
        confidence_track: Array de confianzas por frame
        onset_times: Tiempos de onset detectados
    """
    notes: List[Note] = field(default_factory=list)
    tempo: Optional[float] = None
    is_percussive: bool = False
    pitch_track: Optional[np.ndarray] = None
    confidence_track: Optional[np.ndarray] = None
    onset_times: Optional[np.ndarray] = None
    
    @property
    def num_notes(self) -> int:
        return len(self.notes)
    
    @property
    def total_duration(self) -> float:
        if not self.notes:
            return 0.0
        last_note = max(self.notes, key=lambda n: n.start_time + n.duration)
        return last_note.start_time + last_note.duration


@dataclass 
class QuantizationConfig:
    """
    Configuración de cuantización.
    
    Attributes:
        tolerance_cents: Tolerancia en cents para redondear (0-50)
            0 = fuerza todo a la nota más cercana
            50 = permite hasta medio semitono de desviación
        scale: Nombre de la escala a usar (None = cromática)
        root_note: Nota raíz de la escala (ej: 'C', 'D#')
        snap_to_scale: Si True, solo permite notas de la escala
    """
    tolerance_cents: int = 25
    scale: Optional[str] = None  # 'major', 'minor', 'pentatonic', etc.
    root_note: str = 'C'
    snap_to_scale: bool = True


@dataclass
class SynthConfig:
    """
    Configuración del sintetizador.
    
    Attributes:
        soundfont_path: Ruta al archivo .sf2
        preset: Preset/instrumento a usar
        gain: Ganancia del sintetizador
    """
    soundfont_path: Optional[str] = None
    preset: int = 0  # 0 = Piano
    bank: int = 0
    gain: float = 1.0


@dataclass
class ExportConfig:
    """
    Configuración de exportación.
    
    Attributes:
        output_dir: Directorio de salida
        export_midi: Exportar archivo MIDI
        export_wav: Exportar audio WAV
        export_mp3: Exportar audio MP3
        save_original: Guardar audio original
    """
    output_dir: str = "output"
    export_midi: bool = True
    export_wav: bool = True
    export_mp3: bool = True
    save_original: bool = True
