---
description:
  "Platziere gravierten Text, Beschriftungen und Seriennummern mit dem Textfeld-Werkzeug im
  Rayforge-Sketcher auf einer Skizze."
---

# Textfeld

Das Textfeld-Werkzeug (`G+T`) platziert Text auf der Skizze als bearbeitbare Geometrie — gravierten
Text, Beschriftungen und Seriennummern. Textfelder sind vollständig parametrisch: Die Glyphen
befinden sich innerhalb eines durch Einschränkungen festgelegten Rahmens, sodass sie sich neu lösen,
sobald der Rahmen bewegt oder bemaßt wird.

![Ein Wortzeichen und eine Teilebeschriftung](/screenshots/addons-sketcher-tool-text-box.webp)

## Text erstellen und bearbeiten

1. Wähle das Textfeld-Werkzeug aus dem Kreismenü, dem Menü **Sketch** oder mit `G+T`.
2. Klicke an die Stelle, an der der Text beginnen soll: Am Klickpunkt erscheint ein Textfeld, und
   das Werkzeug wechselt direkt in den Bearbeitungsmodus.
3. Tippe den Text ein — das Feld passt seine Größe beim Tippen automatisch an.
4. Drücke `Enter` oder `Escape`, um die Bearbeitung zu beenden.

Um ein vorhandenes Textfeld zu bearbeiten, klicke hinein. Ein Doppelklick wählt ein Wort aus, ein
Dreifachklick die ganze Zeile, und Text kann wie in jedem Texteditor ausgewählt und ersetzt werden —
inklusive `Ctrl+C`/`Ctrl+V`, Rückgängig/Wiederholen und Einfügen während der Bearbeitung.

## Schriftarteigenschaften

![Das Schriftarteigenschaften-Bedienfeld](/screenshots/addons-sketcher-tool-text-box-font-properties.webp)

Das Bedienfeld **Schriftarteigenschaften** in der Seitenleiste steuert das Erscheinungsbild des auf
der Leinwand ausgewählten Textfelds:

