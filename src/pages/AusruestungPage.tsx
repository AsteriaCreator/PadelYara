import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"

const JSON_LD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Was kostet Padel Ausrüstung für Anfänger?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Realistisch €130–180: Schuhe €60–80, Schläger €40–60, Bälle €10. Mehr ist Overspending.",
      },
    },
    {
      "@type": "Question",
      "name": "Welchen Padel Schläger für Anfänger?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Rundes Kopfprofil, 330–360 g, unter €80. Marke ist egal.",
      },
    },
    {
      "@type": "Question",
      "name": "Brauche ich spezielle Schuhe für Padel?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Ja. Padel wird auf Sand gespielt — du brauchst eine Fischgrätensohle für die Lateralbewegungen. Laufschuhe sind ein Verletzungsrisiko.",
      },
    },
    {
      "@type": "Question",
      "name": "Kann ich Tennisschuhe für Padel benutzen?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Clay-Tennisschuhe funktionieren. Hartplatz-Tennisschuhe nicht — falsche Sohle für Sandbelag.",
      },
    },
    {
      "@type": "Question",
      "name": "Wie lange halten Padel Bälle?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Druckbälle halten 5–10 Sessions. Danach sind sie spürbar weicher und machen das Lernen schwerer als nötig.",
      },
    },
    {
      "@type": "Question",
      "name": "Was ist der Unterschied zwischen teuren und günstigen Padel Schlägern?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Kontrolle, Steifigkeit und Gewichtsverteilung. Alles davon ist irrelevant, bevor du 50 Spielstunden hast.",
      },
    },
  ],
}

