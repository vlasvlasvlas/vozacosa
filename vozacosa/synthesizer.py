"""
MIDI and audio synthesizer using FluidSynth.
Renders MIDI notes to audio using SoundFonts.
"""
import os
from typing import List, Optional
import numpy as np

from .models import Note, NoteType, SynthConfig, AnalysisResult


class Synthesizer:
    """
    Sintetizador basado en FluidSynth.
    Renderiza notas MIDI a audio usando SoundFonts.
    """
    
    # SoundFont por defecto (General MIDI)
    DEFAULT_SOUNDFONT_URLS = [
        "https://github.com/FluidSynth/fluidsynth/wiki/SoundFont",
    ]
    
    def __init__(self, config: Optional[SynthConfig] = None):
        """
        Args:
            config: Configuración del sintetizador
        """
        self.config = config or SynthConfig()
        self._fs = None
        self._sfid = None
        self._initialized = False
    
    def _ensure_init(self):
        """Inicializa FluidSynth bajo demanda"""
        if self._initialized:
            return
            
        try:
            import fluidsynth
            
            self._fs = fluidsynth.Synth(gain=self.config.gain)
            self._fs.start()
            
            if self.config.soundfont_path and os.path.exists(self.config.soundfont_path):
                self._sfid = self._fs.sfload(self.config.soundfont_path)
                self._fs.program_select(0, self._sfid, self.config.bank, self.config.preset)
            
            self._initialized = True
            
        except ImportError:
            raise RuntimeError(
                "FluidSynth no disponible. Instala con: pip install pyfluidsynth\n"
                "Y el binario: brew install fluidsynth (macOS)"
            )
    
    def render(
        self,
        notes: List[Note],
        sample_rate: int = 44100,
        duration: Optional[float] = None
    ) -> np.ndarray:
        """
        Renderiza una lista de notas a audio.
        
        Args:
            notes: Lista de notas a renderizar
            sample_rate: Frecuencia de muestreo
            duration: Duración total (None = auto)
            
        Returns:
            Array de audio
        """
        self._ensure_init()
        
        if not notes:
            return np.array([])
        
        # Calcular duración si no se especifica
        if duration is None:
            duration = max(n.start_time + n.duration for n in notes) + 0.5
        
        # Número de samples
        num_samples = int(duration * sample_rate)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        # Ordenar notas por tiempo de inicio
        sorted_notes = sorted(notes, key=lambda n: n.start_time)
        
        # Eventos MIDI: (time, type, note, velocity)
        events = []
        for note in sorted_notes:
            events.append((note.start_time, 'on', note.midi_note, note.velocity))
            events.append((note.start_time + note.duration, 'off', note.midi_note, 0))
        
        # Ordenar eventos por tiempo
        events.sort(key=lambda e: e[0])
        
        # Renderizar por segmentos
        current_time = 0.0
        current_sample = 0
        
        for event_time, event_type, midi_note, velocity in events:
            # Renderizar hasta este evento
            samples_to_render = int((event_time - current_time) * sample_rate)
            if samples_to_render > 0 and current_sample + samples_to_render <= num_samples:
                segment = self._render_segment(samples_to_render, sample_rate)
                end_sample = min(current_sample + len(segment), num_samples)
                audio[current_sample:end_sample] = segment[:end_sample - current_sample]
                current_sample = end_sample
                current_time = event_time
            
            # Procesar evento
            if event_type == 'on':
                self._fs.noteon(0, midi_note, velocity)
            else:
                self._fs.noteoff(0, midi_note)
        
        # Renderizar cola (release)
        remaining = num_samples - current_sample
        if remaining > 0:
            segment = self._render_segment(remaining, sample_rate)
            audio[current_sample:] = segment[:remaining]
        
        # Apagar todas las notas
        for note in sorted_notes:
            self._fs.noteoff(0, note.midi_note)
        
        return audio
    
    def _render_segment(self, num_samples: int, sample_rate: int) -> np.ndarray:
        """Renderiza un segmento de audio"""
        samples = self._fs.get_samples(num_samples)
        # FluidSynth retorna stereo interleaved, convertir a mono
        if len(samples) > 0:
            stereo = np.frombuffer(samples, dtype=np.int16).reshape(-1, 2)
            mono = stereo.mean(axis=1).astype(np.float32) / 32768.0
            return mono
        return np.zeros(num_samples, dtype=np.float32)
    
    def set_preset(self, preset: int, bank: int = 0):
        """Cambia el preset/instrumento"""
        self._ensure_init()
        if self._sfid is not None:
            self._fs.program_select(0, self._sfid, bank, preset)
            self.config.preset = preset
            self.config.bank = bank
    
    def close(self):
        """Cierra el sintetizador"""
        if self._fs:
            self._fs.delete()
            self._fs = None
            self._initialized = False


