// Datenschutzerklärung für PadelYara.
//
// ENTWURF — inhaltlich auf die tatsächlichen Datenflüsse der App abgestimmt
// (Hosting, Photon/Komoot, MET Norway, eigenes Tracking, Newsletter, MongoDB).
// Vor dem produktiven Einsatz von einem Datenschutz-Generator/-Check gegenlesen
// lassen. Verantwortliche & Adresse müssen mit dem Impressum übereinstimmen.

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

export default function DatenschutzPage() {
  return (
    <article className="text-gray-300">
      <Helmet>
        <title>Datenschutz — PadelYara</title>
        <meta name="robots" content="noindex, follow" />
      </Helmet>
      <h1 className="text-white font-bold text-2xl mb-2">Datenschutzerklärung</h1>
      <p className="text-xs text-gray-600 mb-8">Stand: Juni 2026</p>

      <Section title="1. Verantwortliche">
        <p>
          Verantwortliche im Sinne der Datenschutz-Grundverordnung (DSGVO) ist:
        </p>
        <p className="text-gray-300">
          Cornelia Mayer<br />
          Griesgasse 2<br />
          2340 Mödling<br />
          Österreich<br />
          <a href={`mailto:${email}`} className="text-indigo-400 hover:text-indigo-300">{email}</a>
        </p>
      </Section>

      <Section title="2. Grundsätzliches">
        <p>
          Wir verarbeiten personenbezogene Daten nur im erforderlichen Umfang und
          auf Grundlage der DSGVO. Diese Erklärung informiert Sie gemäß Art. 13
          und 14 DSGVO über Art, Umfang und Zweck der Verarbeitung sowie über Ihre
          Rechte.
        </p>
        <p>
          PadelYara ist ein Dienst, der freie Padel-Court-Zeiten in Österreich
          aus verschiedenen Buchungsplattformen zusammenführt. Eine Registrierung
          oder ein Nutzerkonto ist für die Nutzung nicht erforderlich.
        </p>
      </Section>

      <Section title="3. Hosting">
        <p>
          Die Website (Frontend) wird bei <strong>Vercel Inc.</strong> (USA),
          die Programmschnittstelle (Backend) bei <strong>Railway Corporation</strong>{" "}
          (USA) gehostet. Beim Aufruf der Seite werden technisch notwendige Daten
          (insbesondere IP-Adresse, Datum/Uhrzeit, abgerufene Ressource,
          Browser-/Geräteinformationen) in Server-Logfiles verarbeitet, um den
          Betrieb, die Sicherheit und die Auslieferung der Inhalte zu
          gewährleisten.
        </p>
        <p>
          Rechtsgrundlage ist unser berechtigtes Interesse am sicheren und
          stabilen Betrieb (Art. 6 Abs. 1 lit. f DSGVO). Die Übermittlung in die
          USA erfolgt auf Grundlage der EU-Standardvertragsklauseln bzw. – soweit
          zertifiziert – des EU-US Data Privacy Framework. Mit beiden Anbietern
          besteht ein Auftragsverarbeitungsvertrag (Art. 28 DSGVO).
        </p>
      </Section>

      <Section title="4. Ortssuche und Geocodierung">
        <p>
          Für die Autovervollständigung von Ortsnamen während der Eingabe nutzen
          wir den Dienst <strong>Photon</strong> der <strong>komoot GmbH</strong>{" "}
          (Deutschland). Zur Umwandlung des von Ihnen gewählten Ortes in
          Koordinaten nutzen wir zusätzlich den Dienst <strong>Nominatim</strong>{" "}
          der <strong>OpenStreetMap Foundation</strong> (Vereinigtes Königreich).
          In beiden Fällen wird der von Ihnen eingegebene Ortsname direkt aus
          Ihrem Browser an den jeweiligen Dienst übermittelt, um Vorschläge bzw.
          Koordinaten zurückzugeben.
        </p>
        <p>
          Rechtsgrundlage ist unser berechtigtes Interesse an einer funktionalen
          Ortssuche (Art. 6 Abs. 1 lit. f DSGVO).
        </p>
      </Section>

      <Section title="5. Wetterdaten">
        <p>
          Zur Anzeige der Wetterprognose für den gewählten Spielzeitpunkt
          übermittelt unser Backend die Koordinaten des gesuchten Ortes an den
          Wetterdienst <strong>MET Norway</strong> (Norwegisches Meteorologisches
          Institut, <code>api.met.no</code>). Es werden dabei keine
          personenbezogenen Identifikatoren übertragen. Rechtsgrundlage ist unser
          berechtigtes Interesse an einer nützlichen Zusatzinformation
          (Art. 6 Abs. 1 lit. f DSGVO).
        </p>
      </Section>

      <Section title="6. Reichweitenmessung">
        <p>
          <strong>Eigene Statistik:</strong> Zur Verbesserung des Dienstes
          erfassen wir anonyme Nutzungsstatistiken auf unserem eigenen Server.
          Dabei werden <strong>keine Cookies</strong> gesetzt und{" "}
          <strong>keine IP-Adressen oder genauen Standorte</strong> gespeichert.
          Erfasst werden ausschließlich produktbezogene Ereignisse, z. B. dass
          eine Suche durchgeführt wurde, deren Ergebnisanzahl, die gewählte Region
          (vom Nutzer eingegebener Ortsname), die Gerätekategorie
          (Mobil/Tablet/Desktop) sowie technische Antwortzeiten. Ebenso erfassen
          wir Seitenaufrufe (welche Unterseite aufgerufen wurde) und – sofern Sie
          über einen Link von einer anderen Website kommen – den{" "}
          <strong>bloßen Domainnamen</strong> dieser Website (z. B.
          „google.com"), nicht jedoch die vollständige Adresse.
        </p>
        <p>
          Zur Unterscheidung wiederkehrender Besuche speichert Ihr Browser eine
          zufällig erzeugte Kennung (anonyme <code>session_id</code>) in seinem
          lokalen Speicher (localStorage). Diese Kennung enthält keine
          personenbezogenen Daten und lässt keinen Rückschluss auf Ihre Person zu.
          Sie können sie jederzeit durch Leeren des lokalen Speichers Ihres
          Browsers entfernen.
        </p>
        <p>
          <strong>Vercel Web Analytics &amp; Speed Insights:</strong> Zusätzlich
          nutzen wir die Dienste Web Analytics und Speed Insights unseres
          Hosting-Anbieters <strong>Vercel Inc.</strong> (USA). Web Analytics
          misst allgemeine Zugriffszahlen (z. B. Seitenaufrufe, Herkunftsseiten,
          Land, verwendeter Browsertyp); Speed Insights misst anonyme technische
          Leistungswerte zur Ladegeschwindigkeit der Seite. Beide Dienste
          arbeiten <strong>ohne Cookies</strong> und ohne dauerhafte
          Wiedererkennung einzelner Personen; es werden keine Profile gebildet
          und keine Daten an Werbenetzwerke weitergegeben. Die Übermittlung in
          die USA ist durch die in Abschnitt 3 genannten Garantien abgesichert.
        </p>
        <p>
          Rechtsgrundlage für die Reichweitenmessung ist unser berechtigtes
          Interesse an einer datensparsamen, anonymen Statistik
          (Art. 6 Abs. 1 lit. f DSGVO).
        </p>
      </Section>

      <Section title="7. Newsletter">
        <p>
          Wenn Sie sich für unseren Newsletter anmelden, verarbeiten wir die von
          Ihnen angegebene E-Mail-Adresse, um Ihnen Informationen zu PadelYara zu
          senden. Rechtsgrundlage ist Ihre Einwilligung (Art. 6 Abs. 1 lit. a
          DSGVO). Sie können diese Einwilligung jederzeit widerrufen, etwa über
          den Abmeldelink in jeder E-Mail oder per Nachricht an{" "}
          <a href={`mailto:${email}`} className="text-indigo-400 hover:text-indigo-300">{email}</a>.
        </p>
      </Section>

      <Section title="8. Datenspeicherung (Datenbank)">
        <p>
          Die oben genannten Statistik- und Newsletter-Daten werden in einer
          Datenbank bei <strong>MongoDB Atlas</strong> (MongoDB, Inc.) gespeichert.
          Die Daten werden in einem Rechenzentrum innerhalb der EU verarbeitet,
          sofern technisch nicht anders angegeben. Mit dem Anbieter besteht ein
          Auftragsverarbeitungsvertrag (Art. 28 DSGVO).
        </p>
      </Section>

      <Section title="9. Spielanalyse (öffentliche Turnierdaten)">
        <p>
          Die Funktion „Spielanalyse" ruft auf Anfrage öffentlich zugängliche
          Turnierergebnisse von <strong>padel-austria.at</strong> (Österreichische
          Padelunion) ab und stellt sie übersichtlich dar. Es handelt sich
          ausschließlich um Daten, die die Padelunion selbst öffentlich
          veröffentlicht (Spielname, Turnierergebnisse, Kategorien, Punktestand).
        </p>
        <p>
          Die abgerufenen Daten werden <strong>nicht dauerhaft gespeichert</strong> —
          jede Abfrage erfolgt live direkt von padel-austria.at und wird nach
          Darstellung im Browser nicht in unserer Datenbank abgelegt.
        </p>
        <p>
          Rechtsgrundlage ist unser berechtigtes Interesse an der übersichtlichen
          Darstellung öffentlich verfügbarer Sportstatistiken (Art. 6 Abs. 1 lit. f
          DSGVO). Spieler:innen, die eine Darstellung ihrer Daten auf PadelYara
          nicht wünschen, können dies jederzeit per E-Mail an{" "}
          <a href={`mailto:${email}`} className="text-indigo-400 hover:text-indigo-300">{email}</a>{" "}
          mitteilen — wir sperren den entsprechenden Slug umgehend.
        </p>
      </Section>

      <Section title="10. Lokaler Speicher (localStorage)">
        <p>
          Wir verwenden den lokalen Speicher Ihres Browsers für technisch
          notwendige bzw. funktionale Zwecke, insbesondere für die oben genannte
          anonyme Statistik-Kennung und zur Speicherung Ihrer Einstellungen. Es
          werden dabei keine Tracking-Cookies und keine Cookies von Drittanbietern
          zu Werbezwecken eingesetzt.
        </p>
      </Section>

      <Section title="11. Ihre Rechte">
        <p>
          Sie haben nach der DSGVO das Recht auf Auskunft (Art. 15), Berichtigung
          (Art. 16), Löschung (Art. 17), Einschränkung der Verarbeitung (Art. 18),
          Datenübertragbarkeit (Art. 20) sowie ein Widerspruchsrecht (Art. 21).
          Erteilte Einwilligungen können Sie jederzeit mit Wirkung für die Zukunft
          widerrufen.
        </p>
        <p>
          Zur Ausübung Ihrer Rechte genügt eine Nachricht an{" "}
          <a href={`mailto:${email}`} className="text-indigo-400 hover:text-indigo-300">{email}</a>.
        </p>
        <p>
          Ihnen steht zudem ein Beschwerderecht bei der Aufsichtsbehörde zu. In
          Österreich ist dies die{" "}
          <a
            href="https://www.dsb.gv.at"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-400 hover:text-indigo-300"
          >
            Österreichische Datenschutzbehörde
          </a>.
        </p>
      </Section>
    </article>
  )
}
