#!/usr/bin/env python3
"""
VozACosa - App Interactiva v2
Con sesiones, logging, y progreso con tiempo
"""
import os
import sys

# Colores ANSI
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'

BANNER = f"""
{CYAN}{BOLD}
╦  ╦╔═╗╔═╗╔═╗╔═╗╔═╗╔═╗╔═╗
╚╗╔╝║ ║╔═╝╠═╣║  ║ ║╚═╗╠═╣
 ╚╝ ╚═╝╚═╝╩ ╩╚═╝╚═╝╚═╝╩ ╩
{RESET}{DIM}Voice to MIDI Converter - SOTA Pitch Detection{RESET}
"""

MENU = f"""
{BOLD}═══════════════════════════════════════{RESET}
{CYAN}[1]{RESET} 🎤 Grabar voz y convertir a MIDI
{CYAN}[2]{RESET} 🎹 Probar un instrumento
{CYAN}[3]{RESET} 📋 Ver instrumentos disponibles
{CYAN}[4]{RESET} 🎼 Ver escalas disponibles
{CYAN}[5]{RESET} 🎧 Ver dispositivos de audio
{CYAN}[6]{RESET} 📂 Convertir archivo de audio
{CYAN}[7]{RESET} 📁 Ver sesiones guardadas
{CYAN}[8]{RESET} 🔄 Recargar sesión anterior
{BOLD}═══════════════════════════════════════{RESET}
{CYAN}[0]{RESET} ❌ Salir
"""


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def pause():
    input(f"\n{DIM}Presiona ENTER para continuar...{RESET}")


def show_banner():
    print(BANNER)


