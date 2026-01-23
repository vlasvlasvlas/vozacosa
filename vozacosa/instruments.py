"""
Instrument manager for VozACosa.
Loads and manages JSON-defined instruments with support for:
- SoundFont-based instruments
- Wavetable synthesis
- Karplus-Strong (physical modeling)
- Additive synthesis
- Custom drum kits
"""
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

from .models import Note, NoteType


class InstrumentType(Enum):
    SOUNDFONT = "soundfont"
    WAVETABLE = "wavetable"
    KARPLUS_STRONG = "karplus_strong"
    ADDITIVE = "additive"
    SAMPLES = "samples"


@dataclass
class Envelope:
    """ADSR envelope configuration"""
    attack: float = 0.01
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.3
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Envelope':
        return cls(**{k: v for k, v in d.items() if k in ['attack', 'decay', 'sustain', 'release']})


@dataclass
class Instrument:
    """Represents a loaded instrument"""
    id: str
    name: str
    category: str
    type: InstrumentType
    description: str = ""
    
    # SoundFont specific
    soundfont: Optional[str] = None
    bank: int = 0
    preset: int = 0
    
    # Synthesis parameters
    waveform: str = "sine"
    envelope: Envelope = field(default_factory=Envelope)
    
    # Additional parameters stored as dict
    params: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, id: str, d: Dict) -> 'Instrument':
        inst_type = InstrumentType(d.get('type', 'wavetable'))
        envelope = Envelope.from_dict(d.get('envelope', {}))
        
        return cls(
            id=id,
            name=d.get('name', id),
            category=d.get('category', 'synth'),
            type=inst_type,
            description=d.get('description', ''),
            soundfont=d.get('soundfont'),
            bank=d.get('bank', 0),
            preset=d.get('preset', 0),
            waveform=d.get('waveform', 'sine'),
            envelope=envelope,
            params=d
        )


@dataclass
class DrumKit:
    """Represents a drum kit"""
    id: str
    name: str
    type: InstrumentType
    mapping: Dict[str, Any]  # percussion_type -> midi_note or sample
    soundfont: Optional[str] = None
    bank: int = 128
    preset: int = 0


class InstrumentManager:
    """
    Manages instrument definitions from JSON files.
    Allows loading, listing, and selecting instruments for synthesis.
    """
    
    def __init__(self, instruments_dir: str = None):
        """
        Args:
            instruments_dir: Directory containing instruments.json and soundfonts
        """
        if instruments_dir is None:
            # Default to package instruments directory
            instruments_dir = os.path.join(os.path.dirname(__file__), '..', 'instruments')
        
        self.instruments_dir = os.path.abspath(instruments_dir)
        self.instruments: Dict[str, Instrument] = {}
        self.drum_kits: Dict[str, DrumKit] = {}
        self.categories: Dict[str, Dict] = {}
        
        self._load_instruments()
    
    def _load_instruments(self):
        """Load instruments from JSON file"""
        json_path = os.path.join(self.instruments_dir, 'instruments.json')
        
        if not os.path.exists(json_path):
            # Create default instruments if file doesn't exist
            self._create_default_instruments()
            return
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Load instruments
        for inst_id, inst_data in data.get('instruments', {}).items():
            self.instruments[inst_id] = Instrument.from_dict(inst_id, inst_data)
        
        # Load drum kits
        for kit_id, kit_data in data.get('drum_kits', {}).items():
            self.drum_kits[kit_id] = DrumKit(
                id=kit_id,
                name=kit_data.get('name', kit_id),
                type=InstrumentType(kit_data.get('type', 'soundfont')),
                mapping=kit_data.get('mapping', {}),
                soundfont=kit_data.get('soundfont'),
                bank=kit_data.get('bank', 128),
                preset=kit_data.get('preset', 0)
            )
        
        # Load categories
        self.categories = data.get('categories', {})
    
    def _create_default_instruments(self):
        """Create default instruments in memory"""
        defaults = {
            'sine': Instrument(
                id='sine', name='Sine Wave', category='synth',
                type=InstrumentType.WAVETABLE, waveform='sine',
                description='Pure sine wave'
            ),
            'sawtooth': Instrument(
                id='sawtooth', name='Sawtooth', category='synth',
                type=InstrumentType.WAVETABLE, waveform='sawtooth',
                description='Bright sawtooth wave'
            ),
            'square': Instrument(
                id='square', name='Square', category='synth',
                type=InstrumentType.WAVETABLE, waveform='square',
                description='Hollow square wave'
            ),
            'triangle': Instrument(
                id='triangle', name='Triangle', category='synth',
                type=InstrumentType.WAVETABLE, waveform='triangle',
                description='Soft triangle wave'
            ),
        }
        self.instruments = defaults
    
    def list_instruments(self, category: Optional[str] = None) -> List[Instrument]:
        """List all instruments, optionally filtered by category"""
        instruments = list(self.instruments.values())
        if category:
            instruments = [i for i in instruments if i.category == category]
        return instruments
    
    def list_categories(self) -> List[str]:
        """List all available categories"""
        return list(set(i.category for i in self.instruments.values()))
    
    def get_instrument(self, instrument_id: str) -> Optional[Instrument]:
        """Get an instrument by ID"""
        return self.instruments.get(instrument_id)
    
    def get_drum_kit(self, kit_id: str) -> Optional[DrumKit]:
        """Get a drum kit by ID"""
        return self.drum_kits.get(kit_id)
    
    def get_soundfont_path(self, filename: str) -> str:
        """Get full path to a soundfont file"""
        return os.path.join(self.instruments_dir, 'soundfonts', filename)
    
    def save_custom_instrument(self, instrument: Instrument) -> bool:
        """
        Save a custom instrument to the JSON file.
        
        Args:
            instrument: Instrument to save
            
        Returns:
            True if saved successfully
        """
        json_path = os.path.join(self.instruments_dir, 'instruments.json')
        
        # Load existing data
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {'instruments': {}, 'drum_kits': {}, 'categories': {}}
        
        # Add new instrument
        data['instruments'][instrument.id] = {
            'name': instrument.name,
            'category': instrument.category,
            'type': instrument.type.value,
            'description': instrument.description,
            'waveform': instrument.waveform,
            'envelope': {
                'attack': instrument.envelope.attack,
                'decay': instrument.envelope.decay,
                'sustain': instrument.envelope.sustain,
                'release': instrument.envelope.release
            },
            **instrument.params
        }
        
        # Add soundfont if present
        if instrument.soundfont:
            data['instruments'][instrument.id]['soundfont'] = instrument.soundfont
            data['instruments'][instrument.id]['bank'] = instrument.bank
            data['instruments'][instrument.id]['preset'] = instrument.preset
        
        # Save back
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Update in-memory
        self.instruments[instrument.id] = instrument
        
        return True


