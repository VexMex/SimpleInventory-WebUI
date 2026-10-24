"""Small explicit translation catalogue and locale-aware display formatting."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EN = {
"Inventar":"Inventory", "Übersicht":"Overview", "Einstellungen":"Settings",
"Artikel hinzufügen":"Add item", "Artikel bearbeiten":"Edit item", "Bearbeiten":"Edit",
"Artikel":"Items", "Name":"Name", "Menge":"Quantity", "Einheit":"Unit", "Wert":"Value",
"Gruppe":"Group", "Standort":"Location", "Aktion":"Action", "Anzeigen":"Show",
"Aktualisieren":"Refresh", "Speichern":"Save", "Abbrechen":"Cancel",
"Artikel gespeichert.":"Item saved.", "Dieses Inventar ist leer.":"This inventory is empty.",
"Keine Inventare verfügbar. Bitte in Home Assistant ein Inventar einrichten.":"No inventories available. Set up an inventory in Home Assistant.",
"Wert pro Einheit. Nur die Zahl eingeben.":"Value per unit. Enter only the number.",
"Vorhandenen Wert auswählen oder neuen Wert eintippen.":"Select an existing value or type a new one.",
"Neue Einheiten, Gruppen und Standorte werden beim Speichern angelegt.":"New units, groups and locations are created when saving.",
"Mehrere Gruppen oder Standorte mit Komma trennen.":"Separate multiple groups or locations with commas.",
"Passwort":"Password", "Anmelden":"Sign in", "Anmeldung":"Sign in",
"Passwort ungueltig.":"Invalid password.", "Anmeldung erforderlich.":"Sign-in required.",
"Home Assistant oder das konfigurierte Inventar ist derzeit nicht erreichbar.":"Home Assistant or the selected inventory is currently unavailable.",
"Inventar derzeit nicht erreichbar.":"Inventory currently unavailable.",
"Inventar nicht vorhanden.":"Inventory not found.",
"Inventar nicht vorhanden. Bitte die Inventarauswahl neu oeffnen.":"Inventory not found. Open the inventory overview again.",
"Artikel nicht eindeutig vorhanden. Bitte Bestand neu laden.":"Item not found or ambiguous. Refresh the inventory.",
"Seite nicht gefunden.":"Page not found.", "Ungueltige Eingabe.":"Invalid input.",
"Eingabe zu gross.":"Input too large.", "Formular ungueltig oder abgelaufen. Bitte neu oeffnen.":"Form invalid or expired. Open it again.",
"Name und eine Menge von 0 bis 1000000000 angeben (max. 6 Nachkommastellen). Wert als Zahl von 0 bis 1000000000 mit maximal 2 Nachkommastellen angeben. Textfelder duerfen keine Steuerzeichen enthalten. Mit Zurueck korrigieren.":"Enter a name and quantity from 0 to 1000000000 (up to 6 decimal places). Value must be from 0 to 1000000000 with up to 2 decimal places. Text fields must not contain control characters. Go back to correct the form.",
"Dieses Formular wurde bereits abgesendet. Bitte Bestand neu laden.":"This form has already been submitted. Refresh the inventory.",
"Bitte spaeter erneut versuchen.":"Try again later.",
"Artikel bereits vorhanden oder zwischenzeitlich geaendert. Bitte Bestand neu laden und das Formular erneut oeffnen.":"Item already exists or has changed. Refresh the inventory and reopen the form.",
"Inventar nicht mehr vorhanden. Bitte Uebersicht neu laden.":"Inventory no longer exists. Reload the overview.",
"Home Assistant nicht erreichbar. Bitte Verbindung pruefen.":"Home Assistant unavailable. Check the connection.",
"Speicherung nicht bestaetigt. Bitte zuerst den Bestand pruefen, bevor du erneut speicherst.":"Save not confirmed. Check the inventory before saving again.",
"Anmeldeseite bitte neu laden.":"Reload the sign-in page.",
"Zur Übersicht":"Back to overview", "Bitte Eingabe prüfen":"Please check your input",
"Einfach organisiert.":"Simply organized.", "Bestand im Blick":"Your inventory at a glance",
"Artikel verwalten":"Manage items", "Direkt mit Home Assistant verbunden":"Connected through Home Assistant",
"Zuletzt geladen":"Last loaded", "Anzeige für diesen Browser":"Display for this browser",
"Diese Einstellungen gelten nur für diesen Browser.":"These preferences apply only to this browser.",
"Sprache":"Language", "Standard der Installation":"Installation default", "Home-Assistant-Sprache":"Home Assistant language",
"Währung":"Currency", "Die Währung ändert nur die Anzeige. Beträge werden nicht umgerechnet.":"Currency changes only the display. Amounts are not converted.",
"Darstellung":"Appearance", "Systemeinstellung":"Device preference", "Hell":"Light", "Dunkel":"Dark",
"Farbstil":"Color style", "Petrol":"Teal", "Blau":"Blue",
"Abstände":"Spacing", "Komfortabel":"Comfortable", "Kompakt":"Compact",
"Browser-Einstellungen gespeichert.":"Browser preferences saved.",
"Standardwerte verwenden":"Use installation defaults", "Zentrale Vorgaben":"Installation defaults",
"Passwortschutz":"Password protection", "Aktiviert":"Enabled", "Deaktiviert":"Disabled",
"Lokales Netzwerk ohne Passwort":"Local network without password",
"Diese Vorgaben werden zentral verwaltet und gelten für alle Browser.":"These defaults are managed centrally and apply to all browsers.",
"Browser-Daten zurücksetzen":"Reset browser preferences",
"Deutsch":"Deutsch", "English":"English",
}

def translate(text, language):
    return EN.get(text, text) if language == "en" else text

def number(value, language, money=False):
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) > Decimal("1e15"):
            return "—"
        rendered = format(amount, ",.2f") if money else format(amount, ",.6f").rstrip("0").rstrip(".")
        if language == "de":
            rendered = rendered.replace(",", "_").replace(".", ",").replace("_", ".")
        return rendered
    except (InvalidOperation, ValueError, TypeError):
        return "—"

SYMBOLS = {"EUR":"€", "USD":"$", "GBP":"£", "CHF":"CHF"}

def currency(value, language, code):
    rendered = number(value, language, money=True)
    if rendered == "—":
        return rendered
    symbol = SYMBOLS[code]
    return (symbol + rendered) if language == "en" and code != "CHF" else rendered + " " + symbol

def timestamp(language, timezone):
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = ZoneInfo("UTC")
    return datetime.now(zone).strftime("%d.%m.%Y %H:%M %Z" if language == "de" else "%Y-%m-%d %H:%M %Z")