def option_record():
    """Grabar voz y convertir a MIDI - CON SESIONES Y PROGRESO"""
    from vozacosa.recorder import AudioRecorder
    from vozacosa.analyzer import PitchAnalyzer
    from vozacosa.synthesizer import SimpleSynthesizer
    from vozacosa.exporter import Exporter
    from vozacosa.models import QuantizationConfig, ExportConfig
    from vozacosa.scales import midi_to_note_name
    from vozacosa.session import SessionManager, ProgressTimer, DetectedNote, detect_key, logger
    
    print(f"\n{BOLD}🎤 GRABAR Y CONVERTIR{RESET}\n")
    
    # Crear sesión
    sm = SessionManager()
    session = sm.create_session()
    print(f"{DIM}Sesión: {session.id}{RESET}")
    logger.info(f"Nueva grabación iniciada")
    
    # Configuración de escala
    print(f"\n{BOLD}Configuración de escala:{RESET}")
    print(f"  {DIM}Dejá vacío para AUTO-DETECTAR la tonalidad{RESET}")
    
    scale = input(f"Escala (major/minor/pentatonic/blues/auto) [{GREEN}auto{RESET}]: ").strip().lower() or 'auto'
    
    if scale == 'auto':
        session.scale_detected = True
        session.scale_name = None
        session.scale_root = None
        print(f"  {CYAN}→ Se auto-detectará la tonalidad de tu melodía{RESET}")
    else:
        root = input(f"Nota raíz [{GREEN}C{RESET}]: ").strip() or 'C'
        session.scale_name = scale
        session.scale_root = root
    
    tol = input(f"Tolerancia 0-50 [{GREEN}25{RESET}]: ").strip() or '25'
    session.tolerance_cents = int(tol)
    
    # Grabar
    recorder = AudioRecorder(sample_rate=22050)
    session.input_sample_rate = 22050
    
    print(f"\n{YELLOW}Presiona ENTER para iniciar la grabación...{RESET}")
    input()
    
    sm.start_step("recording")
    recorder.start()
    session.status = "recording"
    print(f"{RED}{BOLD}● GRABANDO{RESET} - Presiona ENTER para detener")
    
    import time
    import select
    try:
        while True:
            time.sleep(0.1)
            elapsed = recorder.elapsed_time
            print(f"\r{DIM}⏱ {elapsed:.1f}s{RESET}", end="", flush=True)
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()
                break
    except KeyboardInterrupt:
        pass
    
    recording = recorder.stop()
    duration = sm.complete_step({"duration": recording.duration})
    session.input_duration = recording.duration
    print(f"\n{GREEN}✓ Grabación completada: {recording.duration:.2f}s{RESET}")
    
    # Guardar audio original
    original_path = os.path.join(session.output_dir, "original.wav")
    recorder.save_wav(recording, original_path)
    session.original_audio_file = original_path
    logger.info(f"Audio guardado: {original_path}")
    
    # Analizar con CREPE - CON PROGRESO
    session.status = "analyzing"
    sm.start_step("pitch_analysis", {"model": "CREPE medium"})
    
    quant_config = QuantizationConfig(
        scale=session.scale_name,
        root_note=session.scale_root or 'C',
        tolerance_cents=session.tolerance_cents
    )
    
    analyzer = PitchAnalyzer(model_capacity='medium')
    
    with ProgressTimer("Analizando pitch con CREPE"):
        result = analyzer.analyze(recording, quant_config)
    
    sm.complete_step({
        "notes_detected": result.num_notes,
        "is_percussive": result.is_percussive,
        "tempo": result.tempo
    })
    
    if not result.notes:
        session.status = "failed"
        sm.fail_step("No se detectaron notas")
        sm.save_session()
        print(f"{YELLOW}⚠ No se detectaron notas{RESET}")
        print(f"{DIM}Sesión guardada en: {session.output_dir}{RESET}")
        return
    
    # Auto-detectar tonalidad
    if session.scale_detected:
        sm.start_step("key_detection")
        with ProgressTimer("Detectando tonalidad"):
            detected_key = detect_key(result.notes)
        session.detected_key = detected_key
        sm.complete_step({"detected_key": detected_key})
        print(f"  {CYAN}Tonalidad detectada: {detected_key}{RESET}")
    
    # Guardar notas detectadas en sesión
    for note in result.notes:
        session.detected_notes.append(DetectedNote(
            midi_note=note.midi_note,
            note_name=midi_to_note_name(note.midi_note),
            start_time=note.start_time,
            duration=note.duration,
            velocity=note.velocity,
            confidence=note.confidence,
            original_hz=note.original_pitch_hz,
            quantized_hz=note.pitch_hz,
            cents_deviation=note.cents_deviation() if note.original_pitch_hz else 0
        ))
    
    session.detected_tempo = result.tempo
    session.is_percussive = result.is_percussive
    
    print(f"\n{GREEN}✓ Notas detectadas: {result.num_notes}{RESET}")
    print(f"  Tipo: {'Percusivo 🥁' if result.is_percussive else 'Melódico 🎵'}")
    if result.tempo:
        print(f"  Tempo: {result.tempo:.0f} BPM")
    
    # Mostrar primeras notas
    print(f"\n{BOLD}Primeras notas:{RESET}")
    for i, note in enumerate(result.notes[:10]):
        name = midi_to_note_name(note.midi_note)
        dev = note.cents_deviation() if note.original_pitch_hz else 0
        dev_str = f" ({dev:+.0f}¢)" if dev else ""
        print(f"  {i+1}. {name}{dev_str} ({note.start_time:.2f}s, {note.duration:.2f}s)")
    
    # Sintetizar
    resp = input(f"\n¿Sintetizar? [{GREEN}s{RESET}/n]: ").strip().lower()
    if resp != 'n':
        session.status = "synthesizing"
        sm.start_step("synthesis", {"waveform": "sawtooth"})
        
        synth = SimpleSynthesizer(waveform='sawtooth')
        
        with ProgressTimer("Sintetizando audio"):
            synth_audio = synth.render(result.notes, sample_rate=44100)
        
        sm.complete_step({"duration": len(synth_audio) / 44100})
        
        # Exportar
        sm.start_step("export")
        exporter = Exporter(ExportConfig(output_dir=session.output_dir))
        
        with ProgressTimer("Exportando archivos"):
            files = exporter.export_all(
                result,
                original_recording=recording,
                synth_audio=synth_audio,
                sample_rate=44100,
                base_name="output"
            )
        
        session.midi_file = files.get('midi')
        session.synth_wav_file = files.get('wav')
        session.synth_mp3_file = files.get('mp3')
        sm.complete_step({"files": list(files.keys())})
        
        print(f"\n{GREEN}{BOLD}📦 Archivos exportados:{RESET}")
        for ftype, fpath in files.items():
            print(f"  • {ftype}: {os.path.basename(fpath)}")
        
        # Reproducir
        resp = input(f"\n¿Reproducir? [{GREEN}s{RESET}/n]: ").strip().lower()
        if resp != 'n' and session.synth_wav_file:
            os.system(f"afplay '{session.synth_wav_file}'")
    
    # Guardar sesión
    session.status = "completed"
    session_file = sm.save_session()
    
    print(f"\n{GREEN}{BOLD}📁 Sesión guardada:{RESET}")
    print(f"  {session.output_dir}")
    print(f"  {DIM}Podés recargar esta sesión con la opción [8]{RESET}")