class AdvancedSynthesizer:
    """
    Advanced synthesizer that renders notes using instruments.
    Supports multiple synthesis types from instrument definitions.
    """
    
    def __init__(self, instrument_manager: InstrumentManager):
        self.manager = instrument_manager
        self._fluidsynth = None
        self._sfid = None
    
    def render(
        self,
        notes: List[Note],
        instrument: Instrument,
        sample_rate: int = 44100,
        duration: Optional[float] = None
    ) -> np.ndarray:
        """
        Render notes using the specified instrument.
        
        Args:
            notes: Notes to render
            instrument: Instrument to use
            sample_rate: Output sample rate
            duration: Total duration (None = auto)
            
        Returns:
            Audio array
        """
        if not notes:
            return np.array([])
        
        if duration is None:
            duration = max(n.start_time + n.duration for n in notes) + 1.0
        
        if instrument.type == InstrumentType.SOUNDFONT:
            return self._render_soundfont(notes, instrument, sample_rate, duration)
        elif instrument.type == InstrumentType.KARPLUS_STRONG:
            return self._render_karplus_strong(notes, instrument, sample_rate, duration)
        else:
            return self._render_wavetable(notes, instrument, sample_rate, duration)
    
    def _render_wavetable(
        self,
        notes: List[Note],
        instrument: Instrument,
        sr: int,
        duration: float
    ) -> np.ndarray:
        """Render using wavetable synthesis"""
        from .scales import midi_to_hz
        
        num_samples = int(duration * sr)
        audio = np.zeros(num_samples, dtype=np.float32)
        env = instrument.envelope
        
        for note in notes:
            if note.note_type == NoteType.PERCUSSIVE:
                continue
            
            freq = note.pitch_hz or midi_to_hz(note.midi_note)
            note_duration = note.duration + env.release
            note_samples = int(note_duration * sr)
            t = np.linspace(0, note_duration, note_samples, dtype=np.float32)
            
            # Generate waveform
            wave = self._generate_waveform(instrument.waveform, freq, t)
            
            # Apply ADSR envelope
            envelope = self._adsr(note_samples, note.duration, env, sr)
            wave *= envelope * (note.velocity / 127.0)
            
            # Mix into output
            start = int(note.start_time * sr)
            end = min(start + len(wave), num_samples)
            audio[start:end] += wave[:end - start]
        
        # Normalize
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = audio / max_val * 0.8
        
        return audio
    
    def _render_karplus_strong(
        self,
        notes: List[Note],
        instrument: Instrument,
        sr: int,
        duration: float
    ) -> np.ndarray:
        """Render using Karplus-Strong physical modeling"""
        from .scales import midi_to_hz
        
        num_samples = int(duration * sr)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        damping = instrument.params.get('damping', 0.5)
        brightness = instrument.params.get('brightness', 0.7)
        
        for note in notes:
            freq = note.pitch_hz or midi_to_hz(note.midi_note)
            note_samples = int((note.duration + 0.5) * sr)
            
            # Delay line length
            delay_length = int(sr / freq)
            if delay_length < 2:
                continue
            
            # Initialize with noise burst
            delay_line = np.random.randn(delay_length).astype(np.float32) * 0.5
            wave = np.zeros(note_samples, dtype=np.float32)
            
            # Karplus-Strong algorithm
            idx = 0
            for i in range(note_samples):
                wave[i] = delay_line[idx]
                avg = (delay_line[idx] + delay_line[(idx + 1) % delay_length]) / 2
                delay_line[idx] = avg * (1 - damping * 0.01)
                idx = (idx + 1) % delay_length
            
            wave *= (note.velocity / 127.0)
            
            # Mix
            start = int(note.start_time * sr)
            end = min(start + len(wave), num_samples)
            audio[start:end] += wave[:end - start]
        
        # Normalize
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = audio / max_val * 0.8
        
        return audio
    
    def _render_soundfont(
        self,
        notes: List[Note],
        instrument: Instrument,
        sr: int,
        duration: float
    ) -> np.ndarray:
        """Render using FluidSynth and SoundFont"""
        try:
            import fluidsynth
        except ImportError:
            # Fallback to wavetable
            return self._render_wavetable(notes, instrument, sr, duration)
        
        sf_path = self.manager.get_soundfont_path(instrument.soundfont)
        if not os.path.exists(sf_path):
            return self._render_wavetable(notes, instrument, sr, duration)
        
        # Initialize FluidSynth
        fs = fluidsynth.Synth()
        fs.start()
        sfid = fs.sfload(sf_path)
        fs.program_select(0, sfid, instrument.bank, instrument.preset)
        
        num_samples = int(duration * sr)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        # Create events
        events = []
        for note in notes:
            events.append((note.start_time, 'on', note.midi_note, note.velocity))
            events.append((note.start_time + note.duration, 'off', note.midi_note, 0))
        events.sort(key=lambda e: e[0])
        
        # Render
        current_time = 0.0
        current_sample = 0
        
        for event_time, event_type, midi_note, velocity in events:
            samples_to_render = int((event_time - current_time) * sr)
            if samples_to_render > 0:
                segment = fs.get_samples(samples_to_render)
                if len(segment) > 0:
                    stereo = np.frombuffer(segment, dtype=np.int16).reshape(-1, 2)
                    mono = stereo.mean(axis=1).astype(np.float32) / 32768.0
                    end = min(current_sample + len(mono), num_samples)
                    audio[current_sample:end] = mono[:end - current_sample]
                    current_sample = end
                current_time = event_time
            
            if event_type == 'on':
                fs.noteon(0, midi_note, velocity)
            else:
                fs.noteoff(0, midi_note)
        
        # Render remaining
        remaining = num_samples - current_sample
        if remaining > 0:
            segment = fs.get_samples(remaining)
            if len(segment) > 0:
                stereo = np.frombuffer(segment, dtype=np.int16).reshape(-1, 2)
                mono = stereo.mean(axis=1).astype(np.float32) / 32768.0
                audio[current_sample:current_sample + len(mono)] = mono
        
        fs.delete()
        return audio
    
    def _generate_waveform(self, waveform: str, freq: float, t: np.ndarray) -> np.ndarray:
        """Generate a waveform"""
        if waveform == 'sine':
            return np.sin(2 * np.pi * freq * t)
        elif waveform == 'square':
            return np.sign(np.sin(2 * np.pi * freq * t))
        elif waveform == 'sawtooth':
            return 2 * (t * freq % 1) - 1
        elif waveform == 'triangle':
            return 2 * np.abs(2 * (t * freq % 1) - 1) - 1
        else:
            return np.sin(2 * np.pi * freq * t)
    
    def _adsr(self, num_samples: int, note_duration: float, env: Envelope, sr: int) -> np.ndarray:
        """Generate ADSR envelope"""
        envelope = np.ones(num_samples, dtype=np.float32)
        
        attack_samples = int(env.attack * sr)
        decay_samples = int(env.decay * sr)
        release_samples = int(env.release * sr)
        sustain_samples = max(0, int(note_duration * sr) - attack_samples - decay_samples)
        
        idx = 0
        
        if attack_samples > 0 and idx < num_samples:
            end = min(idx + attack_samples, num_samples)
            envelope[idx:end] = np.linspace(0, 1, end - idx)
            idx = end
        
        if decay_samples > 0 and idx < num_samples:
            end = min(idx + decay_samples, num_samples)
            envelope[idx:end] = np.linspace(1, env.sustain, end - idx)
            idx = end
        
        if sustain_samples > 0 and idx < num_samples:
            end = min(idx + sustain_samples, num_samples)
            envelope[idx:end] = env.sustain
            idx = end
        
        if idx < num_samples:
            envelope[idx:] = np.linspace(env.sustain, 0, num_samples - idx)
        
        return envelope
