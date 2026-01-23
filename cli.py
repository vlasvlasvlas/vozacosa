#!/usr/bin/env python3
"""
VozACosa CLI - Voice to MIDI Converter
Interfaz de línea de comandos con Rich/Textual
"""
import os
import sys
import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import print as rprint

console = Console()

# Banner ASCII
BANNER = """
[bold cyan]
╦  ╦╔═╗╔═╗╔═╗╔═╗╔═╗╔═╗╔═╗
╚╗╔╝║ ║╔═╝╠═╣║  ║ ║╚═╗╠═╣
 ╚╝ ╚═╝╚═╝╩ ╩╚═╝╚═╝╚═╝╩ ╩
[/bold cyan]
[dim]Voice to MIDI Converter - SOTA Pitch Detection[/dim]
"""


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """VozACosa - Convierte tu voz cantada a MIDI"""
    pass


@cli.command()
def record():
    """Graba audio desde el micrófono y lo convierte a MIDI"""
    from vozacosa.recorder import AudioRecorder, list_audio_devices
    from vozacosa.analyzer import PitchAnalyzer
    from vozacosa.synthesizer import SimpleSynthesizer
    from vozacosa.exporter import Exporter, generate_session_name
    from vozacosa.models import QuantizationConfig, ExportConfig
    from vozacosa.scales import SCALES, midi_to_note_name
    
    console.print(BANNER)
    
    # Mostrar dispositivos disponibles
    devices = list_audio_devices()
    if devices:
        console.print("\n[bold]Dispositivos de audio disponibles:[/bold]")
        for dev in devices:
            console.print(f"  [{dev['id']}] {dev['name']}")
    
    # Configurar cuantización
    console.print("\n[bold yellow]Configuración de cuantización:[/bold yellow]")
    
    # Seleccionar escala
    scales_list = ['chromatic', 'major', 'natural_minor', 'pentatonic_major', 'pentatonic_minor', 'blues']
    console.print("Escalas disponibles: " + ", ".join(scales_list))
    scale = Prompt.ask("Escala", default="major", choices=scales_list)
    
    root = Prompt.ask("Nota raíz", default="C")
    
    tolerance = int(Prompt.ask("Tolerancia en cents (0=estricto, 50=libre)", default="25"))
    
    quant_config = QuantizationConfig(
        scale=scale if scale != 'chromatic' else None,
        root_note=root,
        tolerance_cents=tolerance,
        snap_to_scale=True
    )
    
    # Inicializar componentes
    recorder = AudioRecorder(sample_rate=22050)
    analyzer = PitchAnalyzer(model_capacity='medium')
    synth = SimpleSynthesizer(waveform='sawtooth')
    exporter = Exporter(ExportConfig(output_dir='output'))
    
    console.print("\n[bold green]🎤 Presiona ENTER para iniciar la grabación...[/bold green]")
    input()
    
    recorder.start()
    console.print("[bold red]● GRABANDO[/bold red] - Presiona ENTER para detener")
    
    # Mostrar tiempo de grabación
    import time
    try:
        while True:
            time.sleep(0.1)
            elapsed = recorder.elapsed_time
            console.print(f"\r[dim]⏱ {elapsed:.1f}s[/dim]", end="")
            # Check for enter key (non-blocking would be better but this is simpler)
            import select
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()
                break
    except KeyboardInterrupt:
        pass
    
    recording = recorder.stop()
    console.print(f"\n[green]✓ Grabación completada: {recording.duration:.2f}s[/green]")
    
    # Analizar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Analizando pitch con CREPE...", total=None)
        result = analyzer.analyze(recording, quant_config)
        progress.update(task, completed=True)
    
    # Mostrar resultados
    if result.notes:
        console.print(f"\n[bold]📊 Resultado del análisis:[/bold]")
        console.print(f"  • Notas detectadas: {result.num_notes}")
        console.print(f"  • Tipo: {'Percusivo 🥁' if result.is_percussive else 'Melódico 🎵'}")
        if result.tempo:
            console.print(f"  • Tempo estimado: {result.tempo:.0f} BPM")
        
        # Tabla de notas
        table = Table(title="Notas Detectadas")
        table.add_column("#", style="dim")
        table.add_column("Nota", style="cyan")
        table.add_column("Inicio", style="green")
        table.add_column("Duración", style="yellow")
        table.add_column("Vel", style="magenta")
        
        for i, note in enumerate(result.notes[:20]):  # Mostrar máximo 20
            note_name = midi_to_note_name(note.midi_note)
            table.add_row(
                str(i + 1),
                note_name,
                f"{note.start_time:.2f}s",
                f"{note.duration:.2f}s",
                str(note.velocity)
            )
        
        console.print(table)
        
        if len(result.notes) > 20:
            console.print(f"[dim]... y {len(result.notes) - 20} notas más[/dim]")
        
        # Sintetizar
        if Confirm.ask("\n¿Sintetizar y reproducir?"):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Sintetizando...", total=None)
                synth_audio = synth.render(result.notes, sample_rate=44100)
                progress.update(task, completed=True)
            
            console.print("[green]✓ Síntesis completada[/green]")
            
            # TODO: Reproducir audio
            
            # Exportar
            if Confirm.ask("¿Exportar archivos?"):
                session_name = generate_session_name()
                files = exporter.export_all(
                    result,
                    original_recording=recording,
                    synth_audio=synth_audio,
                    sample_rate=44100,
                    base_name=session_name
                )
                
                console.print("\n[bold green]📦 Archivos exportados:[/bold green]")
                for ftype, fpath in files.items():
                    console.print(f"  • {ftype}: [link=file://{fpath}]{os.path.basename(fpath)}[/link]")
    else:
        console.print("[yellow]⚠ No se detectaron notas en la grabación[/yellow]")
    
    console.print("\n[dim]¡Gracias por usar VozACosa![/dim]")


