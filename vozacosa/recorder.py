"""
Audio recorder module using sounddevice.
Handles microphone input with start/stop control.
"""
import numpy as np
import sounddevice as sd
import wave
import os
from typing import Optional, Callable
from dataclasses import dataclass
from threading import Event
import time

from .models import Recording


class AudioRecorder:
    """
    Grabador de audio con control de inicio/parada.
    
    Usage:
        recorder = AudioRecorder()
        recorder.start()
        # ... usuario canta ...
        recording = recorder.stop()
    """
    
    def __init__(
        self,
        sample_rate: int = 22050,
        channels: int = 1,
        dtype: str = 'float32',
        device: Optional[int] = None
    ):
        """
        Inicializa el grabador.
        
        Args:
            sample_rate: Frecuencia de muestreo (22050 ideal para análisis)
            channels: Número de canales (1 = mono)
            dtype: Tipo de datos de audio
            device: ID del dispositivo de entrada (None = default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device
        
        self._is_recording = False
        self._stop_event = Event()
        self._audio_chunks: list = []
        self._stream: Optional[sd.InputStream] = None
        self._start_time: float = 0
        
    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status
    ):
        """Callback para recibir chunks de audio"""
        if status:
            print(f"[Recorder] Status: {status}")
        if self._is_recording:
            self._audio_chunks.append(indata.copy())
    
    def start(self) -> None:
        """Inicia la grabación"""
        if self._is_recording:
            return
            
        self._audio_chunks = []
        self._stop_event.clear()
        self._is_recording = True
        self._start_time = time.time()
        
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            device=self.device,
            callback=self._audio_callback
        )
        self._stream.start()
    
    def stop(self) -> Recording:
        """
        Detiene la grabación y retorna el resultado.
        
        Returns:
            Recording con el audio grabado
        """
        if not self._is_recording:
            return Recording(
                audio=np.array([]),
                sample_rate=self.sample_rate,
                duration=0.0
            )
        
        self._is_recording = False
        
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        # Concatenar todos los chunks
        if self._audio_chunks:
            audio = np.concatenate(self._audio_chunks, axis=0)
            # Convertir a mono si es necesario
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            audio = audio.flatten()
        else:
            audio = np.array([])
        
        duration = len(audio) / self.sample_rate if len(audio) > 0 else 0.0
        
        return Recording(
            audio=audio,
            sample_rate=self.sample_rate,
            duration=duration
        )
    
    @property
    def is_recording(self) -> bool:
        return self._is_recording
    
    @property
    def elapsed_time(self) -> float:
        """Tiempo transcurrido de grabación en segundos"""
        if not self._is_recording:
            return 0.0
        return time.time() - self._start_time
    
    def save_wav(self, recording: Recording, filepath: str) -> str:
        """
        Guarda la grabación como archivo WAV.
        
        Args:
            recording: Recording a guardar
            filepath: Ruta del archivo
            
        Returns:
            Ruta absoluta del archivo guardado
        """
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        
        # Convertir float32 a int16 para WAV
        audio_int16 = (recording.audio * 32767).astype(np.int16)
        
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(recording.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        
        return os.path.abspath(filepath)


def list_audio_devices() -> list:
    """Lista los dispositivos de audio disponibles"""
    devices = sd.query_devices()
    input_devices = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_devices.append({
                'id': i,
                'name': dev['name'],
                'channels': dev['max_input_channels'],
                'sample_rate': dev['default_samplerate']
            })
    return input_devices


def get_default_input_device() -> Optional[int]:
    """Obtiene el ID del dispositivo de entrada por defecto"""
    try:
        return sd.default.device[0]
    except Exception:
        return None