def option_test_instrument():
    """Probar un instrumento"""
    from vozacosa.instruments import InstrumentManager, AdvancedSynthesizer
    from vozacosa.models import Note, NoteType
    from vozacosa.scales import NOTE_TO_MIDI
    from vozacosa.session import ProgressTimer
    import numpy as np
    from scipy.io import wavfile
    
    print(f"\n{BOLD}🎹 PROBAR INSTRUMENTO{RESET}\n")
    
    manager = InstrumentManager('instruments')
    
    print("Instrumentos disponibles:")
    for inst in manager.list_instruments():
        print(f"  {CYAN}{inst.id}{RESET} - {inst.name}")
    
    inst_id = input(f"\nInstrumento [{GREEN}synth_lead{RESET}]: ").strip() or 'synth_lead'
    instrument = manager.get_instrument(inst_id)
    
    if not instrument:
        print(f"{RED}Instrumento no encontrado{RESET}")
        return
    
    notes_str = input(f"Notas [{GREEN}C4,E4,G4,C5{RESET}]: ").strip() or 'C4,E4,G4,C5'
    
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
    
    synth = AdvancedSynthesizer(manager)
    
    with ProgressTimer(f"Sintetizando con {instrument.name}"):
        audio = synth.render(note_list, instrument, sample_rate=44100)
    
    os.makedirs('output', exist_ok=True)
    output_path = f'output/test_{inst_id}.wav'
    audio_int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    wavfile.write(output_path, 44100, audio_int16)
    
    print(f"{GREEN}✓ Guardado: {output_path}{RESET}")
    
    resp = input(f"\n¿Reproducir? [{GREEN}s{RESET}/n]: ").strip().lower()
    if resp != 'n':
        os.system(f"afplay '{output_path}'")


def option_list_instruments():
    """Ver instrumentos"""
    from vozacosa.instruments import InstrumentManager
    
    print(f"\n{BOLD}📋 INSTRUMENTOS DISPONIBLES{RESET}\n")
    
    manager = InstrumentManager('instruments')
    
    for inst in manager.list_instruments():
        print(f"  {CYAN}{inst.id:15}{RESET} │ {inst.name:20} │ {inst.type.value:15} │ {inst.description}")
    
    if manager.drum_kits:
        print(f"\n{BOLD}Drum Kits:{RESET}")
        for kit_id, kit in manager.drum_kits.items():
            print(f"  {CYAN}{kit_id}{RESET} - {kit.name}")


def option_list_scales():
    """Ver escalas"""
    from vozacosa.scales import SCALES, SCALE_INTERVALS, MIDI_TO_NOTE
    
    print(f"\n{BOLD}🎼 ESCALAS DISPONIBLES{RESET}\n")
    
    for scale_name in SCALES:
        intervals = SCALE_INTERVALS[scale_name]
        notes = [MIDI_TO_NOTE[i] for i in intervals]
        print(f"  {CYAN}{scale_name:18}{RESET} │ {' '.join(notes)}")