export default function AusruestungPage() {
  return (
    <>
      <Helmet>
        <title>Padel Ausrüstung für Anfänger — was du brauchst (und was nicht) | PadelYara</title>
        <meta
          name="description"
          content="Was du für Padel wirklich brauchst: Schläger, Schuhe, Bälle — und was du dir sparen kannst. Yara erklärt es. Kurz und ohne Umweg."
        />
        <link rel="canonical" href="https://www.padelyara.at/ausruestung" />
        <script type="application/ld+json">{JSON.stringify(JSON_LD)}</script>
      </Helmet>

      {/* HERO */}
      <div
        style={{
          position: "relative",
          height: "42vh",
          minHeight: 200,
          overflow: "hidden",
          borderBottom: "1px solid rgba(212,245,60,0.12)",
          marginLeft: -16,
          marginRight: -16,
          marginTop: -16,
        }}
      >
        <img
          src="/ausruestung-hero.jpg"
          alt="Yara mit Padel-Schläger"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center 60%",
            filter: "brightness(1.1)",
            animation: "ausruestung-zoom 8s ease-out forwards",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(to right, rgba(8,8,16,0.7) 40%, rgba(8,8,16,0.05) 100%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
            padding: "0 16px 24px",
          }}
        >
          <p style={{ fontSize: 11, color: "rgba(212,245,60,0.45)", marginBottom: 10, letterSpacing: "0.04em" }}>
            <Link to="/" style={{ color: "rgba(212,245,60,0.45)", textDecoration: "none" }}>← Startseite</Link>
            {" / "}Ausrüstung
          </p>
          <h1
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 30,
              fontWeight: 700,
              color: "#fff",
              letterSpacing: "0.01em",
              lineHeight: 1.1,
              marginBottom: 8,
              animation: "ausruestung-fadein 0.8s 0.3s both",
            }}
          >
            Padel Ausrüstung.<br />
            Was du brauchst.<br />
            Was nicht.
          </h1>
          <p
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 15,
              fontStyle: "italic",
              color: "#d4f53c",
              animation: "ausruestung-fadein 0.8s 0.55s both",
            }}
          >
            Die meisten Anfänger kaufen zu viel. Zu teuer. Zu früh.
          </p>
        </div>
      </div>

      <style>{`
        @keyframes ausruestung-zoom {
          from { transform: scale(1); }
          to   { transform: scale(1.18); }
        }
        @keyframes ausruestung-fadein {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* CONTENT */}
      <div style={{ maxWidth: 680, paddingTop: 8 }}>

        {/* Schläger */}
        <Section>
          <Verdict type="yes">Kaufen</Verdict>
          <SectionHeading>Der Schläger</SectionHeading>
          <p style={body}>
            Rundes Kopfprofil. 330–360 g. Budget €40–80. Das ist alles.
            Ein Einsteigeschläger für €80 limitiert dein Spiel nicht — deine Technik tut das.
          </p>
          <p style={body}>
            Carbon-Fiber, 3K-Weave, Hybrid-EVA-Kern: irrelevant bis du 50 Stunden auf dem Court hast.
            Danach weißt du was du willst.
          </p>
          <Callout>
            Wenn der Schläger teurer ist als dein erstes Quartal Courtmiete, hast du Priorisierungsfehler.
          </Callout>
        </Section>

        {/* Schuhe */}
        <Section>
          <Verdict type="warn">Hier sparen = Fehler</Verdict>
          <SectionHeading>Die Schuhe</SectionHeading>
          <p style={body}>
            Das einzige Equipment, wo Sparen nach hinten losgeht. Lateralbewegungen auf Sand erfordern
            eine Fischgrätensohle. Normale Laufschuhe funktionieren — bis du umknickst.
          </p>
          <p style={body}>
            Budget: €60–100. Padel-Schuhe, alternativ Clay-Tennisschuhe. Kein Kompromiss.
          </p>
        </Section>

        {/* Bälle */}
        <Section>
          <Verdict type="yes">Kaufen, wegwerfen, wiederholen</Verdict>
          <SectionHeading>Die Bälle</SectionHeading>
          <p style={body}>
            Druckbälle. Sie sterben nach 5–10 Sessions. Anfänger merken es oft nicht —
            das ist kein Vorteil, das macht das Lernen schwerer.
          </p>
          <p style={body}>3er-Pack kaufen. Spielen bis sie tot sind. Neues 3er-Pack kaufen.</p>
        </Section>

        {/* Nicht kaufen */}
        <Section>
          <Verdict type="no">Nicht kaufen</Verdict>
          <SectionHeading>Was du nicht brauchst</SectionHeading>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
            {[
              { label: "Handschuhe", text: "Overgrip wenn überhaupt. Handschuhe sind Placebo." },
              { label: "Padel-Tasche", text: "Kauf erst eine wenn du einen Schläger hast der es wert ist." },
              { label: "Performance-Shirts", text: "Niemand schaut auf dein Shirt wenn du noch nicht returnieren kannst." },
              { label: "Vibrationsdämpfer", text: "Tennis-Ritual das bei Padel keinen Sinn ergibt." },
            ].map(item => (
              <div
                key={item.label}
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: 6,
                  padding: "10px 12px",
                }}
              >
                <p style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.07em", color: "#f07070", marginBottom: 3 }}>
                  ✗ {item.label}
                </p>
                <p style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.6 }}>{item.text}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* FAQ */}
        <Section>
          <SectionHeading>Häufige Fragen</SectionHeading>
          {JSON_LD.mainEntity.map(q => (
            <div
              key={q.name}
              style={{ borderTop: "1px solid rgba(255,255,255,0.05)", padding: "11px 0" }}
            >
              <p style={{ fontSize: 13, fontWeight: 600, color: "#e0e0e0", marginBottom: 3 }}>{q.name}</p>
              <p style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.65 }}>{q.acceptedAnswer.text}</p>
            </div>
          ))}
        </Section>

        {/* CTA */}
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 20, paddingBottom: 32 }}>
          <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
            Ausrüstung geklärt. Jetzt einen Court buchen.
          </p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Link to="/padelrevier" style={ctaBtn}>→ Alle Padel-Anlagen in Österreich</Link>
            <Link to="/padelrevier/wien" style={ctaBtn}>→ Padel Courts Wien</Link>
          </div>
        </div>

      </div>
    </>
  )
}

function Section({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: "22px 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
      {children}
    </div>
  )
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2
      style={{
        fontFamily: "'Barlow Condensed', sans-serif",
        fontSize: 18,
        fontWeight: 700,
        color: "#fff",
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        margin: "6px 0 10px",
      }}
    >
      {children}
    </h2>
  )
}

function Verdict({ type, children }: { type: "yes" | "no" | "warn"; children: React.ReactNode }) {
  const styles: Record<string, React.CSSProperties> = {
    yes:  { background: "rgba(212,245,60,0.10)", color: "#d4f53c",  border: "1px solid rgba(212,245,60,0.28)" },
    no:   { background: "rgba(220,60,60,0.10)",  color: "#f07070",  border: "1px solid rgba(220,60,60,0.25)"  },
    warn: { background: "rgba(255,160,40,0.10)", color: "#ffaa44",  border: "1px solid rgba(255,160,40,0.28)" },
  }
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 10,
        fontWeight: 700,
        padding: "2px 8px",
        borderRadius: 4,
        letterSpacing: "0.07em",
        textTransform: "uppercase",
        ...styles[type],
      }}
    >
      {children}
    </span>
  )
}

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "rgba(212,245,60,0.05)",
        border: "1px solid rgba(212,245,60,0.14)",
        borderLeft: "2px solid #d4f53c",
        borderRadius: "0 6px 6px 0",
        padding: "10px 14px",
        marginTop: 10,
      }}
    >
      <p style={{ fontSize: 12, color: "#bbb", lineHeight: 1.65, margin: 0 }}>{children}</p>
    </div>
  )
}

const body: React.CSSProperties = {
  fontSize: 13,
  color: "#9ca3af",
  lineHeight: 1.75,
  marginBottom: 6,
}

const ctaBtn: React.CSSProperties = {
  display: "inline-block",
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.04em",
  padding: "8px 16px",
  borderRadius: 6,
  background: "rgba(212,245,60,0.10)",
  color: "#d4f53c",
  border: "1px solid rgba(212,245,60,0.25)",
  textDecoration: "none",
}