- **Schriftfamilie** — wähle aus den installierten Systemschriften.
- **Benutzerdefinierte Schriftart** — wähle eine selbst installierte Schriftart (siehe
  [Benutzerdefinierte Schriftarten](#custom-fonts)).
- **Schriftgröße** — in Punkt.
- **Fett**- und **Kursiv**-Schalter.

## Text-Transformationen {#text-transforms}

Dasselbe Bedienfeld kann ändern, wie der Text innerhalb seines Rahmens angeordnet wird:

- **Spiegeln** — spiegelt den Text von links nach rechts, um die Rückseite eines transparenten
  Materials zu gravieren.
- **Zeichen umkehren** — schreibt die Zeichen in umgekehrter Reihenfolge, ohne sie zu spiegeln.
- **Vertikal** — stapelt aufrechte Zeichen von oben nach unten.
- **Drehung** — dreht den Text um die Mitte seines Rahmens. Der Rahmen selbst bleibt horizontal.
- **Auf dem Kopf** — eine Abkürzung für eine Drehung um 180°.

Während eine dieser Optionen aktiv ist, kannst du weiterhin in das Textfeld tippen, aber ein Klick
platziert die Einfügemarke nicht mehr innerhalb des Textes.

## Knock-out-Text {#knock-out-text}

Aktiviere **Knock-out**, um eine Platte zu gravieren, bei der der Text ausgespart bleibt. Die Platte
ist der um den **Knock-out-Rand** an jeder Seite vergrößerte Textrahmen. Der Umriss enthält die
Platte und die Buchstaben; die Füllung bedeckt die Platte mit Ausnahme der Buchstaben.

Die geschlossenen Teile von Buchstaben wie O, A und B bleiben nicht erhalten, daher ist
Knock-out-Text für die Gravur gedacht, nicht zum Schneiden von Schablonen.

## Text an einem Pfad {#text-on-a-path}

Text kann einer Linie, einem Bogen, einem Kreis oder einer Kurve folgen:

1. Wähle das Textfeld zusammen mit der Form aus, der es folgen soll.
2. Aktiviere **Pfad folgen** im Bedienfeld Schriftarteigenschaften.

- **Pfadseite** — **Außen** platziert den Text links der Pfadrichtung; **Innen** platziert ihn auf
  der anderen Seite und kehrt die Leserichtung um, sodass Text auf der Innenseite eines Kreises
  unten aufrecht zu lesen ist.
- **Pfadausrichtung** — Anfang, Mitte oder Ende des Pfads.
- **Pfadversatz** — verschiebt den Text entlang des Pfads.
- **Unterer Text** — bei einem Kreis eine zweite Textzeile, die unten auf der Innenseite zentriert
  ist, während der Haupttext oben auf der Außenseite zentriert ist. Beide sind aufrecht lesbar, was
  einen runden Stempel oder ein Siegel ergibt.

Um den Text zu lösen, wähle nur das Textfeld aus und aktiviere **Pfad folgen** erneut. Wenn die Form
gelöscht wird, kehrt der Text in seinen Rahmen zurück.

Text an einem Pfad behält seine Schriftgröße, und Spiegeln, Vertikal, Drehung und Knock-out gelten
nicht dafür. Ein Pfad ist eine einzelne Form; Text setzt sich nicht von einer Linie oder einem Bogen
auf den nächsten fort.

## Benutzerdefinierte Schriftarten {#custom-fonts}

Verwende **Schriftart installieren…**, um eine `.ttf`- oder `.otf`-Datei hinzuzufügen. Installierte
Schriftarten erscheinen in jeder Skizze in der Liste **Benutzerdefinierte Schriftart**, und
**Benutzerdefinierte Schriftart entfernen** löscht die ausgewählte.

Schriftarten werden auf deinem Computer gespeichert, nicht in der Projektdatei. Wenn ein Projekt
eine Schriftart verwendet, die nicht installiert ist, zeigt das Bedienfeld **Schriftart nicht
installiert** an und es wird eine Ersatzschriftart verwendet, bis du die Schriftart installierst
oder eine andere wählst.

## Voreinstellungen {#presets}

Eine Voreinstellung speichert die Schriftart und den Textstil, nicht jedoch den Text selbst oder den
Pfad, dem er folgt. Gib einen Namen in **Als Voreinstellung speichern** ein, um die Einstellungen
des ausgewählten Textfelds zu speichern, wähle einen Namen aus **Voreinstellung**, um sie
anzuwenden, und verwende **Voreinstellung löschen**, um die ausgewählte Voreinstellung zu entfernen.
Das Anwenden einer Voreinstellung ist ein einzelner Rückgängig-Schritt.

## Seriennummern {#serial-numbers}

**Seriennummer einfügen** fügt `{serial()}` in den Text ein. Es zeigt den aktuellen Wert eines
Zählers an, und der Zähler rückt jedes Mal um einen Schritt weiter, wenn ein Auftrag an die Maschine
gesendet oder als G-Code exportiert wird. Framing, Vorschauen und abgebrochene oder fehlgeschlagene
Aufträge verbrauchen keine Nummer.

Zähler werden von allen Dokumenten gemeinsam genutzt und unter **Einstellungen → Seriennummern**
verwaltet, wo jeder Zähler einen Startwert, Schritt, führende Nullen, Präfix und Suffix hat.
Verwende `{serial("name")}`, um einen bestimmten Zähler anzuzeigen.

## Ein parametrischer Rahmen

Ein Textfeld ist kein Rasterbild: Seine Glyphen sind echte Skizzengeometrie, die innerhalb eines
Rahmens aus einem Ursprung sowie Breiten- und Höhenpunkten angeordnet ist. Der Rahmen wird als
Konstruktionsgeometrie gestrichelt gezeichnet, dient also als Layout-Referenz und landet beim
Fertigen der Skizze nie in den Werkzeugpfaden. Wie alles andere im Sketcher ist auch der Rahmen mit
Einschränkungen versehen, sodass er wie jede andere Geometrie bemaßt werden kann — ändere die
Breiteneinschränkung, und der Text wird neu gelöst, um das Feld zu füllen.

Ein Klick innerhalb eines Textfelds mit dem [Füll-Werkzeug](fill.md) schaltet stattdessen die
Füllung der Textglyphen um, statt eine Bereichsfüllung zu erzeugen.

## Vorlagenausdrücke

Textfelder akzeptieren **Vorlagenausdrücke**: Alles in geschweiften Klammern wird beim Lösen der
Skizze ausgewertet, sodass Beschriftungen Live-Werte wie Maße, Daten oder eindeutige Seriennummern
anzeigen können. Einzelheiten und die eingebauten Funktionen findest du unter
[Vorlagenausdrücke in Textfeldern](expressions.md#template-expressions-in-text-boxes).
