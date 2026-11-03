import { readFileSync } from "node:fs";
import path from "node:path";
import ForkExplorer, { Files } from "./components/product";
import { CONTACT } from "./components/site";

const globex = JSON.parse(readFileSync(path.join(process.cwd(), "public/demo-data/globex.json"), "utf8"));
const poNumber = globex.capabilities["POST /invoices/{id}/send"];

const Line = ({ d }) => (
  <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.700" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);

const problems = [
  [<path key="a" d="M8 7h11M8 12h11M8 17h11M4 7h.01M4 12h.01M4 17h.01" />, "Nobody has the full list", "Ask what a client's version can do that the main product can't. The answer usually means finding whoever built it."],
  [<path key="b" d="M9 4H5v4M15 4h4v4M9 20H5v-4M15 20h4v-4" />, "The same feature gets built twice", "One client's export becomes another client's export, written from scratch by someone who never saw the first one."],
  [<path key="c" d="M12 8v5M12 17h.01M4 12a8 8 0 1 0 16 0 8 8 0 0 0-16 0" />, "The reasoning disappears", "What was tried and rejected lives in tickets and coding sessions nobody can find. Then the next person repeats it."],
];

const steps = [
  ["1", "Map the product from code", "Routes and the code behind them become a plain map of what your product does, grouped into areas anyone can read."],
  ["2", "Compare every fork to main", "See what each client's version adds or changes, with lines back to the part of the product it builds on."],
  ["3", "Attach the why", "Link each extension to the ticket that asked for it and the sessions that built it, so the reasoning travels with the work."],
];

const roadmap = [
  ["1", "Connect your repos", "Read your main repo and client forks from GitHub, and build the product map from your real code.", "Know what each client's version can do without chasing down whoever built it."],
  ["2", "Link tickets to code", "Tie each ticket to its branch, commits, PR and files, using the ticket keys your team already writes. Work with no key is listed, not guessed.", "Every custom feature has a clear record of who asked, who owns it and what it touched, which makes handoffs and scoping quicker."],
  ["3", "Attach the coding sessions", "Add the AI coding sessions behind each ticket, including what was tried and rejected.", "The next person or agent starts with what the last one learned, instead of repeating a dead end."],
  ["4", "Spot the same feature across clients", "Flag when two clients have their own version of the same feature, and show how the two differ.", "Catch rebuilds before they start, and make the case for moving work into the main product with evidence."],
];

export default function Home() {
  return (
    <>
      <main>
        <header className="hero">
          <div className="wrap">
            <h1>Know what every client fork <em>actually does</em></h1>
            <p className="sub">
              ProductOlogy maps your client forks against your main product, so anyone can see what was added,
              why it was built, and what belongs back in the product.
            </p>
            {CONTACT && (
              <div className="actions">
                <a className="btn primary" href={CONTACT}>Talk to us</a>
              </div>
            )}
            <div className="preview">
              <div className="frame">
                <div className="frame-bar"><span>Sample product: Harbor, with two fictional clients</span></div>
                <ForkExplorer compact />
              </div>
            </div>
          </div>
        </header>

        <section className="band" id="problem">
          <div className="wrap">
            <p className="eyebrow">The problem</p>
            <h2>Custom work is how you win clients, then lose track of them</h2>
            <p className="intro">Forward-deployed and client teams ship what the deal needs. Six months later, git can show you every changed line and still not tell you what the client can do.</p>
            <div className="grid3">
              {problems.map(([icon, title, text]) => (
                <article className="tile" key={title}>
                  <span className="tile-icon"><Line d={icon} /></span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="band" id="how">
          <div className="wrap">
            <p className="eyebrow">How it works</p>
            <h2>From a pile of diffs to a map people can read</h2>
            <p className="intro">Your team keeps working in the same tickets and branches. ProductOlogy reads what&apos;s already there.</p>
            <div className="grid3">
              {steps.map(([n, title, text]) => (
                <article className="tile" key={n}>
                  <span className="step">Step {n}</span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="band">
          <div className="wrap split">
            <div>
              <p className="eyebrow">Every extension, down to the file</p>
              <h2>Start with the product. Drop into the code when you need it.</h2>
              <p className="intro">One client asked for PO numbers on invoices. That one request reached the API, the database and the UI, and would break other clients if merged as is.</p>
              <ul className="ticks">
                <li><strong>For product and delivery:</strong> what changed, in plain language.</li>
                <li><strong>For engineers:</strong> every file and line, grouped by what it was for.</li>
              </ul>
            </div>
            <Files files={poNumber.files} />
          </div>
        </section>

        <section className="band">
          <div className="wrap">
            <p className="eyebrow">Merge decisions</p>
            <h2>See when one client&apos;s lesson never reached the next</h2>
            <p className="intro">Two clients in the demo asked for a nightly export, and two people built it separately.</p>
            <div className="compare">
              <article className="client-card good">
                <p className="who">Northwind</p>
                <h3>Nightly export to SFTP</h3>
                <p>A plain cron job sent the file twice after a restart, which would have double-counted shipments in billing. It moved to a job queue that can&apos;t send twice.</p>
              </article>
              <article className="client-card risk">
                <p className="who">Globex</p>
                <h3>Nightly export to S3</h3>
                <p>Built later on the plain scheduler, without the retry protection Northwind&apos;s export ended up needing.</p>
              </article>
            </div>
            <p className="verdict"><strong>Built twice.</strong> That makes it a candidate for your main product, and you can see which version to start from.</p>
          </div>
        </section>

        <section className="band" id="next">
          <div className="wrap">
            <p className="eyebrow">What&apos;s next</p>
            <h2>Link every ticket to the code it actually changed</h2>
            <p className="intro">
              Today the demo runs on a sample product, and its links between tickets and code are written by hand. Next, they
              come from what your team already does: a ticket key on a branch ties the ticket to its commits, its PR and every file they touched.
            </p>

            <ol className="chain" aria-label="Example of how a ticket links to code">
              <li><span>Ticket</span><strong>HAR-124</strong><em>Require a PO number on invoices</em></li>
              <li><span>Branch</span><strong>lee/HAR-124-po-number</strong><em>The ticket key is already in the name</em></li>
              <li><span>Commits and PR</span><strong>What was merged</strong><em>Read from git and GitHub</em></li>
              <li><span>Files</span><strong>3 files, +6 −2</strong><em>API, database and UI</em></li>
            </ol>

            <h3 className="roadmap-title">What we&apos;re building, and what it should change for an FDE team</h3>
            <div className="roadmap">
              <div className="roadmap-head" aria-hidden="true"><span>On the roadmap</span><span>What the FDE team gets</span></div>
              {roadmap.map(([n, title, build, gain]) => (
                <article className="roadmap-row" key={n}>
                  <div className="roadmap-build"><span className="step">{n}</span><h4>{title}</h4><p>{build}</p></div>
                  <div className="roadmap-gain"><span className="gain-label">For the FDE team</span><p>{gain}</p></div>
                </article>
              ))}
            </div>
            <p className="roadmap-note">These are the gains we&apos;re aiming for, not measured results. We&apos;re looking for FDE teams to test them with.</p>
          </div>
        </section>

        <section className="closing">
          <div className="wrap">
            <h2>What can your clients do that your product can&apos;t?</h2>
            <p>Scroll up to see how the answer looks on a sample product.</p>
            {CONTACT && (
              <div className="actions">
                <a className="btn primary" href={CONTACT}>Talk to us</a>
              </div>
            )}
          </div>
        </section>
      </main>

      <footer className="foot">
        <div className="wrap"><span>ProductOlogy</span><span>Northwind, Globex and Harbor are fictional examples.</span></div>
      </footer>
    </>
  );
}
