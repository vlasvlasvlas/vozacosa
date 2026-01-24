"""
Session manager for VozACosa.
Tracks all inputs, outputs, and processing steps as a project/session.
"""
import os
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path


# Configure logging
def setup_logging(log_dir: str = "logs") -> logging.Logger:
    """Setup logging to file and console"""
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"vozacosa_{datetime.now().strftime('%Y%m%d')}.log")
    
    logger = logging.getLogger('vozacosa')
    logger.setLevel(logging.DEBUG)
    
    # File handler (detailed)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Console handler (brief) - only warnings and errors
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


# Global logger
logger = setup_logging()


@dataclass
class ProcessingStep:
    """A single processing step in a session"""
    name: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str = "running"  # running, completed, failed
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class DetectedNote:
    """A detected note for JSON serialization"""
    midi_note: int
    note_name: str
    start_time: float
    duration: float
    velocity: int
    confidence: float
    original_hz: Optional[float] = None
    quantized_hz: Optional[float] = None
    cents_deviation: float = 0.0


@dataclass
class Session:
    """
    A recording/processing session that tracks all files and steps.
    This is the 'expediente' for each audio processed.
    """
    id: str
    created_at: str
    
    # Input
    input_type: str = "recording"  # recording, file
    input_file: Optional[str] = None
    input_duration: float = 0.0
    input_sample_rate: int = 22050
    
    # Analysis config
    scale_name: Optional[str] = None
    scale_root: Optional[str] = None
    scale_detected: bool = False  # True if auto-detected
    tolerance_cents: int = 25
    
    # Results
    detected_notes: List[DetectedNote] = field(default_factory=list)
    detected_tempo: Optional[float] = None
    is_percussive: bool = False
    detected_key: Optional[str] = None  # Auto-detected key
    
    # Output files
    output_dir: str = ""
    original_audio_file: Optional[str] = None
    midi_file: Optional[str] = None
    synth_wav_file: Optional[str] = None
    synth_mp3_file: Optional[str] = None
    
    # Instrument used
    instrument_id: Optional[str] = None
    instrument_name: Optional[str] = None
    
    # Processing steps
    steps: List[ProcessingStep] = field(default_factory=list)
    
    # Status
    status: str = "created"  # created, recording, analyzing, synthesizing, completed, failed
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'input_type': self.input_type,
            'input_file': self.input_file,
            'input_duration': self.input_duration,
            'input_sample_rate': self.input_sample_rate,
            'scale_name': self.scale_name,
            'scale_root': self.scale_root,
            'scale_detected': self.scale_detected,
            'tolerance_cents': self.tolerance_cents,
            'detected_notes': [asdict(n) for n in self.detected_notes],
            'detected_tempo': self.detected_tempo,
            'is_percussive': self.is_percussive,
            'detected_key': self.detected_key,
            'output_dir': self.output_dir,
            'original_audio_file': self.original_audio_file,
            'midi_file': self.midi_file,
            'synth_wav_file': self.synth_wav_file,
            'synth_mp3_file': self.synth_mp3_file,
            'instrument_id': self.instrument_id,
            'instrument_name': self.instrument_name,
            'steps': [asdict(s) for s in self.steps],
            'status': self.status
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """Create session from dictionary"""
        session = cls(
            id=data['id'],
            created_at=data['created_at']
        )
        for key, value in data.items():
            if key == 'detected_notes':
                session.detected_notes = [DetectedNote(**n) for n in value]
            elif key == 'steps':
                session.steps = [ProcessingStep(**s) for s in value]
            elif hasattr(session, key):
                setattr(session, key, value)
        return session


