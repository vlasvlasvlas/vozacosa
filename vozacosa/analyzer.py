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
        confidence_threshold: float = 0.4,
        min_note_duration: float = 0.08
    ):
        """
        Args:
            model_capacity: Tamaño del modelo CREPE ('tiny', 'small', 'medium', 'large', 'full')
                           'medium' recommended for balance of speed/accuracy
            step_size: Paso en ms entre frames de pitch (lower = more precise)
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
        
        Usa un enfoque híbrido SOTA:
        1. CREPE para detección de pitch (SOTA en monofónico)
        2. Librosa para detección de onsets (ataques de nota)
        3. Combina ambos para extraer notas limpias
        """
        self._ensure_crepe()
        import librosa
        
        if len(recording.audio) == 0:
            return AnalysisResult()
        
        print(f"🎤 Analyzing {len(recording.audio)/recording.sample_rate:.1f}s of audio...")
        
        # 1. Detectar pitch con CREPE
        print(f"    🧠 Running CREPE ({self.model_capacity})...")
        time_axis, frequency, confidence, _ = self._crepe.predict(
            recording.audio,
            recording.sample_rate,
            model_capacity=self.model_capacity,
            step_size=self.step_size,
            viterbi=True,  # Suavizado temporal HMM
            verbose=0
        )
        
        # 2. Detectar onsets (ataques de nota) con librosa
        print("    🥁 Detecting note onsets...")
        onset_frames = librosa.onset.onset_detect(
            y=recording.audio, 
            sr=recording.sample_rate,
            units='time',
            backtrack=True,  # Retroceder al inicio real del ataque
            pre_max=3,
            post_max=3,
            pre_avg=3,
            post_avg=5,
            delta=0.07,  # Sensibilidad
            wait=5  # Frames mínimos entre onsets
        )
        onset_times = onset_frames
        print(f"    🥁 Found {len(onset_times)} onsets")
        
        # 3. Detectar si es percusivo
        is_percussive = self._detect_percussive(
            recording.audio, 
            recording.sample_rate,
            confidence
        )
        
        # 4. Extraer notas combinando pitch + onsets
        if is_percussive:
            notes = self._extract_percussion_notes(
                recording.audio,
                recording.sample_rate,
                time_axis
            )
        else:
            notes = self._extract_melodic_notes_with_onsets(
                time_axis,
                frequency,
                confidence,
                onset_times,
                recording.audio,
                recording.sample_rate,
                quantization
            )
        
        # 5. Estimar tempo
        tempo = self._estimate_tempo(recording.audio, recording.sample_rate)
        
        return AnalysisResult(
            notes=notes,
            tempo=tempo,
            is_percussive=is_percussive,
            pitch_track=frequency,
            confidence_track=confidence,
            onset_times=onset_times
        )
    
    def _extract_melodic_notes_with_onsets(
        self,
        time_axis: np.ndarray,
        frequency: np.ndarray,
        confidence: np.ndarray,
        onset_times: np.ndarray,
        audio: np.ndarray,
        sr: int,
        quantization: Optional[QuantizationConfig]
    ) -> List[Note]:
        """
        Extrae notas usando ONSETS como guía.
        
        Este es el enfoque SOTA: cada onset marca el inicio de una nota,
        y usamos el pitch de CREPE para determinar la altura.
        """
        import librosa
        
        notes = []
        
        print(f"    🎵 Extracting notes from {len(onset_times)} onsets...")
        
        # Configurar cuantización
        if quantization and quantization.scale:
            scale_notes = get_scale_notes(quantization.root_note, quantization.scale)
            tolerance = quantization.tolerance_cents
        else:
            scale_notes = set(range(12))  # Cromática
            tolerance = 50
        
        # Detectar offsets (fin de notas) usando RMS energy
        rms = librosa.feature.rms(y=audio, frame_length=2048, hop_length=512)[0]
        rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
        rms_threshold = np.percentile(rms, 20)  # 20th percentile como umbral de silencio
        
        # Si no hay onsets detectados, usar el método anterior
        if len(onset_times) == 0:
            print("    ⚠️ No onsets detected, falling back to pitch-based detection")
            return self._extract_melodic_notes(time_axis, frequency, confidence, quantization)
        
        # Procesar cada onset
        audio_duration = len(audio) / sr
        
        for i, onset in enumerate(onset_times):
            # Determinar fin de nota: siguiente onset o fin de audio
            if i < len(onset_times) - 1:
                next_onset = onset_times[i + 1]
            else:
                next_onset = audio_duration
            
            # Buscar offset (fin real de la nota por caída de energía)
            offset = next_onset
            onset_rms_idx = np.searchsorted(rms_times, onset)
            for j in range(onset_rms_idx, len(rms)):
                if rms_times[j] >= next_onset:
                    break
                if rms[j] < rms_threshold:
                    offset = rms_times[j]
                    break
            
            duration = offset - onset
            
            # Filtrar notas muy cortas
            if duration < self.min_note_duration:
                continue
            
            # Obtener el pitch del segmento desde CREPE
            start_idx = np.searchsorted(time_axis, onset)
            end_idx = np.searchsorted(time_axis, offset)
            
            if end_idx <= start_idx:
                continue
            
            segment_freq = frequency[start_idx:end_idx]
            segment_conf = confidence[start_idx:end_idx]
            
            # Solo usar frames con confianza suficiente
            valid_mask = segment_conf >= self.confidence_threshold
            if not np.any(valid_mask):
                continue
            
            valid_freqs = segment_freq[valid_mask]
            valid_confs = segment_conf[valid_mask]
            
            # Usar mediana para robustez (ignora outliers de transitorios)
            median_freq = np.median(valid_freqs)
            avg_conf = np.mean(valid_confs)
            
            # Convertir a MIDI y cuantizar
            midi_float = hz_to_midi(median_freq)
            midi_quantized = quantize_to_scale(midi_float, scale_notes, tolerance)
            quantized_hz = midi_to_hz(midi_quantized)
            
            velocity = int(np.clip(avg_conf * 127, 50, 127))
            
            note = Note(
                pitch_hz=quantized_hz,
                midi_note=midi_quantized,
                start_time=onset,
                duration=duration,
                velocity=velocity,
                confidence=avg_conf,
                note_type=NoteType.MELODIC,
                original_pitch_hz=median_freq
            )
            notes.append(note)
        
        print(f"    🎵 Created {len(notes)} notes from onsets")
        
        # Fusionar notas consecutivas de la misma altura
        notes = self._merge_same_pitch_notes(notes)
        
        print(f"    🎵 Final: {len(notes)} notes after merging same-pitch")
        
        return notes
    
    def _merge_same_pitch_notes(self, notes: List[Note]) -> List[Note]:
        """Fusiona notas consecutivas de la misma altura si están muy cerca"""
        if len(notes) < 2:
            return notes
        
        merged = []
        current = notes[0]
        
        for next_note in notes[1:]:
            gap = next_note.start_time - (current.start_time + current.duration)
            same_pitch = current.midi_note == next_note.midi_note
            
            # Fusionar si misma nota y gap menor a 80ms
            if same_pitch and gap < 0.08:
                current = Note(
                    pitch_hz=current.pitch_hz,
                    midi_note=current.midi_note,
                    start_time=current.start_time,
                    duration=(next_note.start_time + next_note.duration) - current.start_time,
                    velocity=max(current.velocity, next_note.velocity),
                    confidence=(current.confidence + next_note.confidence) / 2,
                    note_type=current.note_type,
                    original_pitch_hz=current.original_pitch_hz
                )
            else:
                merged.append(current)
                current = next_note
        
        merged.append(current)
        return merged
    
    def _extract_melodic_notes(
        self,
        time_axis: np.ndarray,
        frequency: np.ndarray,
        confidence: np.ndarray,
        quantization: Optional[QuantizationConfig]
    ) -> List[Note]:
        """
        Extrae notas melódicas del pitch track.
        
        NUEVO ALGORITMO: Detecta cambios de pitch (no solo silencios) para separar notas.
        Esto es crucial para melodías tarareadas donde no hay gaps de silencio.
        """
        notes = []
        
        print(f"    🎵 Extracting notes: {len(time_axis)} frames, conf_threshold={self.confidence_threshold}")
        print(f"    🎵 Confidence stats: min={confidence.min():.2f}, max={confidence.max():.2f}, mean={confidence.mean():.2f}")
        
        # Configurar cuantización
        if quantization and quantization.scale:
            scale_notes = get_scale_notes(quantization.root_note, quantization.scale)
            tolerance = quantization.tolerance_cents
        else:
            scale_notes = set(range(12))  # Cromática
            tolerance = 50
        
        # Convertir todas las frecuencias a MIDI (cuantizadas)
        midi_track = np.zeros(len(frequency))
        for i in range(len(frequency)):
            if confidence[i] >= self.confidence_threshold and frequency[i] > 0:
                midi_float = hz_to_midi(frequency[i])
                midi_track[i] = quantize_to_scale(midi_float, scale_notes, tolerance)
            else:
                midi_track[i] = 0  # No válido
        
        # Encontrar segmentos con confianza suficiente
        valid = confidence >= self.confidence_threshold
        valid_count = np.sum(valid)
        print(f"    🎵 Valid frames (conf >= {self.confidence_threshold}): {valid_count} / {len(valid)} ({100*valid_count/len(valid):.1f}%)")
        
        if valid_count == 0:
            print("    ⚠️ No valid frames found!")
            return []
        
        # Ahora detectamos cambios: ya sea silencio O cambio de nota MIDI
        # Un cambio ocurre cuando:
        # 1. Pasamos de válido a inválido (silencio)
        # 2. Pasamos de inválido a válido (inicio)
        # 3. El MIDI note cambia (cambio de pitch)
        
        in_note = False
        note_start_idx = 0
        current_midi = 0
        
        for i in range(len(valid)):
            is_valid = valid[i]
            this_midi = midi_track[i] if is_valid else 0
            
            if not in_note and is_valid:
                # Inicio de nota
                in_note = True
                note_start_idx = i
                current_midi = this_midi
                
            elif in_note:
                # Verificar si hay cambio
                pitch_changed = is_valid and abs(this_midi - current_midi) >= 1
                note_ended = not is_valid
                
                if pitch_changed or note_ended or i == len(valid) - 1:
                    # Finalizar nota actual
                    note_end_idx = i if (pitch_changed or note_ended) else i + 1
                    
                    start_time = time_axis[note_start_idx]
                    end_time = time_axis[min(note_end_idx, len(time_axis) - 1)]
                    duration = end_time - start_time
                    
                    if duration >= self.min_note_duration:
                        # Calcular pitch promedio del segmento
                        segment_freq = frequency[note_start_idx:note_end_idx]
                        segment_conf = confidence[note_start_idx:note_end_idx]
                        segment_valid = segment_conf >= self.confidence_threshold
                        
                        if np.any(segment_valid):
                            valid_freqs = segment_freq[segment_valid]
                            valid_confs = segment_conf[segment_valid]
                            
                            # Mediana para robustez
                            avg_freq = np.median(valid_freqs)
                            avg_conf = np.mean(valid_confs)
                            
                            midi_float = hz_to_midi(avg_freq)
                            midi_quantized = quantize_to_scale(midi_float, scale_notes, tolerance)
                            quantized_hz = midi_to_hz(midi_quantized)
                            
                            velocity = int(np.clip(avg_conf * 127, 50, 127))
                            
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
                    
                    # Preparar siguiente nota si hay cambio de pitch (no silencio)
                    if pitch_changed:
                        in_note = True
                        note_start_idx = i
                        current_midi = this_midi
                    else:
                        in_note = False
        
        print(f"    🎵 Found {len(notes)} raw notes")
        
        # Limpiar micro-notas (transitorios de ataque)
        notes = self._clean_micro_notes(notes)
        
        print(f"    🎵 Final: {len(notes)} notes after cleanup")
        
        return notes
    
    def _clean_micro_notes(self, notes: List[Note]) -> List[Note]:
        """
        Elimina micro-notas que son transitorios de ataque.
        
        Una micro-nota es una nota muy corta que aparece justo antes de una nota
        principal más larga. Son artefactos del cambio de pitch durante el ataque.
        """
        if len(notes) < 2:
            return notes
        
        # Umbral: notas menores a 100ms son candidatas a micro-notas
        MICRO_THRESHOLD = 0.10  # 100ms
        # Gap máximo para considerar que es parte del ataque de la siguiente nota
        MAX_GAP = 0.05  # 50ms
        
        cleaned = []
        i = 0
        
        while i < len(notes):
            current = notes[i]
            
            # Si es una nota corta, verificar si es micro-nota
            if current.duration < MICRO_THRESHOLD and i < len(notes) - 1:
                next_note = notes[i + 1]
                gap = next_note.start_time - (current.start_time + current.duration)
                
                # Si hay una nota más larga muy cerca, esta es micro-nota - saltearla
                if gap < MAX_GAP and next_note.duration >= MICRO_THRESHOLD:
                    print(f"      🗑️ Removing micro-note: {current.midi_note} ({current.duration:.3f}s) before {next_note.midi_note}")
                    i += 1
                    continue
            
            # También limpiar micro-notas al FINAL de una nota principal
            # (cuando la voz "decae" a otra frecuencia brevemente)
            if i > 0 and current.duration < MICRO_THRESHOLD:
                prev_note = cleaned[-1] if cleaned else None
                if prev_note:
                    gap = current.start_time - (prev_note.start_time + prev_note.duration)
                    if gap < MAX_GAP and prev_note.duration >= MICRO_THRESHOLD:
                        print(f"      🗑️ Removing trailing micro-note: {current.midi_note} ({current.duration:.3f}s) after {prev_note.midi_note}")
                        i += 1
                        continue
            
            cleaned.append(current)
            i += 1
        
        return cleaned
    
    def _merge_consecutive_notes(self, notes: List[Note]) -> List[Note]:
        """Fusiona notas consecutivas de la misma altura si están muy cerca"""
        if len(notes) < 2:
            return notes
        
        merged = []
        current = notes[0]
        
        for next_note in notes[1:]:
            gap = next_note.start_time - (current.start_time + current.duration)
            same_pitch = current.midi_note == next_note.midi_note
            
            # Fusionar si misma nota y gap menor a 100ms
            if same_pitch and gap < 0.1:
                # Extender la nota actual
                current = Note(
                    pitch_hz=current.pitch_hz,
                    midi_note=current.midi_note,
                    start_time=current.start_time,
                    duration=(next_note.start_time + next_note.duration) - current.start_time,
                    velocity=max(current.velocity, next_note.velocity),
                    confidence=(current.confidence + next_note.confidence) / 2,
                    note_type=current.note_type,
                    original_pitch_hz=current.original_pitch_hz
                )
            else:
                merged.append(current)
                current = next_note
        
        merged.append(current)
        return merged
    
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
        - Muy baja confianza promedio de pitch (< 0.2)
        - Alto ratio de onsets vs duración
        """
        import librosa
        
        avg_confidence = np.mean(confidence)
        high_conf_ratio = np.mean(confidence > 0.5)  # Qué % del audio tiene alta confianza
        
        # Detectar onsets
        onset_frames = librosa.onset.onset_detect(y=audio, sr=sr)
        duration = len(audio) / sr if len(audio) > 0 else 1
        onset_density = len(onset_frames) / duration if duration > 0 else 0
        
        # Percusivo SOLO si: MUY baja confianza Y alta densidad de onsets
        # La voz normalmente tiene algo de pitch detectable
        is_percussive = avg_confidence < 0.2 and high_conf_ratio < 0.1 and onset_density > 3.0
        
        print(f"    🔍 Percussive check: avg_conf={avg_confidence:.2f}, high_conf_ratio={high_conf_ratio:.2f}, onset_density={onset_density:.1f} -> {is_percussive}")
        
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