def option_list_devices():
    """Ver dispositivos de audio"""
    from vozacosa.recorder import list_audio_devices
    
    print(f"\n{BOLD}🎧 DISPOSITIVOS DE AUDIO{RESET}\n")
    
    devices = list_audio_devices()
    if not devices:
        print(f"{YELLOW}No se encontraron dispositivos{RESET}")
        return
    
    for dev in devices:
        print(f"  [{CYAN}{dev['id']}{RESET}] {dev['name']} ({dev['channels']}ch, {dev['sample_rate']:.0f}Hz)")


def option_convert_file():
    """Convertir archivo de audio"""
    from vozacosa.analyzer import PitchAnalyzer, load_audio_file
    from vozacosa.synthesizer import SimpleSynthesizer
    from vozacosa.exporter import Exporter
    from vozacosa.models import QuantizationConfig, ExportConfig
    from vozacosa.session import SessionManager, ProgressTimer, detect_key
    
    print(f"\n{BOLD}📂 CONVERTIR ARCHIVO{RESET}\n")
    
    filepath = input("Ruta del archivo de audio: ").strip()
    
    if not os.path.exists(filepath):
        print(f"{RED}Archivo no encontrado{RESET}")
        return
    
    # Crear sesión
    sm = SessionManager()
    session = sm.create_session()
    session.input_type = "file"
    session.input_file = filepath
    
    scale = input(f"Escala (auto para detectar) [{GREEN}auto{RESET}]: ").strip() or 'auto'
    
    sm.start_step("load_audio")
    with ProgressTimer("Cargando audio"):
        recording = load_audio_file(filepath)
    sm.complete_step({"duration": recording.duration})
    
    session.input_duration = recording.duration
    print(f"  Duración: {recording.duration:.2f}s")
    
    # Analizar
    sm.start_step("analysis")
    analyzer = PitchAnalyzer(model_capacity='medium')
    quant_config = QuantizationConfig(
        scale=None if scale == 'auto' else scale,
        root_note='C'
    )
    
    with ProgressTimer("Analizando con CREPE"):
        result = analyzer.analyze(recording, quant_config)
    sm.complete_step({"notes": result.num_notes})
    
    # Auto-detect key
    if scale == 'auto' and result.notes:
        detected = detect_key(result.notes)
        session.detected_key = detected
        print(f"  {CYAN}Tonalidad detectada: {detected}{RESET}")
    
    print(f"{GREEN}✓ Notas: {result.num_notes}{RESET}")
    
    # Sintetizar y exportar
    sm.start_step("synthesis_export")
    synth = SimpleSynthesizer(waveform='sawtooth')
    
    with ProgressTimer("Sintetizando"):
        synth_audio = synth.render(result.notes, sample_rate=44100)
    
    exporter = Exporter(ExportConfig(output_dir=session.output_dir))
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    
    with ProgressTimer("Exportando"):
        files = exporter.export_all(result, synth_audio=synth_audio, sample_rate=44100, base_name=base_name)
    
    sm.complete_step({"files": list(files.keys())})
    
    session.status = "completed"
    sm.save_session()
    
    print(f"\n{GREEN}{BOLD}📦 Archivos:{RESET}")
    for ftype, fpath in files.items():
        print(f"  • {ftype}: {os.path.basename(fpath)}")
    print(f"\n{DIM}Sesión: {session.output_dir}{RESET}")


def option_list_sessions():
    """Ver sesiones guardadas"""
    from vozacosa.session import SessionManager
    
    print(f"\n{BOLD}📁 SESIONES GUARDADAS{RESET}\n")
    
    sm = SessionManager()
    sessions = sm.list_sessions()
    
    if not sessions:
        print(f"{YELLOW}No hay sesiones guardadas{RESET}")
        return
    
    for s in sessions[:20]:  # Last 20
        status_icon = "✓" if s['status'] == 'completed' else "⚠"
        print(f"  {CYAN}{s['id']}{RESET} │ {status_icon} {s['status']:12} │ {s['notes_count']:3} notas │ {s['duration']:.1f}s")