class SessionManager:
    """
    Manages sessions - creates, saves, loads, and updates.
    """
    
    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)
        self.current_session: Optional[Session] = None
        self._step_start_time: Optional[datetime] = None
    
    def create_session(self) -> Session:
        """Create a new session"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(self.sessions_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        session = Session(
            id=session_id,
            created_at=datetime.now().isoformat(),
            output_dir=session_dir
        )
        
        self.current_session = session
        logger.info(f"Created session: {session_id}")
        
        return session
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session path and its contents"""
        session_dir = os.path.join(self.sessions_dir, session_id)
        if not os.path.exists(session_dir):
            return False
            
        import shutil
        try:
            shutil.rmtree(session_dir)
            if self.current_session and self.current_session.id == session_id:
                self.current_session = None
            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def start_step(self, name: str, details: Dict[str, Any] = None) -> None:
        """Start a processing step"""
        if not self.current_session:
            return
        
        self._step_start_time = datetime.now()
        
        step = ProcessingStep(
            name=name,
            started_at=self._step_start_time.isoformat(),
            details=details or {}
        )
        
        self.current_session.steps.append(step)
        logger.info(f"Step started: {name}")
    
    def complete_step(self, details: Dict[str, Any] = None) -> float:
        """Complete the current step, returns duration in seconds"""
        if not self.current_session or not self.current_session.steps:
            return 0.0
        
        step = self.current_session.steps[-1]
        now = datetime.now()
        step.completed_at = now.isoformat()
        
        if self._step_start_time:
            step.duration_seconds = (now - self._step_start_time).total_seconds()
        
        step.status = "completed"
        
        if details:
            step.details.update(details)
        
        logger.info(f"Step completed: {step.name} ({step.duration_seconds:.2f}s)")
        
        return step.duration_seconds or 0.0
    
    def fail_step(self, error: str) -> None:
        """Mark current step as failed"""
        if not self.current_session or not self.current_session.steps:
            return
        
        step = self.current_session.steps[-1]
        step.completed_at = datetime.now().isoformat()
        step.status = "failed"
        step.error = error
        
        logger.error(f"Step failed: {step.name} - {error}")
    
    def save_session(self) -> str:
        """Save session to JSON file"""
        if not self.current_session:
            return ""
        
        session_file = os.path.join(
            self.current_session.output_dir,
            f"session_{self.current_session.id}.json"
        )
        
        # Custom encoder for numpy types
        import numpy as np
        
        def json_serializer(obj):
            if isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            if isinstance(obj, (np.int32, np.int64)):
                return int(obj)
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            # Fallback for any other numpy type
            if hasattr(obj, 'item'):
                return obj.item()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_session.to_dict(), f, indent=2, ensure_ascii=False, default=json_serializer)
        
        logger.info(f"Session saved: {session_file}")
        return session_file
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a session from disk"""
        session_dir = os.path.join(self.sessions_dir, session_id)
        session_file = os.path.join(session_dir, f"session_{session_id}.json")
        
        if not os.path.exists(session_file):
            return None
        
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        session = Session.from_dict(data)
        logger.info(f"Session loaded: {session_id}")
        return session
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions"""
        sessions = []
        
        for session_id in sorted(os.listdir(self.sessions_dir), reverse=True):
            session_dir = os.path.join(self.sessions_dir, session_id)
            if not os.path.isdir(session_dir):
                continue
            session_file = os.path.join(session_dir, f"session_{session_id}.json")
            if os.path.exists(session_file):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    sessions.append({
                        'id': data['id'],
                        'created_at': data['created_at'],
                        'status': data['status'],
                        'notes_count': len(data.get('detected_notes', [])),
                        'duration': data.get('input_duration', 0)
                    })
                except (json.JSONDecodeError, KeyError) as e:
                    # Skip corrupted sessions
                    logger.warning(f"Skipping corrupted session {session_id}: {e}")
                    continue
        
        return sessions


class ProgressTimer:
    """
    Context manager that shows elapsed time during long operations.
    """
    
    def __init__(self, message: str, show_spinner: bool = True):
        self.message = message
        self.show_spinner = show_spinner
        self.start_time: Optional[datetime] = None
        self._running = False
        self._thread = None
    
    def __enter__(self):
        import threading
        import sys
        
        self.start_time = datetime.now()
        self._running = True
        
        def spinner():
            chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            idx = 0
            while self._running:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                if self.show_spinner:
                    char = chars[idx % len(chars)]
                    sys.stdout.write(f"\r{char} {self.message} [{elapsed:.1f}s]   ")
                else:
                    sys.stdout.write(f"\r⏳ {self.message} [{elapsed:.1f}s]   ")
                sys.stdout.flush()
                idx += 1
                import time
                time.sleep(0.1)
        
        self._thread = threading.Thread(target=spinner, daemon=True)
        self._thread.start()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        
        elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        if exc_type:
            print(f"\r❌ {self.message} [FAILED after {elapsed:.1f}s]")
        else:
            print(f"\r✓ {self.message} [{elapsed:.1f}s]              ")
        
        return False
    
    @property
    def elapsed(self) -> float:
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0


def detect_key(notes: list, sample_rate: int = 22050) -> Optional[str]:
    """
    Auto-detect the musical key from detected notes.
    Returns the most likely key (e.g., 'C major', 'A minor')
    """
    if not notes:
        return None
    
    # Count pitch classes (0-11)
    pitch_counts = [0] * 12
    
    for note in notes:
        pc = note.midi_note % 12
        # Weight by duration and velocity
        weight = note.duration * (note.velocity / 127.0)
        pitch_counts[pc] += weight
    
    # Krumhansl-Schmuckler key profiles
    major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
    
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    best_key = None
    best_correlation = -1
    
    # Try each possible key
    for root in range(12):
        # Rotate pitch counts to match this root
        rotated = pitch_counts[root:] + pitch_counts[:root]
        
        # Correlate with major profile
        import numpy as np
        major_corr = np.corrcoef(rotated, major_profile)[0, 1]
        if major_corr > best_correlation:
            best_correlation = major_corr
            best_key = f"{note_names[root]} major"
        
        # Correlate with minor profile
        minor_corr = np.corrcoef(rotated, minor_profile)[0, 1]
        if minor_corr > best_correlation:
            best_correlation = minor_corr
            best_key = f"{note_names[root]} minor"
    
    return best_key
