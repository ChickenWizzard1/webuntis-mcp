import os
import datetime
import logging
import webuntis
from mcp.server.fastmcp import FastMCP

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebUntisMCPServer")

# FastMCP Server initialisieren
mcp = FastMCP(
    "WebUntis FEG Server",
    instructions="Bietet Tools zum Abrufen von Stundenplänen, Vertretungen und Hausaufgaben von WebUntis für das FEG Sandhausen."
)

def get_session():
    """Hilfsfunktion: Erstellt eine WebUntis-Sitzung basierend auf Umgebungsvariablen."""
    username = os.environ.get("UNTIS_USERNAME")
    password = os.environ.get("UNTIS_PASSWORD")
    
    if not username or not password:
        raise ValueError("Umgebungsvariablen UNTIS_USERNAME oder UNTIS_PASSWORD sind nicht gesetzt!")
        
    return webuntis.Session(
        server='sandhausen.webuntis.com',
        username=username,
        password=password,
        school='feg',
        useragent='MCP-Poke-Agent/1.0'
    )

@mcp.tool()
def get_timetable(days_offset: int = 0) -> str:
    """
    Ruft den Stundenplan für einen bestimmten Tag ab.
    
    Args:
        days_offset: Versatz in Tagen (0 = Heute, 1 = Morgen, etc.)
    """
    try:
        s = get_session()
        s.login()
        try:
            target_date = datetime.date.today() + datetime.timedelta(days=days_offset)
            logger.info(f"Rufe Stundenplan für {target_date} ab...")
            
            timetable = s.my_timetable(start=target_date, end=target_date)
            periods = sorted(timetable, key=lambda p: p.start)
            
            if not periods:
                return f"Kein Unterricht am {target_date.strftime('%d.%m.%Y')}."
                
            result = [f"📅 Stundenplan für {target_date.strftime('%d.%m.%Y')}:"]
            for period in periods:
                start_time = period.start.strftime("%H:%M")
                end_time = period.end.strftime("%H:%M")
                subjects = ", ".join([sub.name for sub in period.subjects]) or "Kein Fach"
                rooms = ", ".join([r.name for r in period.rooms]) or "Kein Raum"
                teachers = ", ".join([t.name for t in period.teachers]) or "Kein Lehrer"
                
                status_suffix = ""
                if period.code == 'cancelled':
                    status_suffix = " ❌ (ENTFÄLLT)"
                elif period.code == 'irregular':
                    status_suffix = " ⚠️ (ÄNDERUNG/VERTRETUNG)"
                    
                result.append(f"⏰ {start_time} - {end_time}: {subjects} bei {teachers} in Raum {rooms}{status_suffix}")
                
            return "\n".join(result)
        finally:
            s.logout()
    except Exception as e:
        logger.error(f"Fehler in get_timetable: {str(e)}")
        return f"Fehler beim Abrufen des Stundenplans: {str(e)}"

@mcp.tool()
def get_substitutions(days_offset: int = 0) -> str:
    """
    Prüft gezielt auf Vertretungen, Raumänderungen oder Ausfälle für einen bestimmten Tag.
    
    Args:
        days_offset: Versatz in Tagen (0 = Heute, 1 = Morgen, etc.)
    """
    try:
        s = get_session()
        s.login()
        try:
            target_date = datetime.date.today() + datetime.timedelta(days=days_offset)
            logger.info(f"Prüfe Vertretungen für {target_date} ab...")
            
            timetable = s.my_timetable(start=target_date, end=target_date)
            periods = sorted(timetable, key=lambda p: p.start)
            
            changes = []
            for period in periods:
                start_time = period.start.strftime("%H:%M")
                subjects = ", ".join([sub.name for sub in period.subjects]) or "Unbekanntes Fach"
                
                if period.code == 'cancelled':
                    changes.append(f"❌ AUSFALL: {start_time} Uhr - {subjects} entfällt.")
                elif period.code == 'irregular':
                    rooms = ", ".join([r.name for r in period.rooms]) or "unbekannt"
                    changes.append(f"⚠️ VERTRETUNG/ÄNDERUNG: {start_time} Uhr - {subjects} (Neu in Raum: {rooms})")
                    
            if not changes:
                return f"Keine Vertretungen oder Ausfälle für den {target_date.strftime('%d.%m.%Y')} bekannt."
                
            return f"📢 Vertretungsplan / Änderungen für {target_date.strftime('%d.%m.%Y')}:\n" + "\n".join(changes)
        finally:
            s.logout()
    except Exception as e:
        logger.error(f"Fehler in get_substitutions: {str(e)}")
        return f"Fehler beim Abrufen des Vertretungsplans: {str(e)}"

@mcp.tool()
def get_homework(days_offset: int = 0) -> str:
    """
    Liest die Hausaufgaben oder anstehenden Einträge für den Tag aus.
    
    Args:
        days_offset: Versatz in Tagen (0 = Heute, 1 = Morgen, etc.)
    """
    try:
        s = get_session()
        s.login()
        try:
            target_date = datetime.date.today() + datetime.timedelta(days=days_offset)
            logger.info(f"Rufe Hausaufgaben für {target_date} ab...")
            
            try:
                events = s.class_reg_events(start=target_date, end=target_date)
                if not events:
                    return f"Keine registrierten Hausaufgaben oder Klassenbucheinträge für den {target_date.strftime('%d.%m.%Y')} gefunden."
                
                result = [f"📝 Einträge/Hausaufgaben für {target_date.strftime('%d.%m.%Y')}:"]
                for event in events:
                    subject_name = event.subject if hasattr(event, 'subject') else "Allgemein"
                    text = event.text if hasattr(event, 'text') else str(event)
                    result.append(f"- [{subject_name}]: {text}")
                return "\n".join(result)
            except Exception as inner_e:
                return f"Die Hausaufgaben/Klassenbuch-API lieferte keine Daten oder ist eingeschränkt. Details: {str(inner_e)}"
        finally:
            s.logout()
    except Exception as e:
        logger.error(f"Fehler in get_homework: {str(e)}")
        return f"Fehler beim Abrufen der Hausaufgaben: {str(e)}"

if __name__ == "__main__":
    import os
    import uvicorn

    # Port von Render auslesen (Standard 10000)
    port = int(os.environ.get("PORT", 10000))

    # Der Monkeypatch-Trick:
    # Wir klinken uns in Uvicorn ein und überschreiben die fest im MCP-Framework
    # hinterlegten Werte (127.0.0.1:8000) dynamisch mit den Render-Vorgaben.
    original_run = uvicorn.run
    def patched_run(*args, **kwargs):
        kwargs["host"] = "0.0.0.0"
        kwargs["port"] = port
        return original_run(*args, **kwargs)
    uvicorn.run = patched_run

    logger.info(f"Starte WebUntis MCP-Server im SSE-Modus (gepatcht auf 0.0.0.0:{port})...")
    mcp.run(transport="sse")