@cli.command()
@click.argument('audio_file', type=click.Path(exists=True))
@click.option('--scale', '-s', default='major', help='Escala para cuantización')
@click.option('--root', '-r', default='C', help='Nota raíz')
@click.option('--tolerance', '-t', default=25, help='Tolerancia en cents')
@click.option('--output', '-o', default='output', help='Directorio de salida')
def convert(audio_file, scale, root, tolerance, output):
    """Convierte un archivo de audio existente a MIDI"""
    from vozacosa.analyzer import PitchAnalyzer, load_audio_file
    from vozacosa.synthesizer import SimpleSynthesizer
    from vozacosa.exporter import Exporter
    from vozacosa.models import QuantizationConfig, ExportConfig
    from vozacosa.scales import midi_to_note_name
    
    console.print(BANNER)
    console.print(f"[bold]Procesando:[/bold] {audio_file}")
    
    # Cargar audio
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Cargando audio...", total=None)
        recording = load_audio_file(audio_file)
        progress.update(task, completed=True)
    
    console.print(f"  • Duración: {recording.duration:.2f}s")
    console.print(f"  • Sample rate: {recording.sample_rate}Hz")
    
    # Configurar
    quant_config = QuantizationConfig(
        scale=scale if scale != 'chromatic' else None,
        root_note=root,
        tolerance_cents=tolerance,
        snap_to_scale=True
    )
    
    # Analizar
    analyzer = PitchAnalyzer(model_capacity='medium')
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Analizando con CREPE...", total=None)
        result = analyzer.analyze(recording, quant_config)
        progress.update(task, completed=True)
    
    console.print(f"\n[bold]Resultado:[/bold]")
    console.print(f"  • Notas: {result.num_notes}")
    console.print(f"  • Tipo: {'Percusivo' if result.is_percussive else 'Melódico'}")
    
    # Sintetizar
    synth = SimpleSynthesizer(waveform='sawtooth')
    synth_audio = synth.render(result.notes, sample_rate=44100)
    
    # Exportar
    exporter = Exporter(ExportConfig(output_dir=output))
    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    files = exporter.export_all(
        result,
        synth_audio=synth_audio,
        sample_rate=44100,
        base_name=base_name
    )
    
    console.print("\n[bold green]Archivos generados:[/bold green]")
    for ftype, fpath in files.items():
        console.print(f"  • {ftype}: {fpath}")


@cli.command()
def devices():
    """Lista los dispositivos de audio disponibles"""
    from vozacosa.recorder import list_audio_devices
    
    console.print(BANNER)
    devices = list_audio_devices()
    
    if not devices:
        console.print("[yellow]No se encontraron dispositivos de entrada[/yellow]")
        return
    
    table = Table(title="Dispositivos de Audio")
    table.add_column("ID", style="cyan")
    table.add_column("Nombre", style="green")
    table.add_column("Canales", style="yellow")
    table.add_column("Sample Rate", style="magenta")
    
    for dev in devices:
        table.add_row(
            str(dev['id']),
            dev['name'],
            str(dev['channels']),
            f"{dev['sample_rate']:.0f}Hz"
        )
    
    console.print(table)


