"""
Calibration system for VozACosa.
Stores user-corrected examples to improve pitch detection accuracy.

This doesn't retrain CREPE (which is not possible), but:
1. Learns user's pitch offset (some people sing consistently sharp/flat)
2. Learns preferred quantization patterns
3. Stores reference examples for comparison
"""
import os
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

logger = logging.getLogger('vozacosa.calibration')


@dataclass
class CalibrationExample:
    """A single calibration example: audio with corrected notes"""
    id: str
    created_at: str
    audio_file: str  # Path to audio file
    duration: float
    
    # Original detection
    original_notes: List[Dict]  # As detected by CREPE
    
    # User corrections
    corrected_notes: List[Dict]  # After user edits
    
    # Computed offset
    pitch_offset_cents: float = 0.0  # Average pitch offset
    timing_offset_ms: float = 0.0  # Average timing offset
    
    # Metadata
    scale_used: Optional[str] = None
    root_note: Optional[str] = None
    

@dataclass
class CalibrationProfile:
    """
    User's calibration profile.
    Aggregates learning from multiple examples.
    """
    id: str = "default"
    created_at: str = ""
    updated_at: str = ""
    
    # Learned parameters
    global_pitch_offset_cents: float = 0.0  # User tends to sing X cents sharp/flat
    global_timing_offset_ms: float = 0.0  # User's notes start X ms early/late
    
    # Per-note corrections (some people are flat on high notes, sharp on low)
    pitch_offset_by_octave: Dict[int, float] = field(default_factory=dict)  # octave -> cents offset
    
    # Confidence adjustments
    min_confidence_learned: float = 0.35  # Learned optimal confidence threshold
    
    # Statistics
    num_examples: int = 0
    total_notes_corrected: int = 0
    
    # Example IDs
    example_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CalibrationProfile':
        return cls(**data)


