"""
Musical scales definitions for quantization.
"""
from typing import Dict, List, Set

# Intervalos en semitonos desde la raíz
SCALE_INTERVALS: Dict[str, List[int]] = {
    # Escalas mayores/menores
    "major": [0, 2, 4, 5, 7, 9, 11],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    
    # Pentatónicas
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    
    # Modos
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    
    # Blues y otras
    "blues": [0, 3, 5, 6, 7, 10],
    "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    
    # Exóticas
    "whole_tone": [0, 2, 4, 6, 8, 10],
    "diminished": [0, 2, 3, 5, 6, 8, 9, 11],
}

# Mapeo de nombres de notas a número MIDI (octava 4)
NOTE_TO_MIDI: Dict[str, int] = {
    'C': 60, 'C#': 61, 'Db': 61,
    'D': 62, 'D#': 63, 'Eb': 63,
    'E': 64, 'Fb': 64,
    'F': 65, 'F#': 66, 'Gb': 66,
    'G': 67, 'G#': 68, 'Ab': 68,
    'A': 69, 'A#': 70, 'Bb': 70,
    'B': 71, 'Cb': 71,
}

# Mapeo de número MIDI a nombre de nota
MIDI_TO_NOTE: Dict[int, str] = {
    0: 'C', 1: 'C#', 2: 'D', 3: 'D#',
    4: 'E', 5: 'F', 6: 'F#', 7: 'G',
    8: 'G#', 9: 'A', 10: 'A#', 11: 'B'
}


def get_scale_notes(root: str, scale_name: str) -> Set[int]:
    """
    Obtiene el conjunto de clases de pitch (0-11) para una escala.
    
    Args:
        root: Nota raíz (ej: 'C', 'F#')
        scale_name: Nombre de la escala
        
    Returns:
        Set de pitch classes (0-11) que pertenecen a la escala
    """
    if scale_name not in SCALE_INTERVALS:
        raise ValueError(f"Escala desconocida: {scale_name}")
    
    root_pc = NOTE_TO_MIDI.get(root, 60) % 12
    intervals = SCALE_INTERVALS[scale_name]
    
    return {(root_pc + interval) % 12 for interval in intervals}


def midi_to_note_name(midi_note: int) -> str:
    """
    Convierte número MIDI a nombre de nota.
    
    Args:
        midi_note: Número MIDI (0-127)
        
    Returns:
        Nombre de nota con octava (ej: 'C4', 'F#5')
    """
    octave = (midi_note // 12) - 1
    note = MIDI_TO_NOTE[midi_note % 12]
    return f"{note}{octave}"


def hz_to_midi(frequency: float) -> float:
    """
    Convierte frecuencia en Hz a número MIDI (puede ser fraccionario).
    
    Args:
        frequency: Frecuencia en Hz
        
    Returns:
        Número MIDI como float
    """
    import numpy as np
    if frequency <= 0:
        return 0.0
    return 69 + 12 * np.log2(frequency / 440.0)


def midi_to_hz(midi_note: float) -> float:
    """
    Convierte número MIDI a frecuencia en Hz.
    
    Args:
        midi_note: Número MIDI (puede ser fraccionario)
        
    Returns:
        Frecuencia en Hz
    """
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def quantize_to_scale(
    midi_note: float,
    scale_notes: Set[int],
    tolerance_cents: int = 25
) -> int:
    """
    Cuantiza una nota MIDI a la escala más cercana.
    
    Args:
        midi_note: Nota MIDI fraccionaria
        scale_notes: Set de pitch classes válidos
        tolerance_cents: Tolerancia en cents
        
    Returns:
        Nota MIDI cuantizada (entero)
    """
    import numpy as np
    
    # Nota entera más cercana
    rounded = int(round(midi_note))
    deviation_cents = abs(midi_note - rounded) * 100
    
    # Si la escala es cromática, simplemente redondear
    if len(scale_notes) == 12:
        return rounded
    
    # Encontrar la nota más cercana en la escala
    pitch_class = rounded % 12
    
    if pitch_class in scale_notes:
        # Ya está en la escala, verificar tolerancia
        if deviation_cents <= tolerance_cents:
            return rounded
        # Buscar alternativas si supera tolerancia
    
    # Buscar la nota más cercana en la escala
    best_note = rounded
    min_distance = float('inf')
    
    for offset in range(-12, 13):
        candidate = rounded + offset
        if candidate < 0 or candidate > 127:
            continue
        if candidate % 12 in scale_notes:
            distance = abs(midi_note - candidate)
            if distance < min_distance:
                min_distance = distance
                best_note = candidate
    
    return best_note


# Alias comunes
SCALES = list(SCALE_INTERVALS.keys())