@cli.command()
def scales():
    """Muestra las escalas disponibles"""
    from vozacosa.scales import SCALES, SCALE_INTERVALS, MIDI_TO_NOTE
    
    console.print(BANNER)
    
    table = Table(title="Escalas Disponibles")
    table.add_column("Nombre", style="cyan")
    table.add_column("Intervalos", style="green")
    table.add_column("Notas (desde C)", style="yellow")
    
    for scale_name in SCALES:
        intervals = SCALE_INTERVALS[scale_name]
        notes = [MIDI_TO_NOTE[i] for i in intervals]
        table.add_row(
            scale_name,
            " ".join(str(i) for i in intervals),
            " ".join(notes)
        )
    
    console.print(table)


@cli.command()
def instruments():
    """Lista los instrumentos disponibles"""
    from vozacosa.instruments import InstrumentManager
    
    console.print(BANNER)
    
    manager = InstrumentManager('instruments')
    
    # Group by category
    categories = {}
    for inst in manager.list_instruments():
        cat = inst.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(inst)
    
    table = Table(title="Instrumentos Disponibles")
    table.add_column("ID", style="cyan")
    table.add_column("Nombre", style="green")
    table.add_column("Categoría", style="yellow")
    table.add_column("Tipo", style="magenta")
    table.add_column("Descripción", style="dim")
    
    for cat, insts in sorted(categories.items()):
        for inst in insts:
            table.add_row(
                inst.id,
                inst.name,
                cat,
                inst.type.value,
                inst.description[:40] + "..." if len(inst.description) > 40 else inst.description
            )
    
    console.print(table)
    
    # Show drum kits
    if manager.drum_kits:
        console.print("\n[bold]Drum Kits:[/bold]")
        for kit_id, kit in manager.drum_kits.items():
            console.print(f"  • {kit_id}: {kit.name}")


@cli.command()
@click.argument('instrument_id')
@click.option('--notes', '-n', default='C4,E4,G4,C5', help='Notas a tocar (separadas por coma)')
@click.option('--duration', '-d', default=0.5, help='Duración de cada nota en segundos')
@click.option('--output', '-o', default='output/test.wav', help='Archivo de salida')
def test_instrument(instrument_id, notes, duration, output):
    """Prueba un instrumento con notas específicas"""
    from vozacosa.instruments import InstrumentManager, AdvancedSynthesizer
    from vozacosa.models import Note, NoteType
    from vozacosa.scales import NOTE_TO_MIDI
    import numpy as np
    from scipy.io import wavfile
    import os
    
    console.print(BANNER)
    
    manager = InstrumentManager('instruments')
    instrument = manager.get_instrument(instrument_id)
    
    if not instrument:
        console.print(f"[red]Error: Instrumento '{instrument_id}' no encontrado[/red]")
        console.print("Usa 'python cli.py instruments' para ver la lista")
        return
    
    console.print(f"[bold]Probando:[/bold] {instrument.name} ({instrument.type.value})")
    
    # Parse notes
    note_list = []
    time = 0.0
    for note_str in notes.split(','):
        note_str = note_str.strip()
        # Parse note name (e.g., C4, D#5)
        if len(note_str) >= 2:
            note_name = note_str[:-1] if note_str[-1].isdigit() else note_str
            octave = int(note_str[-1]) if note_str[-1].isdigit() else 4
            
            base_midi = NOTE_TO_MIDI.get(note_name, 60)
            midi_note = (base_midi % 12) + (octave + 1) * 12
            
            note_list.append(Note(
                pitch_hz=None,
                midi_note=midi_note,
                start_time=time,
                duration=duration,
                velocity=100,
                note_type=NoteType.MELODIC
            ))
            time += duration + 0.1
    
    console.print(f"  • Notas: {len(note_list)}")
    
    # Synthesize
    synth = AdvancedSynthesizer(manager)
    audio = synth.render(note_list, instrument, sample_rate=44100)
    
    # Save
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    audio_int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    wavfile.write(output, 44100, audio_int16)
    
    console.print(f"\n[bold green]✓ Guardado:[/bold green] {output}")
    console.print(f"  Duración: {len(audio) / 44100:.2f}s")


if __name__ == '__main__':
    cli()