class CalibrationManager:
    """
    Manages calibration examples and profiles.
    """
    
    def __init__(self, calibration_dir: str = "calibration"):
        self.calibration_dir = calibration_dir
        self.examples_dir = os.path.join(calibration_dir, "examples")
        self.profiles_dir = os.path.join(calibration_dir, "profiles")
        
        os.makedirs(self.examples_dir, exist_ok=True)
        os.makedirs(self.profiles_dir, exist_ok=True)
        
        self.current_profile: Optional[CalibrationProfile] = None
        self._load_default_profile()
    
    def _load_default_profile(self):
        """Load or create default profile"""
        profile_path = os.path.join(self.profiles_dir, "default.json")
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                data = json.load(f)
                self.current_profile = CalibrationProfile.from_dict(data)
        else:
            self.current_profile = CalibrationProfile(
                id="default",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            self._save_profile(self.current_profile)
    
    def _save_profile(self, profile: CalibrationProfile):
        """Save profile to disk"""
        profile_path = os.path.join(self.profiles_dir, f"{profile.id}.json")
        with open(profile_path, 'w') as f:
            json.dump(profile.to_dict(), f, indent=2)
    
    def add_example(
        self,
        audio_file: str,
        duration: float,
        original_notes: List[Dict],
        corrected_notes: List[Dict],
        scale_used: Optional[str] = None,
        root_note: Optional[str] = None
    ) -> CalibrationExample:
        """
        Add a calibration example and update the profile.
        """
        example_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Calculate offsets
        pitch_offset, timing_offset = self._calculate_offsets(original_notes, corrected_notes)
        
        example = CalibrationExample(
            id=example_id,
            created_at=datetime.now().isoformat(),
            audio_file=audio_file,
            duration=duration,
            original_notes=original_notes,
            corrected_notes=corrected_notes,
            pitch_offset_cents=pitch_offset,
            timing_offset_ms=timing_offset,
            scale_used=scale_used,
            root_note=root_note
        )
        
        # Save example
        example_path = os.path.join(self.examples_dir, f"{example_id}.json")
        with open(example_path, 'w') as f:
            json.dump(asdict(example), f, indent=2)
        
        # Update profile
        self._update_profile_with_example(example)
        
        logger.info(f"Added calibration example {example_id}: pitch_offset={pitch_offset:.1f}¢, timing_offset={timing_offset:.1f}ms")
        
        return example
    
    def _calculate_offsets(
        self,
        original_notes: List[Dict],
        corrected_notes: List[Dict]
    ) -> Tuple[float, float]:
        """
        Calculate average pitch and timing offsets between original and corrected notes.
        """
        if not original_notes or not corrected_notes:
            return 0.0, 0.0
        
        pitch_diffs = []
        timing_diffs = []
        
        # Match notes by time proximity
        for orig in original_notes:
            # Find closest corrected note
            orig_start = orig.get('start_time', 0)
            orig_midi = orig.get('midi_note', 60)
            
            best_match = None
            best_dist = float('inf')
            
            for corr in corrected_notes:
                corr_start = corr.get('start_time', 0)
                dist = abs(corr_start - orig_start)
                if dist < best_dist and dist < 0.5:  # Within 500ms
                    best_dist = dist
                    best_match = corr
            
            if best_match:
                # Pitch difference in cents (100 cents = 1 semitone)
                corr_midi = best_match.get('midi_note', 60)
                pitch_diff = (corr_midi - orig_midi) * 100  # Convert semitones to cents
                pitch_diffs.append(pitch_diff)
                
                # Timing difference
                timing_diff = (best_match.get('start_time', 0) - orig_start) * 1000  # ms
                timing_diffs.append(timing_diff)
        
        avg_pitch = np.mean(pitch_diffs) if pitch_diffs else 0.0
        avg_timing = np.mean(timing_diffs) if timing_diffs else 0.0
        
        return float(avg_pitch), float(avg_timing)
    
    def _update_profile_with_example(self, example: CalibrationExample):
        """Update the current profile with a new example"""
        if not self.current_profile:
            return
        
        profile = self.current_profile
        
        # Exponential moving average for offsets
        alpha = 0.3  # Weight for new example
        profile.global_pitch_offset_cents = (
            (1 - alpha) * profile.global_pitch_offset_cents +
            alpha * example.pitch_offset_cents
        )
        profile.global_timing_offset_ms = (
            (1 - alpha) * profile.global_timing_offset_ms +
            alpha * example.timing_offset_ms
        )
        
        # Update per-octave offsets
        for note in example.corrected_notes:
            midi = note.get('midi_note', 60)
            octave = midi // 12
            # Find corresponding original note offset
            for orig in example.original_notes:
                if abs(orig.get('start_time', 0) - note.get('start_time', 0)) < 0.3:
                    offset = (note.get('midi_note', 60) - orig.get('midi_note', 60)) * 100
                    if octave not in profile.pitch_offset_by_octave:
                        profile.pitch_offset_by_octave[octave] = offset
                    else:
                        profile.pitch_offset_by_octave[octave] = (
                            0.7 * profile.pitch_offset_by_octave[octave] + 0.3 * offset
                        )
                    break
        
        # Update stats
        profile.num_examples += 1
        profile.total_notes_corrected += len(example.corrected_notes)
        profile.example_ids.append(example.id)
        profile.updated_at = datetime.now().isoformat()
        
        self._save_profile(profile)
    
    def apply_calibration(self, notes: List[Dict]) -> List[Dict]:
        """
        Apply learned calibration to detected notes.
        This adjusts pitch based on learned user patterns.
        """
        if not self.current_profile or self.current_profile.num_examples == 0:
            return notes  # No calibration data yet
        
        profile = self.current_profile
        calibrated = []
        
        for note in notes:
            midi = note.get('midi_note', 60)
            octave = midi // 12
            
            # Calculate total offset
            total_offset_cents = profile.global_pitch_offset_cents
            if octave in profile.pitch_offset_by_octave:
                total_offset_cents += profile.pitch_offset_by_octave[octave]
            
            # Apply offset (convert cents to semitones)
            semitone_offset = round(total_offset_cents / 100)
            
            new_note = note.copy()
            new_note['midi_note'] = midi + semitone_offset
            
            # Recalculate note name
            note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            new_midi = new_note['midi_note']
            new_note['note_name'] = f"{note_names[new_midi % 12]}{(new_midi // 12) - 1}"
            
            # Apply timing offset
            if profile.global_timing_offset_ms != 0:
                new_note['start_time'] = max(0, note.get('start_time', 0) + profile.global_timing_offset_ms / 1000)
            
            calibrated.append(new_note)
        
        return calibrated
    
    def get_profile_stats(self) -> Dict:
        """Get current profile statistics"""
        if not self.current_profile:
            return {}
        
        p = self.current_profile
        return {
            'num_examples': p.num_examples,
            'total_notes_corrected': p.total_notes_corrected,
            'global_pitch_offset_cents': round(p.global_pitch_offset_cents, 1),
            'global_timing_offset_ms': round(p.global_timing_offset_ms, 1),
            'pitch_offset_by_octave': {k: round(v, 1) for k, v in p.pitch_offset_by_octave.items()},
            'is_calibrated': p.num_examples > 0
        }
    
    def list_examples(self) -> List[Dict]:
        """List all calibration examples"""
        examples = []
        for filename in os.listdir(self.examples_dir):
            if filename.endswith('.json'):
                path = os.path.join(self.examples_dir, filename)
                with open(path, 'r') as f:
                    data = json.load(f)
                    examples.append({
                        'id': data['id'],
                        'created_at': data['created_at'],
                        'duration': data['duration'],
                        'num_notes': len(data.get('corrected_notes', [])),
                        'pitch_offset': data.get('pitch_offset_cents', 0),
                        'timing_offset': data.get('timing_offset_ms', 0)
                    })
        return sorted(examples, key=lambda x: x['created_at'], reverse=True)
    
    def reset_calibration(self):
        """Reset calibration profile to defaults"""
        self.current_profile = CalibrationProfile(
            id="default",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self._save_profile(self.current_profile)
        logger.info("Calibration profile reset")


# Global instance
calibration_manager = CalibrationManager()
