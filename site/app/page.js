const REPO = "https://github.com/MatthewDegtyar/ontol-sessions";

const sources = [
  ["Ticket", "What was asked for, for whom, and who owns it."],
  ["Session", "What was tried, what was rejected, and why."],
  ["Code and PR", "What actually shipped."],
];

const results = [
  ["History", "8", "0 correct, 2 partial, 6 couldn't answer", "7 correct, 1 wrong"],
  ["Past pitfalls", "4", "2 correct, 2 partial", "3 correct, 1 partial"],
  ["Current state", "4", "4 correct", "4 correct"],
];

export default function Home() {
  return (
    <main>
      <nav>
        <span className="mark">ontol</span>
        <a href={REPO}>GitHub</a>
      </nav>

      <header>
        <h1>What did we build for this client, and why?</h1>
        <p className="lede">
          The reasoning behind custom work lives in AI coding sessions that nobody can find. ontol links those
          sessions to your tickets, so the next person or agent starts with what the last one learned.
        </p>
        <a className="button" href={REPO}>View the demo on GitHub</a>
      </header>

      <section>
        <h2>Before Globex gets a second export pipeline</h2>
        <p>
          A new ticket asks for a nightly export for Globex. Someone already built one for Northwind, and already
          learned what breaks. This is real output from the demo, which uses a made-up product and clients.
        </p>
        <pre tabIndex={0}><code>
          <span className="cmd">$ python3 ontol.py related HAR-117</span>{"\n"}
          {"HAR-101  Northwind  Done  6 matching messages\n"}
          {"  Nightly shipment export to SFTP for Northwind\n\n"}
          <span className="cmd">$ python3 ontol.py search &quot;cron restart&quot; --client northwind</span>{"\n"}
          {"[4] HAR-101 (Northwind) assistant: The cron job retries from scratch after a\n"}
          {"restart, so it can't tell the upload already happened. I'm dropping the cron\n"}
          {"approach and moving the export to the job queue with an idempotency key…"}
        </code></pre>
      </section>

      <section>
        <h2>Three records, one thread</h2>
        <dl className="sources">
          {sources.map(([term, text]) => (
            <div key={term}><dt>{term}</dt><dd>{text}</dd></div>
          ))}
        </dl>
        <p>
          Claude Code already records the git branch on every message. A branch like{" "}
          <code>sam/HAR-101-export</code> links that work to its ticket. Nothing is guessed, and anything without a
          key is listed as unlinked. If your branches already carry ticket keys, your team has nothing new to do.
        </p>
      </section>

      <section>
        <h2>What we&apos;ve measured so far</h2>
        <p>One small test on our own project: an agent answered 16 questions about past work, with and without the sessions.</p>
        <div className="table">
          <table>
            <thead><tr><th>Questions</th><th>Files and notes</th><th>With sessions</th></tr></thead>
            <tbody>
              {results.map(([name, n, files, db]) => (
                <tr key={name}><th scope="row">{name} ({n})</th><td>{files}</td><td>{db}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          We wrote the questions from the same transcripts, so the history result favours sessions by design. It&apos;s
          one person&apos;s project with one run per question, and it doesn&apos;t show that the resulting work gets better.
        </p>
      </section>

      <section>
        <h2>Try it with your agent</h2>
        <p>Point your coding agent at the repo. It runs the demo from made-up data and won&apos;t touch your sessions.</p>
        <pre tabIndex={0}><code>{`Read ${REPO.replace("https://", "")}/blob/main/AGENTS.md\nand run the demo.`}</code></pre>
      </section>

      <section>
        <h2>What this is today</h2>
        <ul>
          <li><strong>Works now:</strong> a local command-line tool for Claude Code sessions. No dependencies, and nothing leaves your machine.</li>
          <li><strong>Not built:</strong> team sync, a Jira connector, and checks for work that drifted from its ticket.</li>
          <li><strong>Be careful:</strong> redaction is pattern matching and can miss things, so don&apos;t share the database.</li>
        </ul>
      </section>

      <footer>
        Do you run client or forward-deployed work? We&apos;d like to hear how it goes back into your product:{" "}
        <a href={`${REPO}/issues`}>open an issue</a>.
      </footer>
    </main>
  );
}