class SimpleSynthesizer:
    """
    Sintetizador simple sin dependencias externas.
    Usa síntesis por tabla de ondas básica.
    Útil para testing o cuando FluidSynth no está disponible.
    """
    
    WAVEFORMS = ['sine', 'square', 'sawtooth', 'triangle']
    
    def __init__(self, waveform: str = 'sine'):
        self.waveform = waveform
        self.attack = 0.01
        self.decay = 0.1
        self.sustain = 0.7
        self.release = 0.2
    
    def render(
        self,
        notes: List[Note],
        sample_rate: int = 44100,
        duration: Optional[float] = None
    ) -> np.ndarray:
        """Renderiza notas a audio usando síntesis simple"""
        if not notes:
            return np.array([])
        
        if duration is None:
            duration = max(n.start_time + n.duration for n in notes) + 0.5
        
        num_samples = int(duration * sample_rate)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        for note in notes:
            if note.note_type == NoteType.PERCUSSIVE:
                note_audio = self._render_percussion(note, sample_rate)
            else:
                note_audio = self._render_melodic(note, sample_rate)
            
            start_sample = int(note.start_time * sample_rate)
            end_sample = min(start_sample + len(note_audio), num_samples)
            audio[start_sample:end_sample] += note_audio[:end_sample - start_sample]
        
        # Normalizar
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = audio / max_val * 0.8
        
        return audio
    
    def _render_melodic(self, note: Note, sr: int) -> np.ndarray:
        """Renderiza una nota melódica"""
        from .scales import midi_to_hz
        
        freq = note.pitch_hz or midi_to_hz(note.midi_note)
        duration = note.duration + self.release
        num_samples = int(duration * sr)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)
        
        # Generar forma de onda
        if self.waveform == 'sine':
            wave = np.sin(2 * np.pi * freq * t)
        elif self.waveform == 'square':
            wave = np.sign(np.sin(2 * np.pi * freq * t))
        elif self.waveform == 'sawtooth':
            wave = 2 * (t * freq % 1) - 1
        elif self.waveform == 'triangle':
            wave = 2 * np.abs(2 * (t * freq % 1) - 1) - 1
        else:
            wave = np.sin(2 * np.pi * freq * t)
        
        # Aplicar envolvente ADSR
        envelope = self._adsr_envelope(num_samples, note.duration, sr)
        
        return wave * envelope * (note.velocity / 127.0)
    
    def _render_percussion(self, note: Note, sr: int) -> np.ndarray:
        """Renderiza un sonido percusivo simple"""
        duration = note.duration
        num_samples = int(duration * sr)
        
        # Ruido con envolvente rápida
        noise = np.random.randn(num_samples).astype(np.float32)
        
        # Envolvente percusiva (attack muy corto, decay rápido)
        t = np.linspace(0, 1, num_samples)
        envelope = np.exp(-t * 10)  # Decay exponencial
        
        return noise * envelope * 0.5
    
    def _adsr_envelope(self, num_samples: int, note_duration: float, sr: int) -> np.ndarray:
        """Genera envolvente ADSR"""
        envelope = np.ones(num_samples, dtype=np.float32)
        
        attack_samples = int(self.attack * sr)
        decay_samples = int(self.decay * sr)
        release_samples = int(self.release * sr)
        sustain_samples = int(note_duration * sr) - attack_samples - decay_samples
        
        idx = 0
        
        # Attack
        if attack_samples > 0:
            end = min(idx + attack_samples, num_samples)
            envelope[idx:end] = np.linspace(0, 1, end - idx)
            idx = end
        
        # Decay
        if decay_samples > 0 and idx < num_samples:
            end = min(idx + decay_samples, num_samples)
            envelope[idx:end] = np.linspace(1, self.sustain, end - idx)
            idx = end
        
        # Sustain
        if sustain_samples > 0 and idx < num_samples:
            end = min(idx + sustain_samples, num_samples)
            envelope[idx:end] = self.sustain
            idx = end
        
        # Release
        if idx < num_samples:
            envelope[idx:] = np.linspace(self.sustain, 0, num_samples - idx)
        
        return envelope


def get_available_presets() -> List[dict]:
    """Retorna lista de presets General MIDI comunes"""
    return [
        {"id": 0, "name": "Acoustic Grand Piano", "category": "piano"},
        {"id": 4, "name": "Electric Piano", "category": "piano"},
        {"id": 25, "name": "Acoustic Guitar", "category": "guitar"},
        {"id": 33, "name": "Electric Bass", "category": "bass"},
        {"id": 40, "name": "Violin", "category": "strings"},
        {"id": 48, "name": "String Ensemble", "category": "strings"},
        {"id": 56, "name": "Trumpet", "category": "brass"},
        {"id": 65, "name": "Alto Sax", "category": "winds"},
        {"id": 73, "name": "Flute", "category": "winds"},
        {"id": 80, "name": "Square Lead", "category": "synth"},
        {"id": 81, "name": "Sawtooth Lead", "category": "synth"},
        {"id": 88, "name": "Pad (New Age)", "category": "synth"},
    ]
