// Nutzungsbedingungen (AGB) für PadelYara.
//
// ENTWURF — an die tatsächliche Funktion der App angepasst: kostenloser
// Informationsdienst, der öffentlich verfügbare Court-Zeiten und Turnierdaten
// zusammenführt; keine Buchung über PadelYara, keine Nutzerkonten. Vor dem
// produktiven Einsatz rechtlich gegenlesen lassen. Anbieter & Adresse müssen
// mit dem Impressum und der Datenschutzerklärung übereinstimmen.

import { Helmet } from "react-helmet-async"

const email = "yara@adventure-it.at"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-white font-semibold text-lg mb-3">{title}</h2>
      <div className="space-y-3 text-sm text-gray-400 leading-relaxed">{children}</div>
    </section>
  )
}

export default function AGBPage() {
  return (
    <article className="text-gray-300">
      <Helmet>
        <title>Nutzungsbedingungen — PadelYara</title>
        <meta name="robots" content="noindex, follow" />
      </Helmet>
      <h1 className="text-white font-bold text-2xl mb-2">Nutzungsbedingungen</h1>
      <p className="text-xs text-gray-600 mb-8">Stand: Juli 2026</p>

      <Section title="1. Anbieter und Geltungsbereich">
        <p>
          Diese Nutzungsbedingungen gelten für die Nutzung der Website und der
          Dienste von PadelYara, erreichbar unter{" "}
          <strong>padelyara.at</strong>. Anbieterin ist:
        </p>
        <p className="text-gray-300">
          Cornelia Mayer<br />
          Griesgasse 2<br />
          2340 Mödling<br />
          Österreich<br />
          <a href={`mailto:${email}`} className="text-indigo-400 hover:text-indigo-300">{email}</a>
        </p>
        <p>
          Mit dem Aufruf und der Nutzung von PadelYara erklären Sie sich mit
          diesen Bedingungen einverstanden.
        </p>
      </Section>

      <Section title="2. Leistungsbeschreibung">
        <p>
          PadelYara ist ein kostenloser Informationsdienst, der freie
          Padel-Court-Zeiten in Österreich aus verschiedenen Buchungsplattformen
          zusammenführt und übersichtlich darstellt. Ergänzend werden
          öffentlich zugängliche Turnier- und Wettbewerbsinformationen
          („Turnierjagd", „Spielanalyse") aufbereitet.
        </p>
        <p>
          Für die Nutzung ist keine Registrierung und kein Nutzerkonto
          erforderlich. Optionale Funktionen (z. B. Newsletter, Court- bzw.
          Turnier-Benachrichtigungen) setzen die freiwillige Angabe einer
          E-Mail-Adresse voraus.
        </p>
      </Section>

      <Section title="3. Keine Buchung über PadelYara">
        <p>
          PadelYara ist eine reine Übersichts- und Verweisplattform.{" "}
          <strong>Buchungen, Zahlungen und Vertragsabschlüsse erfolgen
          ausschließlich auf den jeweiligen Plattformen der Betreiber der
          Anlagen bzw. der Buchungsdienste</strong> und nicht über PadelYara.
          Es kommt durch die Nutzung von PadelYara kein Vertrag über die Miete
          eines Courts oder die Teilnahme an einem Turnier zustande.
        </p>
        <p>
          Für Inhalte, Verfügbarkeiten, Preise und Bedingungen dieser
          Drittplattformen sind ausschließlich deren Betreiber verantwortlich.
        </p>
      </Section>

      <Section title="4. Verfügbarkeit und Richtigkeit der Daten">
        <p>
          Die angezeigten Court-Zeiten, Preise und Turnierdaten werden aus
          externen Quellen abgerufen und können sich jederzeit ändern. Wir
          bemühen uns um eine möglichst aktuelle und korrekte Darstellung,
          können aber <strong>keine Gewähr für Vollständigkeit, Richtigkeit und
          ständige Verfügbarkeit</strong> übernehmen. Maßgeblich sind stets die
          Angaben auf der jeweiligen Buchungs- bzw. Anbieterplattform.
        </p>
        <p>
          Der Dienst wird ohne Anspruch auf ununterbrochene Verfügbarkeit
          bereitgestellt. Wir behalten uns vor, den Dienst jederzeit zu ändern,
          einzuschränken oder einzustellen.
        </p>
      </Section>

      <Section title="5. Zulässige Nutzung">
        <p>
          Sie dürfen PadelYara ausschließlich für den privaten, nicht
          kommerziellen Gebrauch nutzen. Nicht gestattet sind insbesondere das
          automatisierte Auslesen (Scraping), das massenhafte Abfragen zur
          Beeinträchtigung des Betriebs sowie jede missbräuchliche Nutzung, die
          die Sicherheit oder Verfügbarkeit des Dienstes gefährdet.
        </p>
      </Section>

      <Section title="6. Urheberrecht und Marken">
        <p>
          Gestaltung, Texte, Grafiken, das Logo sowie die Marke „PadelYara"
          einschließlich der Figur „Yara" sind urheber- bzw. markenrechtlich
          geschützt. Eine Verwendung außerhalb der bestimmungsgemäßen Nutzung
          des Dienstes bedarf unserer vorherigen Zustimmung.
        </p>
      </Section>

      <Section title="7. Haftung">
        <p>
          Wir haften unbeschränkt für Schäden aus der Verletzung des Lebens, des
          Körpers oder der Gesundheit sowie für Vorsatz und grobe
          Fahrlässigkeit. Im Übrigen ist die Haftung — insbesondere für
          mittelbare Schäden, entgangenen Gewinn oder Schäden aus der Nutzung
          verlinkter Drittangebote — im gesetzlich zulässigen Umfang
          ausgeschlossen. Für die Inhalte externer Links sind ausschließlich
          deren Betreiber verantwortlich.
        </p>
      </Section>

      <Section title="8. Änderung der Nutzungsbedingungen">
        <p>
          Wir behalten uns vor, diese Nutzungsbedingungen mit Wirkung für die
          Zukunft anzupassen, etwa bei Änderungen des Funktionsumfangs oder der
          Rechtslage. Es gilt jeweils die zum Zeitpunkt der Nutzung auf dieser
          Seite veröffentlichte Fassung.
        </p>
      </Section>

      <Section title="9. Anwendbares Recht und Gerichtsstand">
        <p>
          Es gilt österreichisches Recht unter Ausschluss der
          Verweisungsnormen. Zwingende verbraucherschutzrechtliche Bestimmungen
          des Staates, in dem eine Nutzerin oder ein Nutzer ihren bzw. seinen
          gewöhnlichen Aufenthalt hat, bleiben unberührt.
        </p>
      </Section>

      <Section title="10. Kontakt">
        <p>
          Fragen zu diesen Nutzungsbedingungen richten Sie bitte an{" "}
          <a href={`mailto:${email}`} className="text-indigo-400 hover:text-indigo-300">{email}</a>.
          Ergänzend gelten unser{" "}
          <a href="/impressum" className="text-indigo-400 hover:text-indigo-300">Impressum</a>{" "}
          und unsere{" "}
          <a href="/datenschutz" className="text-indigo-400 hover:text-indigo-300">Datenschutzerklärung</a>.
        </p>
      </Section>
    </article>
  )
}