def option_reload_session():
    """Recargar sesión anterior"""
    from vozacosa.session import SessionManager
    from vozacosa.scales import midi_to_note_name
    
    print(f"\n{BOLD}🔄 RECARGAR SESIÓN{RESET}\n")
    
    sm = SessionManager()
    sessions = sm.list_sessions()
    
    if not sessions:
        print(f"{YELLOW}No hay sesiones guardadas{RESET}")
        return
    
    print("Sesiones disponibles:")
    for s in sessions[:10]:
        print(f"  {CYAN}{s['id']}{RESET} - {s['notes_count']} notas, {s['duration']:.1f}s")
    
    session_id = input(f"\nID de sesión: ").strip()
    
    session = sm.load_session(session_id)
    if not session:
        print(f"{RED}Sesión no encontrada{RESET}")
        return
    
    print(f"\n{GREEN}{BOLD}Sesión cargada:{RESET}")
    print(f"  Creada: {session.created_at}")
    print(f"  Duración: {session.input_duration:.2f}s")
    print(f"  Notas: {len(session.detected_notes)}")
    print(f"  Tonalidad: {session.detected_key or 'No detectada'}")
    print(f"  Estado: {session.status}")
    
    print(f"\n{BOLD}Archivos:{RESET}")
    if session.original_audio_file:
        print(f"  • Original: {os.path.basename(session.original_audio_file)}")
    if session.midi_file:
        print(f"  • MIDI: {os.path.basename(session.midi_file)}")
    if session.synth_wav_file:
        print(f"  • WAV: {os.path.basename(session.synth_wav_file)}")
    
    print(f"\n{BOLD}Pasos de procesamiento:{RESET}")
    for step in session.steps:
        status_icon = "✓" if step.status == 'completed' else "❌"
        dur = f"{step.duration_seconds:.2f}s" if step.duration_seconds else "?"
        print(f"  {status_icon} {step.name}: {dur}")
    
    # Opciones
    print(f"\n{BOLD}Opciones:{RESET}")
    print(f"  {CYAN}[1]{RESET} Reproducir audio sintetizado")
    print(f"  {CYAN}[2]{RESET} Ver notas detectadas")
    print(f"  {CYAN}[3]{RESET} Abrir carpeta de sesión")
    
    opt = input(f"\nOpción: ").strip()
    
    if opt == '1' and session.synth_wav_file:
        os.system(f"afplay '{session.synth_wav_file}'")
    elif opt == '2':
        print(f"\n{BOLD}Notas detectadas:{RESET}")
        for i, n in enumerate(session.detected_notes[:20]):
            print(f"  {i+1}. {n.note_name} @ {n.start_time:.2f}s ({n.duration:.2f}s)")
    elif opt == '3':
        os.system(f"open '{session.output_dir}'")


def main():
    while True:
        clear_screen()
        show_banner()
        print(MENU)
        
        choice = input(f"{BOLD}Elige una opción: {RESET}").strip()
        
        try:
            if choice == '1':
                option_record()
                pause()
            elif choice == '2':
                option_test_instrument()
                pause()
            elif choice == '3':
                option_list_instruments()
                pause()
            elif choice == '4':
                option_list_scales()
                pause()
            elif choice == '5':
                option_list_devices()
                pause()
            elif choice == '6':
                option_convert_file()
                pause()
            elif choice == '7':
                option_list_sessions()
                pause()
            elif choice == '8':
                option_reload_session()
                pause()
            elif choice == '0':
                print(f"\n{DIM}¡Hasta luego!{RESET}\n")
                break
            else:
                print(f"{YELLOW}Opción no válida{RESET}")
                pause()
        except KeyboardInterrupt:
            print(f"\n{DIM}Cancelado{RESET}")
            pause()
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            import traceback
            traceback.print_exc()
            pause()


if __name__ == '__main__':
    main()
