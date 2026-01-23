"""
MIDI and audio exporter.
Exports analysis results to MIDI, WAV, and MP3 formats.
"""
import os
from typing import List, Optional
from datetime import datetime

from .models import Note, NoteType, AnalysisResult, ExportConfig, Recording


class Exporter:
    """
    Exportador de MIDI y audio.
    Genera archivos .mid, .wav y .mp3 a partir de notas analizadas.
    """
    
    def __init__(self, config: Optional[ExportConfig] = None):
        self.config = config or ExportConfig()
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def export_all(
        self,
        result: AnalysisResult,
        original_recording: Optional[Recording] = None,
        synth_audio: Optional['np.ndarray'] = None,
        sample_rate: int = 44100,
        base_name: Optional[str] = None
    ) -> dict:
        """
        Exporta todos los formatos configurados.
        
        Args:
            result: Resultado del análisis
            original_recording: Grabación original (para guardar)
            synth_audio: Audio sintetizado
            sample_rate: Sample rate del audio sintetizado
            base_name: Nombre base para los archivos
            
        Returns:
            Dict con rutas de archivos generados
        """
        import numpy as np
        
        if base_name is None:
            base_name = datetime.now().strftime("vozacosa_%Y%m%d_%H%M%S")
        
        files = {}
        
        # Exportar MIDI
        if self.config.export_midi:
            midi_path = os.path.join(self.config.output_dir, f"{base_name}.mid")
            self.export_midi(result.notes, midi_path, result.tempo)
            files['midi'] = midi_path
        
        # Guardar audio original
        if self.config.save_original and original_recording is not None:
            original_path = os.path.join(self.config.output_dir, f"{base_name}_original.wav")
            self._save_wav(
                original_recording.audio,
                original_recording.sample_rate,
                original_path
            )
            files['original'] = original_path
        
        # Exportar audio sintetizado
        if synth_audio is not None and len(synth_audio) > 0:
            if self.config.export_wav:
                wav_path = os.path.join(self.config.output_dir, f"{base_name}_synth.wav")
                self._save_wav(synth_audio, sample_rate, wav_path)
                files['wav'] = wav_path
            
            if self.config.export_mp3:
                mp3_path = os.path.join(self.config.output_dir, f"{base_name}_synth.mp3")
                self._save_mp3(synth_audio, sample_rate, mp3_path)
                files['mp3'] = mp3_path
        
        return files
    
    def export_midi(
        self,
        notes: List[Note],
        filepath: str,
        tempo: Optional[float] = None
    ) -> str:
        """
        Exporta notas a archivo MIDI.
        
        Args:
            notes: Lista de notas
            filepath: Ruta del archivo
            tempo: BPM (default: 120)
            
        Returns:
            Ruta absoluta del archivo
        """
        from midiutil import MIDIFile
        
        # Separar notas melódicas y percusivas
        melodic_notes = [n for n in notes if n.note_type == NoteType.MELODIC]
        perc_notes = [n for n in notes if n.note_type == NoteType.PERCUSSIVE]
        
        num_tracks = 1 if not perc_notes else 2
        midi = MIDIFile(num_tracks)
        
        tempo = tempo or 120
        
        # Track 0: Notas melódicas
        track = 0
        channel = 0
        midi.addTempo(track, 0, tempo)
        midi.addProgramChange(track, channel, 0, 0)  # Piano
        
        for note in melodic_notes:
            midi.addNote(
                track=track,
                channel=channel,
                pitch=note.midi_note,
                time=note.start_time,
                duration=note.duration,
                volume=note.velocity
            )
        
        # Track 1: Percusión (si hay)
        if perc_notes:
            track = 1
            channel = 9  # Canal 10 para drums (0-indexed = 9)
            midi.addTempo(track, 0, tempo)
            
            for note in perc_notes:
                midi.addNote(
                    track=track,
                    channel=channel,
                    pitch=note.midi_note,
                    time=note.start_time,
                    duration=note.duration,
                    volume=note.velocity
                )
        
        # Guardar archivo
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'wb') as f:
            midi.writeFile(f)
        
        return os.path.abspath(filepath)
    
    def export_midi_pretty(
        self,
        notes: List[Note],
        filepath: str,
        tempo: Optional[float] = None
    ) -> str:
        """
        Exporta notas a MIDI usando pretty_midi (alternativa).
        """
        import pretty_midi
        
        pm = pretty_midi.PrettyMIDI(initial_tempo=tempo or 120)
        
        # Instrumento melódico
        melodic_program = pretty_midi.instrument_name_to_program('Acoustic Grand Piano')
        melodic = pretty_midi.Instrument(program=melodic_program)
        
        # Instrumento percusivo
        drums = pretty_midi.Instrument(program=0, is_drum=True)
        
        for note in notes:
            pm_note = pretty_midi.Note(
                velocity=note.velocity,
                pitch=note.midi_note,
                start=note.start_time,
                end=note.start_time + note.duration
            )
            
            if note.note_type == NoteType.PERCUSSIVE:
                drums.notes.append(pm_note)
            else:
                melodic.notes.append(pm_note)
        
        if melodic.notes:
            pm.instruments.append(melodic)
        if drums.notes:
            pm.instruments.append(drums)
        
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        pm.write(filepath)
        
        return os.path.abspath(filepath)
    
    def _save_wav(
        self,
        audio: 'np.ndarray',
        sample_rate: int,
        filepath: str
    ) -> str:
        """Guarda audio como WAV"""
        import numpy as np
        from scipy.io import wavfile
        
        # Normalizar y convertir a int16
        audio = np.clip(audio, -1, 1)
        audio_int16 = (audio * 32767).astype(np.int16)
        
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        wavfile.write(filepath, sample_rate, audio_int16)
        
        return os.path.abspath(filepath)
    
    def _save_mp3(
        self,
        audio: 'np.ndarray',
        sample_rate: int,
        filepath: str
    ) -> str:
        """Guarda audio como MP3 usando pydub"""
        import numpy as np
        from pydub import AudioSegment
        import tempfile
        
        # Primero guardar como WAV temporal
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
        
        self._save_wav(audio, sample_rate, tmp_path)
        
        # Convertir a MP3
        audio_segment = AudioSegment.from_wav(tmp_path)
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        audio_segment.export(filepath, format='mp3', bitrate='192k')
        
        # Limpiar temporal
        os.unlink(tmp_path)
        
        return os.path.abspath(filepath)


def generate_session_name() -> str:
    """Genera un nombre único para la sesión"""
    return datetime.now().strftime("vozacosa_%Y%m%d_%H%M%S")
