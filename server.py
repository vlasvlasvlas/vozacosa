#!/usr/bin/env python3
"""
VozACosa - Web GUI Backend
Flask server that provides API for the frontend
"""
import os
import json
import base64
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import numpy as np
from scipy.io import wavfile

# Import vozacosa modules
from vozacosa.recorder import AudioRecorder
from vozacosa.analyzer import PitchAnalyzer, load_audio_file
from vozacosa.synthesizer import SimpleSynthesizer
from vozacosa.instruments import InstrumentManager, AdvancedSynthesizer
from vozacosa.exporter import Exporter
from vozacosa.models import QuantizationConfig, ExportConfig, Note, NoteType
from vozacosa.scales import SCALES, SCALE_INTERVALS, MIDI_TO_NOTE, midi_to_note_name, NOTE_TO_MIDI
from vozacosa.session import SessionManager, detect_key, DetectedNote, logger
from vozacosa.calibration import calibration_manager

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

# Global instances
session_manager = SessionManager()
instrument_manager = InstrumentManager('instruments')

# Cache of analyzers by model capacity
_analyzers = {}

def get_analyzer(model_capacity: str = 'medium'):
    """
    Get or create a PitchAnalyzer with the specified CREPE model.
    
    Models:
    - 'tiny': 5K params, fastest, least accurate
    - 'small': 20K params, fast
    - 'medium': 80K params, balanced (default)
    - 'large': 320K params, accurate
    - 'full': 1.3M params, SOTA, most accurate but slowest
    """
    global _analyzers
    
    # Validate model capacity
    valid_models = ['tiny', 'small', 'medium', 'large', 'full']
    if model_capacity not in valid_models:
        model_capacity = 'medium'
    
    if model_capacity not in _analyzers:
        print(f"🧠 Loading CREPE model: {model_capacity}")
        _analyzers[model_capacity] = PitchAnalyzer(
            model_capacity=model_capacity,
            step_size=10,  # 10ms steps for precise timing
            confidence_threshold=0.25,  # Bajo para capturar notas sutiles
            min_note_duration=0.05  # 50ms minimum note
        )
    
    return _analyzers[model_capacity]


