"""
SOTA Audio analyzer using CREPE for pitch detection.
Detects pitch, onset, and classifies melodic vs percussive content.
"""
import numpy as np
from typing import Optional, Tuple, List
import warnings

# Suppress TensorFlow warnings
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from .models import (
    Recording, AnalysisResult, Note, NoteType, 
    PercussionType, QuantizationConfig
)
from .scales import hz_to_midi, midi_to_hz, get_scale_notes, quantize_to_scale


class PitchAnalyzer:
    """
    Analizador de pitch usando CREPE (SOTA deep learning model).
    
    CREPE es un modelo CNN entrenado para detección de pitch monofónico,
    con precisión superior a métodos tradicionales como pYIN.
    """
    
    def __init__(
        self,
        model_capacity: str = 'medium',
        step_size: int = 10,
        confidence_threshold: float = 0.5,
        min_note_duration: float = 0.05
    ):
        """
        Args:
            model_capacity: Tamaño del modelo CREPE ('tiny', 'small', 'medium', 'large', 'full')
            step_size: Paso en ms entre frames de pitch
            confidence_threshold: Umbral mínimo de confianza para considerar un pitch válido
            min_note_duration: Duración mínima de nota en segundos
        """
        self.model_capacity = model_capacity
        self.step_size = step_size
        self.confidence_threshold = confidence_threshold
        self.min_note_duration = min_note_duration
        
        self._crepe_loaded = False
    
    def _ensure_crepe(self):
        """Carga CREPE bajo demanda"""
        if not self._crepe_loaded:
            import crepe
            self._crepe = crepe
            self._crepe_loaded = True
    
    def analyze(
        self,
        recording: Recording,
        quantization: Optional[QuantizationConfig] = None
    ) -> AnalysisResult:
        """
        Analiza una grabación y extrae notas.
        
        Args:
            recording: Grabación de audio a analizar
            quantization: Configuración de cuantización (opcional)
            
        Returns:
            AnalysisResult con notas, pitch track, etc.
        """
        self._ensure_crepe()
        
        if len(recording.audio) == 0:
            return AnalysisResult()
        
        # Detectar pitch con CREPE
        time_axis, frequency, confidence, _ = self._crepe.predict(
            recording.audio,
            recording.sample_rate,
            model_capacity=self.model_capacity,
            step_size=self.step_size,
            viterbi=True,  # Suavizado temporal
            verbose=0
        )
        
        # Detectar si es percusivo
        is_percussive = self._detect_percussive(
            recording.audio, 
            recording.sample_rate,
            confidence
        )
        
        # Extraer notas del pitch track
        if is_percussive:
            notes = self._extract_percussion_notes(
                recording.audio,
                recording.sample_rate,
                time_axis
            )
        else:
            notes = self._extract_melodic_notes(
                time_axis,
                frequency,
                confidence,
                quantization
            )
        
        # Estimar tempo
        tempo = self._estimate_tempo(recording.audio, recording.sample_rate)
        
        # Detectar onsets
        onset_times = self._detect_onsets(recording.audio, recording.sample_rate)
        
        return AnalysisResult(
            notes=notes,
            tempo=tempo,
            is_percussive=is_percussive,
            pitch_track=frequency,
            confidence_track=confidence,
            onset_times=onset_times
        )
    
    def _extract_melodic_notes(
        self,
        time_axis: np.ndarray,
        frequency: np.ndarray,
        confidence: np.ndarray,
        quantization: Optional[QuantizationConfig]
    ) -> List[Note]:
        """Extrae notas melódicas del pitch track"""
        notes = []
        
        # Encontrar segmentos con confianza suficiente
        valid = confidence >= self.confidence_threshold
        
        # Encontrar cambios de estado (nota on/off)
        changes = np.diff(valid.astype(int))
        note_starts = np.where(changes == 1)[0] + 1
        note_ends = np.where(changes == -1)[0] + 1
        
        # Manejar caso inicial
        if valid[0]:
            note_starts = np.insert(note_starts, 0, 0)
        if valid[-1]:
            note_ends = np.append(note_ends, len(valid))
        
        # Configurar cuantización
        if quantization and quantization.scale:
            scale_notes = get_scale_notes(quantization.root_note, quantization.scale)
            tolerance = quantization.tolerance_cents
        else:
            scale_notes = set(range(12))  # Cromática
            tolerance = 50
        
        # Crear notas para cada segmento
        for start_idx, end_idx in zip(note_starts, note_ends):
            start_time = time_axis[start_idx]
            end_time = time_axis[min(end_idx, len(time_axis) - 1)]
            duration = end_time - start_time
            
            # Filtrar notas muy cortas
            if duration < self.min_note_duration:
                continue
            
            # Pitch promedio ponderado por confianza
            segment_freq = frequency[start_idx:end_idx]
            segment_conf = confidence[start_idx:end_idx]
            
            if len(segment_freq) == 0 or segment_conf.sum() == 0:
                continue
                
            avg_freq = np.average(segment_freq, weights=segment_conf)
            avg_conf = np.mean(segment_conf)
            
            # Convertir a MIDI y cuantizar
            midi_float = hz_to_midi(avg_freq)
            midi_quantized = quantize_to_scale(midi_float, scale_notes, tolerance)
            quantized_hz = midi_to_hz(midi_quantized)
            
            # Velocity basada en confianza
            velocity = int(np.clip(avg_conf * 127, 40, 127))
            
            note = Note(
                pitch_hz=quantized_hz,
                midi_note=midi_quantized,
                start_time=start_time,
                duration=duration,
                velocity=velocity,
                confidence=avg_conf,
                note_type=NoteType.MELODIC,
                original_pitch_hz=avg_freq
            )
            notes.append(note)
        
        return notes
    
    def _extract_percussion_notes(
        self,
        audio: np.ndarray,
        sr: int,
        time_axis: np.ndarray
    ) -> List[Note]:
        """Extrae notas percusivas basadas en onsets y características espectrales"""
        import librosa
        
        notes = []
        
        # Detectar onsets
        onset_frames = librosa.onset.onset_detect(y=audio, sr=sr, units='frames')
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        
        for i, onset_time in enumerate(onset_times):
            # Determinar duración hasta el siguiente onset
            if i < len(onset_times) - 1:
                duration = min(onset_times[i + 1] - onset_time, 0.25)
            else:
                duration = 0.1
            
            # Extraer segmento para análisis espectral
            start_sample = int(onset_time * sr)
            end_sample = min(start_sample + int(0.1 * sr), len(audio))
            segment = audio[start_sample:end_sample]
            
            if len(segment) < 256:
                continue
            
            # Clasificar tipo de percusión
            perc_type, midi_note = self._classify_percussion(segment, sr)
            
            note = Note(
                pitch_hz=None,
                midi_note=midi_note,
                start_time=onset_time,
                duration=duration,
                velocity=100,
                confidence=0.8,
                note_type=NoteType.PERCUSSIVE,
                percussion_type=perc_type
            )
            notes.append(note)
        
        return notes
    
    def _classify_percussion(
        self,
        segment: np.ndarray,
        sr: int
    ) -> Tuple[PercussionType, int]:
        """
        Clasifica un segmento de audio en tipo de percusión.
        Usa heurísticas espectrales simples.
        """
        import librosa
        
        # Características espectrales
        spectral_centroid = librosa.feature.spectral_centroid(y=segment, sr=sr)[0].mean()
        zcr = librosa.feature.zero_crossing_rate(segment)[0].mean()
        
        # Heurísticas basadas en centroide y ZCR
        # Kick: baja frecuencia, bajo ZCR
        # Snare: media frecuencia, alto ZCR
        # Hihat: alta frecuencia, muy alto ZCR
        
        if spectral_centroid < 500 and zcr < 0.1:
            return PercussionType.KICK, 36  # C1 en General MIDI drums
        elif spectral_centroid > 3000 or zcr > 0.3:
            return PercussionType.HIHAT, 42  # Closed Hi-Hat
        elif zcr > 0.15:
            return PercussionType.SNARE, 38  # Acoustic Snare
        else:
            return PercussionType.UNKNOWN, 36
    
    def _detect_percussive(
        self,
        audio: np.ndarray,
        sr: int,
        confidence: np.ndarray
    ) -> bool:
        """
        Detecta si el audio es principalmente percusivo.
        
        Criterios:
        - Baja confianza promedio de pitch (< 0.4)
        - Alto ratio de onsets vs duración
        """
        import librosa
        
        avg_confidence = np.mean(confidence)
        
        # Detectar onsets
        onset_frames = librosa.onset.onset_detect(y=audio, sr=sr)
        duration = len(audio) / sr
        onset_density = len(onset_frames) / duration if duration > 0 else 0
        
        # Percusivo si: baja confianza de pitch Y alta densidad de onsets
        is_percussive = avg_confidence < 0.4 and onset_density > 2.0
        
        return is_percussive
    
    def _estimate_tempo(self, audio: np.ndarray, sr: int) -> Optional[float]:
        """Estima el tempo en BPM"""
        import librosa
        
        try:
            tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
            return float(tempo) if tempo > 0 else None
        except Exception:
            return None
    
    def _detect_onsets(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Detecta tiempos de onset"""
        import librosa
        
        onset_frames = librosa.onset.onset_detect(y=audio, sr=sr)
        return librosa.frames_to_time(onset_frames, sr=sr)


def load_audio_file(filepath: str, sr: int = 22050) -> Recording:
    """
    Carga un archivo de audio.
    
    Args:
        filepath: Ruta al archivo
        sr: Sample rate objetivo
        
    Returns:
        Recording con el audio cargado
    """
    import librosa
    
    audio, sample_rate = librosa.load(filepath, sr=sr, mono=True)
    duration = len(audio) / sample_rate
    
    return Recording(
        audio=audio,
        sample_rate=sample_rate,
        duration=duration,
        filepath=filepath
    )