@app.route('/')
def index():
    return send_from_directory('web', 'index.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '0.1.0'})


@app.route('/api/scales')
def get_scales():
    """Get available scales"""
    scales = []
    for name in SCALES:
        intervals = SCALE_INTERVALS[name]
        notes = [MIDI_TO_NOTE[i] for i in intervals]
        scales.append({
            'id': name,
            'name': name.replace('_', ' ').title(),
            'intervals': intervals,
            'notes': notes
        })
    return jsonify(scales)


@app.route('/api/instruments')
def get_instruments():
    """Get available instruments"""
    instruments = []
    for inst in instrument_manager.list_instruments():
        instruments.append({
            'id': inst.id,
            'name': inst.name,
            'category': inst.category,
            'type': inst.type.value,
            'description': inst.description
        })
    return jsonify(instruments)


@app.route('/api/sessions')
def get_sessions():
    """Get saved sessions"""
    return jsonify(session_manager.list_sessions())


@app.route('/api/sessions/<session_id>', methods=['GET', 'DELETE'])
def handle_session(session_id):
    """Get or delete a specific session"""
    if request.method == 'DELETE':
        success = session_manager.delete_session(session_id)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to delete session'}), 400
        
    session = session_manager.load_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify(session.to_dict())


@app.route('/api/analyze', methods=['POST'])
def analyze_audio():
    """
    Analyze uploaded audio file
    Expects: multipart/form-data with 'audio' file
    """
    import time
    start_time = time.time()
    
    print("=" * 50)
    print("🎤 ANALYZE: Starting analysis...")
    
    if 'audio' not in request.files:
        print("❌ ANALYZE: No audio file in request")
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    scale = request.form.get('scale', 'auto')
    tolerance = int(request.form.get('tolerance', 25))
    crepe_model = request.form.get('crepe_model', 'medium')
    
    print(f"📁 ANALYZE: Got file, scale={scale}, tolerance={tolerance}, model={crepe_model}")
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name
    
    print(f"💾 ANALYZE: Saved temp file: {tmp_path} ({time.time() - start_time:.2f}s)")
    
    try:
        # Create session
        session = session_manager.create_session()
        session.input_type = 'upload'
        print(f"📂 ANALYZE: Created session {session.id} ({time.time() - start_time:.2f}s)")
        
        # Load audio
        print(f"🔊 ANALYZE: Loading audio file...")
        recording = load_audio_file(tmp_path)
        session.input_duration = recording.duration
        session.input_sample_rate = recording.sample_rate
        print(f"✓ ANALYZE: Audio loaded: {recording.duration:.1f}s at {recording.sample_rate}Hz ({time.time() - start_time:.2f}s)")
        
        # Save original
        original_path = os.path.join(session.output_dir, 'original.wav')
        wavfile.write(original_path, recording.sample_rate, 
                      (recording.audio * 32767).astype(np.int16))
        session.original_audio_file = original_path
        print(f"💾 ANALYZE: Saved original.wav ({time.time() - start_time:.2f}s)")
        
        # Configure quantization
        quant_config = QuantizationConfig(
            scale=None if scale == 'auto' else scale,
            root_note='C',
            tolerance_cents=tolerance
        )
        
        # Analyze with CREPE
        print(f"🧠 ANALYZE: Starting CREPE with model '{crepe_model}' (this may take a moment)...")
        result = get_analyzer(crepe_model).analyze(recording, quant_config)
        print(f"✓ ANALYZE: CREPE done! Found {len(result.notes)} notes ({time.time() - start_time:.2f}s)")
        
        if not result.notes:
            return jsonify({
                'error': 'No notes detected',
                'session_id': session.id
            }), 400
        
        # Auto-detect key if needed
        if scale == 'auto':
            detected_key = detect_key(result.notes)
            session.detected_key = detected_key
            session.scale_detected = True
        
        # Store notes in session
        notes_data = []
        for note in result.notes:
            note_data = {
                'midi_note': int(note.midi_note),
                'note_name': midi_to_note_name(note.midi_note),
                'start_time': float(note.start_time),
                'duration': float(note.duration),
                'velocity': int(note.velocity),
                'confidence': float(note.confidence),
                'original_hz': float(note.original_pitch_hz) if note.original_pitch_hz else None,
                'quantized_hz': float(note.pitch_hz) if note.pitch_hz else None
            }
            notes_data.append(note_data)
            session.detected_notes.append(DetectedNote(**note_data, cents_deviation=0))
        
        session.detected_tempo = float(result.tempo) if result.tempo else None
        session.is_percussive = result.is_percussive
        session.status = 'analyzed'
        
        # Generate waveform data for visualization (downsampled)
        waveform = recording.audio[::max(1, len(recording.audio) // 1000)].tolist()
        
        # Save session
        session_manager.save_session()
        
        return jsonify({
            'session_id': session.id,
            'duration': float(recording.duration),
            'notes': notes_data,
            'tempo': float(result.tempo) if result.tempo else None,
            'is_percussive': bool(result.is_percussive),
            'detected_key': session.detected_key,
            'waveform': [float(x) for x in waveform],
            # Return pitch track for visualization (time, freq)
            # Filter out low confidence points and downsample
            'pitch_track': [
                {'t': float(t), 'f': float(f)} 
                for t, f, c in zip(result.onset_times if result.is_percussive else np.linspace(0, recording.duration, len(result.pitch_track)), 
                                 result.pitch_track, 
                                 result.confidence_track)
                if c > 0.4  # Only return confident points
            ][::2] # Downsample slightly
        })
        

        
    finally:
        os.unlink(tmp_path)


@app.route('/api/sessions/<session_id>/reanalyze', methods=['POST'])
def reanalyze_session(session_id):
    """
    Re-quantize existing session notes to a new key/scale.
    Does NOT re-run CREPE, just maps original Hz to new scale.
    """
    try:
        data = request.json
        root_note = data.get('root_note')
        scale_type = data.get('scale_type')
        
        if not root_note or not scale_type:
            return jsonify({'error': 'Missing root_note or scale_type'}), 400
            
        session = session_manager.load_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
            
        print(f"🔄 RE-ANALYZE: Session {session_id} -> {root_note} {scale_type}")
        
        # We need the set of allowed MIDI notes (0-11) for this scale
        from vozacosa.scales import get_scale_notes, quantize_to_scale, hz_to_midi, midi_to_hz, SCALE_INTERVALS
        
        # Validation
        if scale_type not in SCALE_INTERVALS:
             return jsonify({'error': f'Invalid scale type: {scale_type}'}), 400
        
        target_scale_notes = get_scale_notes(root_note, scale_type)
        
        target_scale_notes = get_scale_notes(root_note, scale_type)
        
        updated_notes = []
        for note in session.detected_notes:
            note_name = note.note_name
            midi_note = note.midi_note
            quantized_hz = note.quantized_hz

            if note.original_hz:
                try:
                    # Re-quantize
                    midi_float = hz_to_midi(note.original_hz)
                    # Use 50 cents detection tolerance for re-quantization
                    midi_quantized = quantize_to_scale(midi_float, target_scale_notes, 50)
                    quantized_hz = midi_to_hz(midi_quantized)
                    midi_note = midi_quantized
                    note_name = midi_to_note_name(midi_quantized)
                    
                    # Update session note object in place
                    note.midi_note = midi_quantized
                    note.quantized_hz = quantized_hz
                    note.note_name = note_name
                except Exception as e:
                    print(f"⚠️ Warning processing note: {e}")
            
            updated_notes.append({
                'midi_note': int(midi_note),
                'note_name': note_name,
                'start_time': float(note.start_time),
                'duration': float(note.duration),
                'velocity': int(note.velocity),
                'confidence': float(note.confidence),
                'original_hz': float(note.original_hz) if note.original_hz else None,
                'quantized_hz': float(quantized_hz) if quantized_hz else None
            })
            
        session.detected_key = f"{root_note} {scale_type.replace('_', ' ')}"
        session.scale_detected = True # User manually set it
        session_manager.save_session()
        
        return jsonify({
            'success': True,
            'session_id': session.id,
            'detected_key': session.detected_key,
            'notes': updated_notes,
            'notes_count': len(updated_notes)
        })
        
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"❌ ERROR IN /reanalyze:\n{error_msg}")
        return jsonify({'error': str(e), 'details': error_msg}), 500
    session.scale_detected = True # User manually set it
    session_manager.save_session()
    
    return jsonify({
        'success': True,
        'session_id': session.id,
        'detected_key': session.detected_key,
        'notes': updated_notes,
        'notes_count': len(updated_notes)
    })



@app.route('/api/synthesize', methods=['POST'])
def synthesize():
    """
    Synthesize notes with an instrument
    Expects JSON: {session_id, instrument_id}
    """
    data = request.json
    session_id = data.get('session_id')
    instrument_id = data.get('instrument_id', 'synth_lead')
    
    session = session_manager.load_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    instrument = instrument_manager.get_instrument(instrument_id)
    if not instrument:
        return jsonify({'error': 'Instrument not found'}), 404
    
    # Rebuild notes from session
    notes = []
    for n in session.detected_notes:
        notes.append(Note(
            pitch_hz=n.quantized_hz,
            midi_note=n.midi_note,
            start_time=n.start_time,
            duration=n.duration,
            velocity=n.velocity,
            confidence=n.confidence,
            note_type=NoteType.MELODIC
        ))
    
    # Synthesize
    synth = AdvancedSynthesizer(instrument_manager)
    audio = synth.render(notes, instrument, sample_rate=44100)
    
    # Save
    session.instrument_id = instrument_id
    session.instrument_name = instrument.name
    
    wav_path = os.path.join(session.output_dir, f'synth_{instrument_id}.wav')
    audio_int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    wavfile.write(wav_path, 44100, audio_int16)
    session.synth_wav_file = wav_path
    
    # Export MIDI
    exporter = Exporter(ExportConfig(output_dir=session.output_dir))
    from vozacosa.models import AnalysisResult
    result = AnalysisResult(notes=notes)
    midi_path = exporter.export_midi(notes, os.path.join(session.output_dir, 'output.mid'))
    session.midi_file = midi_path
    
    session.status = 'completed'
    session_manager.current_session = session
    session_manager.save_session()
    
    return jsonify({
        'success': True,
        'wav_file': os.path.basename(wav_path),
        'midi_file': os.path.basename(midi_path)
    })


@app.route('/api/sessions/<session_id>/audio/<filename>')
def get_audio_file(session_id, filename):
    """Serve audio file from session"""
    session_dir = os.path.join('sessions', session_id)
    return send_from_directory(session_dir, filename)


@app.route('/api/sessions/<session_id>/notes', methods=['PUT'])
def update_session_notes(session_id):
    """
    Update notes for a session (from Piano Roll editor).
    Expects JSON: {notes: [{midi_note, note_name, start_time, duration, velocity, ...}, ...]}
    """
    try:
        data = request.json
        notes = data.get('notes', [])
        
        session = session_manager.load_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Update session notes
        session.detected_notes = []
        for n in notes:
            session.detected_notes.append(DetectedNote(
                midi_note=n.get('midi_note', 60),
                note_name=n.get('note_name', 'C4'),
                start_time=n.get('start_time', 0),
                duration=n.get('duration', 0.5),
                velocity=n.get('velocity', 100),
                confidence=n.get('confidence', 1.0),
                original_hz=n.get('original_hz'),
                quantized_hz=n.get('quantized_hz'),
                cents_deviation=n.get('cents_deviation', 0)
            ))
        
        session_manager.current_session = session
        session_manager.save_session()
        
        return jsonify({
            'success': True,
            'notes_count': len(session.detected_notes)
        })
        
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"❌ ERROR IN /notes PUT:\n{error_msg}")
        return jsonify({'error': str(e)}), 500


@app.route('/output/<path:filename>')
def get_output_file(filename):
    """Serve files from output directory (for previews)"""
    return send_from_directory('output', filename)


@app.route('/api/test-instrument', methods=['POST'])
def test_instrument():
    """Test an instrument with specific notes"""
    data = request.json
    instrument_id = data.get('instrument_id', 'synth_lead')
    notes_str = data.get('notes', 'C4,E4,G4,C5')
    
    instrument = instrument_manager.get_instrument(instrument_id)
    if not instrument:
        return jsonify({'error': 'Instrument not found'}), 404
    
    # Parse notes
    note_list = []
    time = 0.0
    for note_str in notes_str.split(','):
        note_str = note_str.strip()
        if len(note_str) >= 2:
            note_name = note_str[:-1] if note_str[-1].isdigit() else note_str
            octave = int(note_str[-1]) if note_str[-1].isdigit() else 4
            base_midi = NOTE_TO_MIDI.get(note_name, 60)
            midi_note = (base_midi % 12) + (octave + 1) * 12
            note_list.append(Note(
                pitch_hz=None, midi_note=midi_note,
                start_time=time, duration=0.4,
                velocity=100, note_type=NoteType.MELODIC
            ))
            time += 0.5
    
    synth = AdvancedSynthesizer(instrument_manager)
    audio = synth.render(note_list, instrument, sample_rate=44100)
    
    # Convert to base64 for immediate playback
    audio_int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    
    # Save to output
    os.makedirs('output', exist_ok=True)
    output_path = f'output/test_{instrument_id}.wav'
    wavfile.write(output_path, 44100, audio_int16)
    
    return jsonify({
        'success': True,
        'file': output_path,
        'duration': len(audio) / 44100
    })


if __name__ == '__main__':
    print("\n🎤 VozACosa Web GUI")
    print("=" * 40)
    print("Opening: http://localhost:5001")
    print("=" * 40)
    
    import webbrowser
    webbrowser.open('http://localhost:5001')
    
    app.run(debug=True, port=5001)


# ========== CALIBRATION ENDPOINTS ==========

@app.route('/api/calibration/status')
def get_calibration_status():
    """Get current calibration profile status"""
    stats = calibration_manager.get_profile_stats()
    return jsonify(stats)


@app.route('/api/calibration/examples')
def list_calibration_examples():
    """List all calibration examples"""
    examples = calibration_manager.list_examples()
    return jsonify(examples)


@app.route('/api/calibration/add', methods=['POST'])
def add_calibration_example():
    """
    Add a calibration example from a session.
    Uses the original detected notes and user-corrected notes.
    """
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        session = session_manager.load_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get original and corrected notes from session
        # The corrected notes are the current detected_notes (after user edits)
        corrected_notes = [
            {
                'midi_note': n.midi_note,
                'note_name': n.note_name,
                'start_time': n.start_time,
                'duration': n.duration,
                'velocity': n.velocity,
                'confidence': n.confidence,
                'original_hz': n.original_hz
            }
            for n in session.detected_notes
        ]
        
        # For original notes, we need the original_hz to recalculate
        # Since we don't store "pre-correction" notes separately,
        # we'll use the original_hz to estimate original MIDI
        from vozacosa.scales import hz_to_midi, midi_to_note_name
        original_notes = []
        for n in session.detected_notes:
            if n.original_hz:
                orig_midi = round(hz_to_midi(n.original_hz))
                original_notes.append({
                    'midi_note': orig_midi,
                    'note_name': midi_to_note_name(orig_midi),
                    'start_time': n.start_time,
                    'duration': n.duration,
                    'velocity': n.velocity,
                    'confidence': n.confidence,
                    'original_hz': n.original_hz
                })
        
        if not original_notes:
            return jsonify({'error': 'No original pitch data in session'}), 400
        
        # Add calibration example
        example = calibration_manager.add_example(
            audio_file=session.original_audio_file or '',
            duration=session.input_duration,
            original_notes=original_notes,
            corrected_notes=corrected_notes,
            scale_used=session.scale_name,
            root_note=session.scale_root
        )
        
        return jsonify({
            'success': True,
            'example_id': example.id,
            'pitch_offset_cents': example.pitch_offset_cents,
            'timing_offset_ms': example.timing_offset_ms,
            'profile_stats': calibration_manager.get_profile_stats()
        })
        
    except Exception as e:
        import traceback
        print(f"❌ ERROR adding calibration: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/calibration/apply', methods=['POST'])
def apply_calibration():
    """
    Apply calibration to a session's notes.
    """
    try:
        data = request.json
        session_id = data.get('session_id')
        
        session = session_manager.load_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get current notes as dicts
        notes = [
            {
                'midi_note': n.midi_note,
                'note_name': n.note_name,
                'start_time': n.start_time,
                'duration': n.duration,
                'velocity': n.velocity,
                'confidence': n.confidence,
                'original_hz': n.original_hz,
                'quantized_hz': n.quantized_hz
            }
            for n in session.detected_notes
        ]
        
        # Apply calibration
        calibrated = calibration_manager.apply_calibration(notes)
        
        # Update session
        session.detected_notes = [
            DetectedNote(
                midi_note=n['midi_note'],
                note_name=n['note_name'],
                start_time=n['start_time'],
                duration=n['duration'],
                velocity=n['velocity'],
                confidence=n['confidence'],
                original_hz=n.get('original_hz'),
                quantized_hz=n.get('quantized_hz'),
                cents_deviation=0
            )
            for n in calibrated
        ]
        
        session_manager.current_session = session
        session_manager.save_session()
        
        return jsonify({
            'success': True,
            'notes': calibrated,
            'notes_count': len(calibrated)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/calibration/reset', methods=['POST'])
def reset_calibration():
    """Reset calibration to defaults"""
    calibration_manager.reset_calibration()
    return jsonify({
        'success': True,
        'profile_stats': calibration_manager.get_profile_stats()
    })
